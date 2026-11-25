import json
import os
import shutil

import pytest

from desk.loader import load_data, map_records, read_rows, to_bool
from desk.schemas import SCHEMAS


def test_demo_library_loads_with_no_rejected_records(data):
    assert data.errors == []
    assert data.facts["firm_name"] == "Example Firm LLP" and data.facts["as_of"]


def test_consent_is_false_unless_explicitly_yes():
    for v in (True, "true", "Yes", " Y ", "1", 1):
        assert to_bool(v) is True
    for v in (False, None, "", "no", "pending", "ask partner", "0", 0, 2, "n/a"):
        assert to_bool(v) is False


def test_missing_consent_column_defaults_to_false():
    rows = [{"id": "E1", "client_name": "X District", "agency_type": "special_district",
             "practice": "general_counsel", "start_year": "2020"}]
    recs, errs = map_records(rows, "experience")
    assert errs == [] and recs[0]["client_consent"] is False and recs[0]["end_year"] is None
    assert recs[0]["subjects"] == [] and recs[0]["anonymized_description"] == ""


def test_csv_export_with_the_firms_own_column_names(tmp_path):
    p = tmp_path / "matters.csv"
    p.write_text("Matter No,Client,OK to name?,Blurb,Kind,Group,Topics,Opened,Closed\n"
                 "M-1,Tallowfield Water District,Yes,a water district,special_district,general_counsel,water; governance,2019,\n"
                 "M-2,Mossgate Harbor District,ask partner,,special_district,general_counsel,,2015,2021\n"
                 "M-3,,Yes,,special_district,general_counsel,,2015,\n"
                 "M-4,Fogbank Water District,Yes,,special_district,general_counsel,,twenty,\n", encoding="utf-8")
    spec = {"fields": {"id": "Matter No", "client_name": "Client", "client_consent": "OK to name?",
                       "anonymized_description": "Blurb", "agency_type": "Kind", "practice": "Group",
                       "subjects": "Topics", "start_year": "Opened", "end_year": "Closed"}}
    recs, errs = map_records(read_rows(str(p)), "experience", spec)
    assert [r["id"] for r in recs] == ["M-1", "M-2"]
    assert recs[0]["client_consent"] is True and recs[0]["subjects"] == ["water", "governance"]
    assert recs[1]["client_consent"] is False and recs[1]["end_year"] == 2021
    assert [e["id"] for e in errs] == ["M-3", "M-4"]
    assert "client_name: required field is missing" in errs[0]["problems"]
    assert "start_year" in errs[1]["problems"][0]


def test_date_format_defaults_and_duplicate_ids():
    rows = [{"ref": "A1", "prop": "P1", "agency": "X", "sub": "03/14/2025", "qt": "approach", "text": "Words here.",
             "review": "03/14/2027"},
            {"ref": "A1", "prop": "P1", "agency": "X", "sub": "03/14/2025", "qt": "approach", "text": "Again.",
             "review": "03/14/2027"},
            {"ref": "A2", "prop": "P1", "agency": "X", "sub": "2025-03-14", "qt": "approach", "text": "Bad date.",
             "review": "03/14/2027"}]
    spec = {"fields": {"id": "ref", "proposal_id": "prop", "proposal_agency": "agency", "submitted": "sub",
                       "question_type": "qt", "answer_text": "text", "review_by": "review"},
            "date_format": "%m/%d/%Y", "defaults": {"agency_type": "city", "practice": "general_counsel"}}
    recs, errs = map_records(rows, "past_answers", spec)
    assert len(recs) == 1 and recs[0]["submitted"] == "2025-03-14" and recs[0]["review_by"] == "2027-03-14"
    assert recs[0]["approved"] is False and recs[0]["outcome"] == "pending" and recs[0]["agency_type"] == "city"
    assert any("duplicate id" in p for p in errs[0]["problems"])
    assert any("submitted" in p for p in errs[1]["problems"])


def test_answer_without_a_review_date_is_rejected():
    rows = [{"id": "A1", "proposal_id": "P1", "proposal_agency": "X", "agency_type": "city",
             "practice": "general_counsel", "submitted": "2025-01-01", "question_type": "approach",
             "answer_text": "Words."}]
    recs, errs = map_records(rows, "past_answers")
    assert recs == [] and "review_by: required field is missing" in errs[0]["problems"]


def test_whole_library_can_be_loaded_through_a_custom_mapping(tmp_path, root):
    lib = tmp_path / "lib"
    shutil.copytree(os.path.join(root, "data", "library"), lib)
    rows = json.load(open(lib / "bios.json", encoding="utf-8"))
    renamed = [{"Person": r["name"], "Key": r["id"], "Rank": r["title"], "State": r["status"],
                "Bar year": r["admit_year"], "Where": r["office"], "Groups": "|".join(r["practices"]),
                "Clients": "|".join(r["agency_types"]), "Topics": "|".join(r["subjects"]),
                "Roles": "|".join(r["roles"]), "Blurb": r["bio_text"]} for r in rows]
    json.dump(renamed, open(lib / "people_export.json", "w", encoding="utf-8"))
    mapping = json.load(open(lib / "mapping.json", encoding="utf-8"))
    mapping["bios"] = {"file": "people_export.json", "list_separator": "|",
                       "fields": {"id": "Key", "name": "Person", "title": "Rank", "status": "State",
                                  "admit_year": "Bar year", "office": "Where", "practices": "Groups",
                                  "agency_types": "Clients", "subjects": "Topics", "roles": "Roles", "bio_text": "Blurb"}}
    json.dump(mapping, open(lib / "mapping.json", "w", encoding="utf-8"))
    d = load_data(str(lib))
    assert d.errors == [] and len(d.bios) == 25
    assert d.bio("B03")["practices"] == ["labor"] and d.bio("B06")["status"] == "departed"


def test_firm_facts_must_have_an_as_of_date(tmp_path, root):
    from desk.loader import LoadError
    lib = tmp_path / "lib"
    shutil.copytree(os.path.join(root, "data", "library"), lib)
    facts = json.load(open(lib / "firm_facts.json", encoding="utf-8"))
    del facts["as_of"]
    json.dump(facts, open(lib / "firm_facts.json", "w", encoding="utf-8"))
    with pytest.raises(LoadError):
        load_data(str(lib))


def test_schemas_cover_the_six_record_types_and_consent_defaults_false():
    assert set(SCHEMAS) == {"past_answers", "experience", "bios", "rate_schedules", "references", "standard_forms"}
    for name in ("experience", "references"):
        field = next(f for f in SCHEMAS[name] if f[0] == "client_consent")
        assert field[1] == "bool" and field[3] is False


def test_generator_is_seeded(tmp_path, root, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", os.path.join(root, "data", "generate_data.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", str(tmp_path))
    gen.main()
    for f in ("past_answers.json", "experience.json", "references.json", "bios.json", "firm_facts.json"):
        assert open(tmp_path / f, encoding="utf-8").read() == open(os.path.join(root, "data", "library", f), encoding="utf-8").read()
