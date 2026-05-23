@echo off
REM One-command installer: install Python deps and create NeonDB tables.

echo === Installing Python dependencies ===
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo.
echo === Creating tables in NeonDB ===
python -m database.setup
if errorlevel 1 (
    echo ERROR: database setup failed. Check db_string in .env.
    exit /b 1
)

echo.
echo Setup complete. Run extractions with: python options.py ^<pdf_path^>
