"""Central configuration. Everything can be overridden with environment variables or a .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MASTER_DATA_PATH = ROOT / "master_data.json"
EMAIL_DIR = ROOT / "email"
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "po_agent.db"))

ERP_URL = os.getenv("ERP_URL", "http://127.0.0.1:8080")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

# Guard against huge attachments (e.g. a 200-page PDF). Pages beyond this are not sent
# to the LLM and the requisition is flagged so a human checks it.
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "20"))

# Tolerance when comparing a stated total with the sum of the line items.
AMOUNT_TOLERANCE = 0.01
