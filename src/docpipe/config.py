"""Paths, environment and constants."""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parents[1]

PROMPTS_DIR = REPO_ROOT / "prompts"
DATA_DIR = REPO_ROOT / "data"
INVOICES_DIR = DATA_DIR / "invoices"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"
REPORTS_DIR = REPO_ROOT / "reports"
DOCS_DIR = REPO_ROOT / "docs"

DEFAULT_PROMPT = PROMPTS_DIR / "extract_v1.txt"

ALLOWED_CURRENCIES = ("EUR", "USD", "UAH", "GBP")

# Rounding tolerance for monetary cross-checks (2 cents).
MONEY_TOLERANCE = Decimal("0.02")

# Max JSON-repair retries on invalid extraction output.
MAX_RETRIES = 2

# Number of synthetic invoices the generator produces.
N_INVOICES = 30

DEFAULT_MODEL = os.environ.get("LLM_MODEL") or "claude-haiku-4-5-20251001"

# Approximate Anthropic Haiku pricing (USD per 1M tokens); used only for any
# cost estimate. Rounded public list figures, not a billing source of truth.
PRICE_INPUT_PER_MTOK = 1.00
PRICE_OUTPUT_PER_MTOK = 5.00


# Document lifecycle statuses.
class Status:
    PROCESSING = "processing"
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    APPROVED = "approved"  # approved by a human reviewer
    REJECTED = "rejected"  # rejected by a human reviewer


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    return f"sqlite:///{REPO_ROOT / 'docpipe.db'}"


def anthropic_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    return key or None


def default_profile() -> str:
    return os.environ.get("DOCPIPE_PROFILE", "good").strip() or "good"
