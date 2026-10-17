"""
config/settings.py
Application-wide configuration loaded once from environment variables.
Secrets are NEVER stored in the database or logged.
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file when running locally; in production set variables in the OS
load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"

for _d in (UPLOADS_DIR, PROCESSED_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'analyst.db'}")

# ── Security ──────────────────────────────────────────────────────────────────
APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY", "")
if not APP_SECRET_KEY:
    import secrets
    APP_SECRET_KEY = secrets.token_hex(32)

ADMIN_PASSWORD_HASH: str = os.getenv("ADMIN_PASSWORD_HASH", "")
SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1024 * 1024

# ── AI ────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-3.8-flash"

# ── Email ─────────────────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")  # read-only; never logged
SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
ALERT_FROM_NAME: str = os.getenv("ALERT_FROM_NAME", "Data Analyst Agent")

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")

# ── Application ───────────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "production")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Silence noisy third-party loggers
for _noisy in ("httpx", "httpcore", "urllib3", "apscheduler"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# ── Anomaly defaults ──────────────────────────────────────────────────────────
DEFAULT_THRESHOLD_PCT: float = 20.0   # flag if change > ±20 %
DEFAULT_MAD_MULTIPLIER: float = 3.0   # MAD Z-score threshold
MIN_HISTORY_PERIODS: int = 4          # periods needed before running baselines

ALLOWED_EXTENSIONS: set[str] = {".xlsx", ".xls"}
