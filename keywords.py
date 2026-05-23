"""
Keyword patterns for the Stage 1 lenient candidate filter.

PHILOSOPHY:
  Stage 1 is a CHEAP wide-net filter. Its job is to eliminate obvious
  non-candidates (TOC, blank pages, unrelated notes) without missing
  any legitimate options disclosure. Precision is the LLM's job in Stage 2.

A page becomes a candidate if ANY of these conditions match:
  1. NOTE_TITLE_PATTERNS match (strongest signal - actual section header)
  2. PLAN_CODE_KEYWORDS match (specific plan acronyms - rarely false positive)
  3. VALUATION_KEYWORDS match (Black-Scholes/Monte Carlo - very specific)
  4. 3+ ROLLFORWARD_PATTERNS matches (full opening→granted→exercised→closing sequence)
  5. GENERIC_KEYWORDS match AND page has a numeric table
  6. SECTION_HEADERS match AND page has a numeric table
  7. NON_ENGLISH_KEYWORDS match (German, French, Spanish, Chinese, Japanese)

All patterns are regex strings, applied case-insensitively against page text
(except non-ASCII patterns which are applied to the raw text).
"""

# ─────────────────────────────────────────────────────────────────────────
# TIER 1: HIGH-PRECISION PLAN CODES
# These acronyms rarely appear outside of share-based payment disclosures.
# A single match makes the page a candidate.
# ─────────────────────────────────────────────────────────────────────────
PLAN_CODE_KEYWORDS = [
    # UK plans
    r"\bLTIP\b",          # Long-Term Incentive Plan
    r"\bPSP\b",           # Performance Share Plan
    r"\bSAYE\b",          # Save As You Earn
    r"\bCSOP\b",          # Company Share Option Plan
    r"\bSIP\b",           # Share Incentive Plan
    r"\bSRSOS\b",         # Savings Related Share Option Scheme
    r"\bDBP\b",           # Deferred Bonus Plan
    r"\bDSP\b",           # Deferred Share Plan
    r"\bRSP\b",           # Restricted Share Plan
    r"\bESOS\b",          # Executive Share Option Scheme
    r"\bSOS\b",           # Share Option Scheme
    r"\bAESOP\b",         # All Employee Share Ownership Plan

    # US plans
    r"\bRSUs?\b",         # Restricted Stock Units
    r"\bPSUs?\b",         # Performance Stock Units
    r"\bESPP\b",          # Employee Stock Purchase Plan
    r"\bESOPs?\b",        # Employee Stock Ownership Plan
    r"\bNQSO\b",          # Non-Qualified Stock Options
    r"\bISO\b",           # Incentive Stock Options
    r"\bSARs?\b",         # Stock Appreciation Rights

    # Phrased plans
    r"save\s*as\s*you\s*earn",
    r"sharesave\s*(?:plan|scheme)",
    r"performance\s*share\s*plan",
    r"long[\s\-]*term\s*incentive\s*plan",
    r"restricted\s*stock\s*units?",
    r"restricted\s*share\s*units?",
    r"employee\s*stock\s*purchase",
    r"employee\s*share\s*ownership\s*plan",
    r"deferred\s*bonus\s*plan",
    r"founders?\s*performance\s*plan",
    r"co[\s\-]*investment\s*plan",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 2: VALUATION MODEL KEYWORDS
# These appear almost exclusively in option valuation disclosures.
# A single match makes the page a candidate.
# ─────────────────────────────────────────────────────────────────────────
VALUATION_KEYWORDS = [
    r"black[\s\-]*scholes\s*(?:model|formula|valuation)?",
    r"monte[\s\-]*carlo\s*(?:simulation|model|valuation)",
    r"binomial\s*(?:model|valuation|tree|lattice)",
    r"trinomial\s*(?:model|tree|lattice)",
    r"option\s*pricing\s*model",
    r"lattice\s*model",
    r"finnerty\s*model",
    r"ghaidarov\s*(?:adjustment|model)",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 3: GENERIC KEYWORDS (require corroboration)
# These can appear in policy text, so we only treat them as a signal
# if the page ALSO has a numeric table.
# ─────────────────────────────────────────────────────────────────────────
GENERIC_KEYWORDS = [
    r"share[\s\-]*based\s*(?:payment|compensation|remuneration)",
    r"share\s*options?",
    r"stock\s*options?",
    r"share\s*option\s*scheme",
    r"equity[\s\-]*settled\s*(?:share|award|option)",
    r"cash[\s\-]*settled\s*(?:share|award|option)",
    r"nil[\s\-]*cost\s*option",
    r"option\s*(?:plan|scheme|programme)",
    r"warrant\s*(?:plan|scheme|programme|holders?)",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 4: ROLL-FORWARD TABLE PATTERNS
# These specifically describe the structure of an options activity table.
# 3+ matches alone (without other signals) makes a page a candidate.
# 1-2 matches require a plan keyword to also be present.
# ─────────────────────────────────────────────────────────────────────────
ROLLFORWARD_PATTERNS = [
    # Opening balance variants
    r"(?:outstanding|options?|awards?|units?|warrants?)\s*(?:at|as\s*at)\s*(?:the\s*)?(?:beginning|start)\s*of\s*(?:the\s*)?(?:year|period)",
    r"(?:outstanding|options?|awards?|units?|warrants?)\s*(?:at|as\s*at)\s*1\s*(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"(?:opening|brought\s*forward)\s*balance",

    # Closing balance variants
    r"(?:outstanding|options?|awards?|units?|warrants?)\s*(?:at|as\s*at)\s*(?:the\s*)?(?:end|year[\s\-]*end)\s*of\s*(?:the\s*)?(?:year|period)",
    r"(?:outstanding|options?|awards?|units?|warrants?)\s*(?:at|as\s*at)\s*3[01]\s*(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"(?:closing|carried\s*forward)\s*balance",

    # Activity verbs in table format
    r"granted\s*(?:during|in)\s*(?:the\s*)?(?:year|period)",
    r"(?:lapsed|forfeited|cancelled|expired|surrendered)\s*(?:during|in)\s*(?:the\s*)?(?:year|period)",
    r"exercised\s*(?:during|in)\s*(?:the\s*)?(?:year|period)",
    r"vested\s*(?:during|in)\s*(?:the\s*)?(?:year|period)",
    r"settled\s*(?:during|in)\s*(?:the\s*)?(?:year|period)",

    # Exercisable
    r"exercisable\s*(?:at|as\s*at)\s*(?:the\s*)?(?:beginning|end|year[\s\-]*end)",
    r"vested\s*and\s*exercisable",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 5: SECTION HEADER PATTERNS (require numeric table)
# Generic section headings that need a numeric table to qualify.
# ─────────────────────────────────────────────────────────────────────────
SECTION_HEADERS = [
    r"share[\s\-]*based\s*payment",
    r"share[\s\-]*based\s*compensation",
    r"equity[\s\-]*based\s*compensation",
    r"stock[\s\-]*based\s*compensation",
    r"employee\s*share\s*(?:plans?|schemes?)",
    r"equity\s*(?:plans?|instruments?|compensation|incentive)",
    r"share\s*incentive\s*(?:plans?|schemes?)",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 6: NOTE TITLE PATTERNS (strongest signal)
# Matches actual note headers like "23. Share-based payments"
# A single match qualifies the page.
# ─────────────────────────────────────────────────────────────────────────
NOTE_TITLE_PATTERNS = [
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+share[\s\-]*based\s*(?:payment|compensation|remuneration)",
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+(?:employee\s*)?(?:share|stock)\s*(?:option|plan|scheme|award)",
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+(?:share|equity|stock)[\s\-]*(?:based|incentive|compensation)",
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+share[\s\-]*based\s*payment\s*arrangement",
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+(?:long[\s\-]*term\s*)?incentive\s*(?:plan|award|scheme)",
    r"(?:^|\n)\s*(?:note\s*)?\d+[\.\:\)\s]+restricted\s*(?:share|stock)\s*(?:plan|award|unit)",
]

# ─────────────────────────────────────────────────────────────────────────
# TIER 7: NON-ENGLISH KEYWORDS
# International support — match against raw text (case-sensitive for some).
# ─────────────────────────────────────────────────────────────────────────
NON_ENGLISH_KEYWORDS = [
    # German
    r"aktienoptionen",
    r"aktienoptionsplan",
    r"aktienbasiert[en]?\s*verg(?:ü|ue)tung",
    r"mitarbeiterbeteiligung(?:sprogramm)?",
    r"aktienzusagen",
    r"performanceaktien",

    # French
    r"options?\s*(?:de|sur)\s*actions?",
    r"actions?\s*gratuites?",
    r"actions?\s*de\s*performance",
    r"r[ée]mun[ée]ration\s*(?:en|fond[ée]e\s*sur)\s*actions?",
    r"plan\s*d['']?attribution\s*d['']?actions?",
    r"plan\s*d['']?options?",

    # Spanish
    r"opciones\s*sobre\s*acciones",
    r"acciones\s*restringidas",
    r"plan\s*de\s*incentivos\s*a\s*largo\s*plazo",
    r"retribuci[óo]n\s*(?:en|basada\s*en)\s*acciones",

    # Italian
    r"piani\s*di\s*stock\s*option",
    r"compensi\s*basati\s*su\s*azioni",

    # Chinese (Simplified & Traditional)
    r"股票期权",
    r"股權激勵",
    r"股权激励",
    r"限制性股票",
    r"限制性股權",
    r"員工持股",
    r"员工持股",

    # Japanese
    r"ストック\s*オプション",
    r"株式報酬",
    r"新株予約権",

    # Korean
    r"주식매수선택권",
    r"성과주식",
]