import json
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from filingkit import judges  # noqa: E402
from filingkit.authorities import Authorities  # noqa: E402
from filingkit.checklist import load_descriptor, run_checklist  # noqa: E402
from filingkit.policy import load_policy  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
SAMPLES = os.path.join(ROOT, "sample_filings")
NOW = "2027-01-12T17:00:00+00:00"


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


@pytest.fixture
def ctx():
    return {"judge_orders": judges.load_orders(), "policy": load_policy(), "authorities": Authorities()}


@pytest.fixture
def filing(tmp_path):
    """Copy a sample filing into a temp folder. Returns a helper with edit and check methods."""

    class Filing:
        def __init__(self, fid):
            self.dir = str(tmp_path / fid)
            shutil.copytree(os.path.join(SAMPLES, fid), self.dir)
            self.path = os.path.join(self.dir, "filing.json")

        def file(self, name):
            return os.path.join(self.dir, name)

        def edit(self, name, fn):
            obj = read_json(self.file(name))
            fn(obj)
            save_json(self.file(name), obj)

        def check(self, ctx, now=NOW, **policy_overrides):
            desc, base = load_descriptor(self.path)
            c = dict(ctx)
            if policy_overrides:
                c["policy"] = load_policy(overrides=policy_overrides)
            return run_checklist(desc, base, now=now, **c)

    return Filing


def item(result, id_):
    return next(i for i in result["items"] if i["id"] == id_)


@pytest.fixture
def brief_filing(tmp_path):
    """A filing built from the existing checker's own sample brief and real report (17 citations)."""

    def make(report_name="citecheck_report.sample.json", attest=True):
        d = tmp_path / "brief"
        d.mkdir(exist_ok=True)
        shutil.copy(os.path.join(FIX, "citecheck_sample_brief.txt"), d / "document.txt")
        shutil.copy(os.path.join(FIX, report_name), d / "citation_report.json")
        report = read_json(os.path.join(FIX, "citecheck_report.sample.json"))
        desc = {"filing_id": "F-TEST", "matter": {"number": "M-1", "client": "Test client (fictional)"},
                "court_id": "fict-alder-ridge", "judge_id": "fict-quillon",
                "document": {"path": "document.txt", "type": "opposition"},
                "responsible_attorney": {"name": "Fictional Counsel"}, "genai": {"used": False},
                "citation_report": "citation_report.json"}
        if attest:
            atts = [{"citation_id": c["id"], "attorney": "Fictional Counsel", "attested_at": "2027-01-12T10:00:00+00:00",
                     "how_checked": "Read the source and compared it with the brief.",
                     "resolution": "Checked the flag by hand against the official source."}
                    for c in report["citations"]]
            save_json(d / "attestations.json", {"doc_sha256": report["doc_sha256"], "attestations": atts})
            desc["attestations"] = "attestations.json"
        save_json(d / "filing.json", desc)
        return str(d / "filing.json")

    return make
