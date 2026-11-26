import json
import os
import shutil

import pytest

from conftest import AS_OF, rfp_text
from desk.harvest import harvest, parse_final_markdown, set_outcome, tag_text
from desk.loader import load_data
from desk.pipeline import build

RFP = "general_counsel_redwood_flats"


@pytest.fixture()
def lib(tmp_path, root):
    dst = tmp_path / "library"
    shutil.copytree(os.path.join(root, "data", "library"), dst)
    return str(dst)


@pytest.fixture()
def final(root):
    with open(os.path.join(root, "data", "harvest_sample", "final_redwood_flats.md"), encoding="utf-8") as f:
        return f.read()


def test_final_markdown_is_split_by_requirement_heading(final):
    heads = [s["heading"] for s in parse_final_markdown(final)]
    assert heads[0] == "A Letter of Transmittal" and len(heads) == 8


def test_harvest_files_answers_unapproved_with_outcome_and_review_date(lib, final):
    rep = harvest(final, rfp_text(RFP), load_data(lib), "pending")
    recs = [x["record"] for x in rep["filed"]]
    assert [r["question_type"] for r in recs] == ["firm_overview", "team", "approach", "transition"]
    for r in recs:
        assert r["approved"] is False and r["approver"] == "" and r["outcome"] == "pending"
        assert r["submitted"] == "2026-12-17" and r["review_by"] == "2028-06-17"
        assert r["proposal_agency"] == "Redwood Flats Water District" and "harvested" in r["tags"]
    on_disk = json.load(open(os.path.join(lib, "harvested_answers.json"), encoding="utf-8"))
    assert [r["id"] for r in on_disk] == [r["id"] for r in recs]


def test_harvest_never_files_conflicts_pricing_or_open_gaps(lib, final):
    rep = harvest(final, rfp_text(RFP), load_data(lib))
    reasons = {s["heading"]: s["reason"] for s in rep["skipped"]}
    assert "conflicts" in reasons["G Potential Conflicts"]
    assert "pricing" in reasons["H Compensation"]
    assert "open gap" in reasons["F Client References"]
    assert "cover letters" in reasons["A Letter of Transmittal"]
    assert not any(x["record"]["question_type"] in ("conflicts", "rates") for x in rep["filed"])


def test_harvest_tags_the_agency_so_the_answer_can_be_reused(lib, final):
    rep = harvest(final, rfp_text(RFP), load_data(lib))
    text = next(x["record"]["answer_text"] for x in rep["filed"] if x["record"]["question_type"] == "approach")
    assert "Redwood Flats" not in text and "the District" not in text
    assert text.startswith("We propose to serve {AGENCY} with one lead attorney who attends every regular {GOVERNING_BODY} meeting.")
    assert "{CHIEF_EXEC}" in text and "{AGENCY_SHORT} considers new rates" in text
    assert "[Source:" not in text                                     # internal notes are not filed


def test_harvest_reports_another_agency_name_left_in_the_final_text(lib, final):
    rep = harvest(final, rfp_text(RFP), load_data(lib))
    notes = next(x["notes"] for x in rep["filed"] if x["record"]["question_type"] == "transition")
    assert any("Kettle Bend Irrigation District" in n for n in notes)


def test_tag_text_handles_possessive_and_capitalised_forms():
    meta = {"agency": "Redwood Flats Water District", "agency_short": "District"}
    text, counts = tag_text("The District's files. REDWOOD FLATS WATER DISTRICT's Board of Directors.", meta,
                            "Board of Directors", "General Manager")
    assert text == "{AGENCY_SHORT}'s files. {AGENCY}'s {GOVERNING_BODY}."
    assert counts == {"{AGENCY}": 1, "{AGENCY_SHORT}": 1, "{GOVERNING_BODY}": 1}


def test_harvested_answers_load_and_are_used_only_as_partial_until_approved(lib, final):
    harvest(final, rfp_text(RFP), load_data(lib), "won")
    data = load_data(lib)
    mine = [a for a in data.answers if "harvested" in a["tags"]]
    assert len(mine) == 4 and len(data.answers) == 124
    data.answers = mine                                   # make them the only candidates
    res = build(rfp_text("city_attorney_marlow_ridge"), data, "2027-02-01")
    sec = next(s for s in res["sections"] if s["qtype"] == "approach")
    assert sec["status"] == "partial"
    assert "not approved by the practice lead" in " ".join(sec["notes"])
    passage = next(p for p in sec["parts"] if p["type"] == "passage")
    assert "City of Marlow Ridge" in passage["text"] and "Redwood Flats" not in passage["text"]


def test_outcome_is_recorded_once_known(lib, final):
    rep = harvest(final, rfp_text(RFP), load_data(lib), "pending")
    assert set_outcome(lib, rep["proposal_id"], "won") == 4
    assert {a["outcome"] for a in load_data(lib).answers if "harvested" in a["tags"]} == {"won"}
    assert set_outcome(lib, "P-NOPE", "lost") == 0
    with pytest.raises(ValueError):
        set_outcome(lib, rep["proposal_id"], "maybe")


def test_harvest_twice_does_not_duplicate(lib, final):
    harvest(final, rfp_text(RFP), load_data(lib))
    harvest(final, rfp_text(RFP), load_data(lib))
    assert len(json.load(open(os.path.join(lib, "harvested_answers.json"), encoding="utf-8"))) == 4


def test_cli_harvest_and_set_outcome(lib, final, tmp_path, capsys, root):
    from desk.__main__ import main
    f = tmp_path / "final.md"
    f.write_text(final, encoding="utf-8")
    rfp = os.path.join(root, "data", "rfps", RFP + ".txt")
    assert main(["harvest", str(f), "--rfp", rfp, "--data", lib, "--proposal-id", "P-2026-77"]) == 0
    assert "## Filed: 4" in capsys.readouterr().out
    assert main(["harvest", "--set-outcome", "P-2026-77", "lost", "--data", lib]) == 0
    assert main(["harvest", "--set-outcome", "P-0000-00", "lost", "--data", lib]) == 1


def test_run_demo_does_not_change_the_demo_library(root):
    assert not os.path.exists(os.path.join(root, "data", "library", "harvested_answers.json"))
