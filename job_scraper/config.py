"""Central configuration for the job scraper."""

import os
from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "jobs.db"
OUTPUT_DIR = PROJECT_ROOT / "output"

# --- Geographic scope ---
ROMANDIE_CANTONS = {"GE", "VD", "VS", "NE", "JU", "FR"}

ROMANDIE_CITIES = {
    "Geneva": "GE",
    "Lausanne": "VD",
    "Sion": "VS",
    "Neuchatel": "NE",
    "Neuchâtel": "NE",
    "Fribourg": "FR",
    "Yverdon": "VD",
    "Yverdon-les-Bains": "VD",
    "Montreux": "VD",
    "Nyon": "VD",
    "Morges": "VD",
    "Vevey": "VD",
    "Renens": "VD",
    "Prilly": "VD",
    "Bienne": "BE",
    "Biel": "BE",
    "Delémont": "JU",
    "Sierre": "VS",
    "Martigny": "VS",
    "Monthey": "VS",
}

# --- Target keywords (per discipline) ---
TARGET_KEYWORDS = {
    "process": [
        "process engineer",
        "process engineering",
        "chemical engineer",
        "manufacturing engineer",
    ],
    "automation": [
        "automation engineer",
        "automation engineering",
        "control engineer",
        "control systems",
        "instrumentation engineer",
        "PLC",
        "SCADA",
        "DCS",
    ],
    "energy": [
        "energy engineer",
        "energy engineering",
        "power engineer",
        "power systems",
        "renewable energy",
        "electrical engineer",
    ],
}

# --- Filter patterns ---
LANGUAGE_EXCLUDE_PATTERNS = [
    r"(?i)\bfrançais\b",
    r"(?i)\bfrancais\b",
    r"(?i)\bfrench\s*(:|required|fluent|native|courant|mandatory)",
    r"(?i)\bgerman\s*(:|required|fluent|native|mandatory)",
    r"(?i)\bdeutsch\b",
    r"(?i)\ballemand\b",
    r"(?i)\bmuttersprache\b",
    r"(?i)\blangue\s+maternelle\b",
    r"(?i)\bcourant\s+requis\b",
]

ENTRY_LEVEL_PATTERNS = [
    r"(?i)\bentry[- ]level\b",
    r"(?i)\bjunior\b",
    r"(?i)\bgraduate\b",
    r"(?i)\brecent graduate\b",
    r"(?i)\btrainee\b",
    r"(?i)\bintern(?:ship)?\b",
    r"(?i)\b0[- ]?2\s*years?\b",
    r"(?i)\b1[- ]?2\s*years?\b",
    r"(?i)\b0[- ]?1\s*years?\b",
]

SENIOR_EXCLUDE_PATTERNS = [
    r"(?i)\bsenior\b",
    r"(?i)\blead\b",
    r"(?i)\bprincipal\b",
    r"(?i)\bmanager\b",
    r"(?i)\bdirector\b",
    r"(?i)\b[5-9]\+?\s*years?\b",
    r"(?i)\b\d{2}\+?\s*years?\b",
]

ENROLLMENT_EXCLUDE_PATTERNS = [
    r"(?i)\bcurrently\s+enrolled\b",
    r"(?i)\bmust\s+be\s+enrolled\b",
    r"(?i)\bactive\s+student\b",
    r"(?i)\bregistered\s+student\b",
    r"(?i)\benrolled\s+in\s+a\s+(university|master|bachelor|degree)\b",
]

# --- HTTP settings ---
REQUEST_DELAY_SECONDS = 2

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# --- LLM settings ---
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
LLM_DESCRIPTION_MAX_CHARS = 2000

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "scraper.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3
