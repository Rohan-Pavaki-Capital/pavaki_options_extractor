"""
FastAPI Backend for Pavaki Options Extractor
==================================================

Wires the existing extraction pipeline (options.py, Anthropic/, format/,
database/) behind an HTTP API used by the React frontend.

Endpoints:
    POST   /api/extract            - Upload PDF, return job_id, start async run
    GET    /api/job/{job_id}       - Poll job status + progress
    GET    /api/result/{job_id}    - Final JSON result
    GET    /api/download/{job_id}/excel  - Download Excel file
    DELETE /api/job/{job_id}       - Cancel/delete a job
    GET    /api/health             - Health check
    GET    /api/jobs               - List jobs (debug)

Run:
    uvicorn backend:app --reload --port 8000
"""

import json
import os
import shutil
import sys
import time
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Pipeline modules (live at project root) ──────────────────────────
from options import (
    detect_relevant_pages,
    extract_text_from_pages,
    rasterize_pages,
    CostTracker,
)
from Anthropic import (
    extract_with_claude,
    validate_all_plans,
    validate_final_output,
    merge_results,
    set_verbose as _set_anthropic_verbose,
)
from format.json_to_excel import build_workbook
from database.storage import save_extraction

import anthropic
from openai import OpenAI


# ═════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

JOBS: dict[str, dict] = {}


# ═════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═════════════════════════════════════════════════════════════════════

class JobStatus(BaseModel):
    job_id: str
    status: str
    filename: str
    file_size: int
    created_at: str
    updated_at: str
    progress: int
    current_stage: Optional[str] = None
    stages: dict = {}
    elapsed_seconds: float = 0
    estimated_remaining: Optional[float] = None
    cost_so_far: float = 0
    error: Optional[str] = None
    result_available: bool = False
    extraction_id: Optional[int] = None


# ═════════════════════════════════════════════════════════════════════
# JOB MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

def create_job(filename: str, file_size: int) -> str:
    job_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()

    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "filename": filename,
        "file_size": file_size,
        "created_at": now,
        "updated_at": now,
        "progress": 0,
        "current_stage": None,
        "stages": {
            "upload": {"status": "completed", "duration": 0, "cost": 0},
            "stage1_keywords": {"status": "pending", "duration": None, "cost": 0},
            "stage2_classifier": {"status": "pending", "duration": None, "cost": 0},
            "stage3_extraction": {"status": "pending", "duration": None, "cost": 0},
            "validation": {"status": "pending", "duration": None, "cost": 0},
            "excel_generation": {"status": "pending", "duration": None, "cost": 0},
        },
        "elapsed_seconds": 0,
        "estimated_remaining": 20.0,
        "cost_so_far": 0,
        "start_time": time.time(),
        "result_available": False,
        "extraction_id": None,
    }
    return job_id


def update_job(job_id: str, **updates):
    if job_id not in JOBS:
        return
    JOBS[job_id].update(updates)
    JOBS[job_id]["updated_at"] = datetime.utcnow().isoformat()
    JOBS[job_id]["elapsed_seconds"] = time.time() - JOBS[job_id]["start_time"]


def get_job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _mark_stage(job_id: str, stage_key: str, duration: float, cost: float, details: str):
    JOBS[job_id]["stages"][stage_key] = {
        "status": "completed",
        "duration": duration,
        "cost": cost,
        "details": details,
    }


# ═════════════════════════════════════════════════════════════════════
# EXTRACTION WORKER
# ═════════════════════════════════════════════════════════════════════

def run_extraction_pipeline(job_id: str):
    """Mirror of options.py main() flow, instrumented with progress updates."""
    job = JOBS[job_id]
    job_dir = get_job_dir(job_id)
    pdf_path = job_dir / job["filename"]
    pdf_stem = Path(job["filename"]).stem

    try:
        _set_anthropic_verbose(False)

        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

        together_key = os.environ.get("TOGETHER_API_KEY")
        together_model = os.environ.get(
            "TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        )

        cost_tracker = CostTracker(together_model=together_model)

        # ── Stage 1 + 2: page detection ────────────────────────────
        update_job(job_id, status="processing",
                   current_stage="stage1_keywords", progress=5)

        together_client = None
        if together_key and together_key != "your_together_key_here":
            try:
                together_client = OpenAI(
                    api_key=together_key,
                    base_url="https://api.together.xyz/v1",
                )
            except Exception:
                together_client = None

        stage_start = time.time()
        target_pages, classifications = detect_relevant_pages(
            str(pdf_path),
            together_client=together_client,
            together_model=together_model,
            skip_llm=together_client is None,
            debug=False,
            cost_tracker=cost_tracker,
        )
        detect_duration = time.time() - stage_start

        _mark_stage(job_id, "stage1_keywords",
                    duration=min(detect_duration * 0.2, 3.0),
                    cost=0,
                    details=f"Scanned PDF, {len(target_pages)} candidate page(s) found")

        stage2_cost = cost_tracker.together_cost()
        update_job(job_id, current_stage="stage2_classifier", progress=20,
                   cost_so_far=stage2_cost)

        _mark_stage(job_id, "stage2_classifier",
                    duration=detect_duration * 0.8,
                    cost=round(stage2_cost, 4),
                    details=f"{len(target_pages)} page(s) confirmed")

        if not target_pages:
            raise RuntimeError("No relevant pages detected in PDF")

        # ── Stage 3: Claude extraction ─────────────────────────────
        update_job(job_id, current_stage="stage3_extraction", progress=30)
        stage_start = time.time()

        texts = extract_text_from_pages(str(pdf_path), target_pages)
        images = rasterize_pages(str(pdf_path), target_pages)

        client = anthropic.Anthropic(api_key=anthropic_key)
        batch_size = 12
        all_results = []
        for i in range(0, len(target_pages), batch_size):
            batch = target_pages[i:i + batch_size]
            bt = {pg: texts[pg] for pg in batch if pg in texts}
            bi = {pg: images[pg] for pg in batch if pg in images}
            result = extract_with_claude(
                client, bt, bi, "claude-sonnet-4-20250514",
                use_vision=True,
                skip_validation=False,
                cost_tracker=cost_tracker,
            )
            all_results.append(result)

        if not all_results:
            final = {"company_name": None, "report_period": None,
                     "currency": None, "plans": []}
        elif len(all_results) == 1:
            final = all_results[0]
        else:
            final = merge_results(all_results)

        stage3_cost = cost_tracker.anthropic_cost()
        _mark_stage(job_id, "stage3_extraction",
                    duration=time.time() - stage_start,
                    cost=round(stage3_cost, 4),
                    details=f"{len(final.get('plans', []))} plan(s) extracted")

        update_job(job_id, current_stage="validation", progress=80,
                   cost_so_far=stage2_cost + stage3_cost)

        # ── Validation ─────────────────────────────────────────────
        stage_start = time.time()
        final = validate_all_plans(final)
        final = validate_final_output(final)
        _mark_stage(job_id, "validation",
                    duration=time.time() - stage_start,
                    cost=0,
                    details="Roll-forward math validated")

        # ── Meta block ─────────────────────────────────────────────
        final["_meta"] = {
            "source_pdf": job["filename"],
            "total_pdf_pages": _pdf_page_count(pdf_path),
            "pages_processed": target_pages,
            "mode": "vision+text",
            "model": "claude-sonnet-4-20250514",
            "validation_pass": True,
            "detection": {
                "stage2_classifier": together_model if together_client else "skipped",
                "classifications": {
                    str(pg): {
                        "decision": classifications[pg].get("decision"),
                        "confidence": classifications[pg].get("confidence"),
                        "reason": classifications[pg].get("reason"),
                    }
                    for pg in target_pages if pg in classifications
                },
            },
            "cost": cost_tracker.summary(),
        }

        # ── Excel + DB save ────────────────────────────────────────
        update_job(job_id, current_stage="excel_generation", progress=90)
        stage_start = time.time()

        json_path = job_dir / "extraction.json"
        excel_path = job_dir / f"{pdf_stem}_options.xlsx"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)

        build_workbook(str(json_path), str(excel_path))
        xlsx_bytes = excel_path.read_bytes()

        extraction_id = None
        try:
            extraction_id = save_extraction(final, xlsx_bytes, excel_path.name)
        except Exception as e:
            print(f"WARNING: NeonDB save failed: {e}", file=sys.stderr)

        _mark_stage(job_id, "excel_generation",
                    duration=time.time() - stage_start,
                    cost=0,
                    details="Excel workbook generated")

        total_cost = cost_tracker.total_cost()
        update_job(
            job_id,
            status="completed",
            progress=100,
            current_stage=None,
            result_available=True,
            cost_so_far=round(total_cost, 4),
            extraction_id=extraction_id,
        )

    except Exception as e:
        traceback.print_exc()
        update_job(job_id, status="failed", error=str(e)[:500])


def _pdf_page_count(pdf_path: Path) -> int:
    try:
        import fitz
        with fitz.open(pdf_path) as doc:
            return len(doc)
    except Exception:
        return 0


# ═════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Pavaki Options Extractor API",
    description="Extract share-based compensation data from annual reports",
    version="1.0.0",
)

_default_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_extra_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": "Pavaki Options Extractor API", "status": "ready"}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "active_jobs": len(JOBS)}


@app.post("/api/extract")
async def extract_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)",
        )

    job_id = create_job(file.filename, len(contents))
    job_dir = get_job_dir(job_id)
    pdf_path = job_dir / file.filename
    with open(pdf_path, "wb") as f:
        f.write(contents)

    background_tasks.add_task(run_extraction_pipeline, job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "filename": file.filename,
        "file_size": len(contents),
    }


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS[job_id].copy()
    job["elapsed_seconds"] = time.time() - job["start_time"]

    if job["status"] == "processing" and job["progress"] > 0:
        elapsed = job["elapsed_seconds"]
        estimated_total = elapsed / (job["progress"] / 100)
        job["estimated_remaining"] = max(0, estimated_total - elapsed)
    elif job["status"] == "completed":
        job["estimated_remaining"] = 0

    job.pop("start_time", None)
    return job


@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS[job_id]
    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job not ready (status: {job['status']})",
        )

    json_path = get_job_dir(job_id) / "extraction.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found")

    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/download/{job_id}/excel")
async def download_excel(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    job = JOBS[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Job not completed")

    job_dir = get_job_dir(job_id)
    excel_files = list(job_dir.glob("*.xlsx"))
    if not excel_files:
        raise HTTPException(status_code=404, detail="Excel file not found")

    excel_path = excel_files[0]
    return FileResponse(
        path=excel_path,
        filename=excel_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.delete("/api/job/{job_id}")
async def cancel_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    JOBS[job_id]["status"] = "cancelled"
    job_dir = get_job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    JOBS.pop(job_id, None)
    return {"status": "cancelled", "job_id": job_id}


@app.get("/api/jobs")
async def list_jobs():
    return {
        "total": len(JOBS),
        "jobs": [
            {
                "job_id": j["job_id"],
                "filename": j["filename"],
                "status": j["status"],
                "progress": j["progress"],
                "created_at": j["created_at"],
            }
            for j in JOBS.values()
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
