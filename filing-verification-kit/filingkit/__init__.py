"""Filing verification kit: pre-filing checklist, verification record and ledger.

Personal portfolio demo. Fictional data. Not legal advice. Not reviewed by an attorney.
Every statutory statement shown by this package comes from data/authorities.json.
"""
import os

__version__ = "0.1.0"
KIT_NAME = "filingkit"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
