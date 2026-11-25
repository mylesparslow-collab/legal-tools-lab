"""Matter clearance for AI. Personal portfolio demo. Fictional data. Not legal advice."""
from pathlib import Path

__version__ = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DECISIONS = ["ALLOWED", "ALLOWED_WITH_CONDITIONS", "HOLD_FOR_REVIEW", "NOT_ALLOWED"]
DECISION_LABELS = {
    "ALLOWED": "ALLOWED",
    "ALLOWED_WITH_CONDITIONS": "ALLOWED WITH CONDITIONS",
    "HOLD_FOR_REVIEW": "HOLD FOR REVIEW",
    "NOT_ALLOWED": "NOT ALLOWED",
}
