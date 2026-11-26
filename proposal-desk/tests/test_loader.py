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
    assert errs == [] and recs[0]["consent_to_name_client"] is False and recs[0]["end_year"] is None
    assert recs[0]["subjects"] == [] and recs[0]["anonymized_description"] == ""


def test_csv_export_with_the_firms_own_column_names(tmp_path):
    p = tmp_path / "matters.csv"
    p.write_text("Matter No,Client,OK to name?,Blurb,Kind,Group,Topics,Opened,Closed\n"
                 "M-1,Tallowfield Water District,Yes,a water district,special_district,general_counsel,water; governance,2019,\n"
                 "M-2,Mossgate Harbor District,ask partner,,special_district,general_counsel,,2015,2021\n"
                 "M-3,,Yes,,special_district,general_counsel,,2015,\n"
                 "M-4,Fogbank Water District,Yes,,special_district,general_counsel,,twenty,\n", encoding="utf-8")
    spec = {"fields": {"id": "Matter No", "client_name": "Client", "consent_to_name_client": "OK to name?",
                       "anonymized_description": "Blurb", "agency_type": "Kind", "practice": "Group",
                       "subjects": "Topics", "start_year": "Opened", "end_year": "Closed"}}
    recs, errs = map_records(read_rows(str(p)), "experience", spec)
    assert [r["id"] for r in recs] == ["M-1", "M-2"]
    assert recs[0]["consent_to_name_client"] is True and recs[0]["subjects"] == ["water", "governance"]
    assert recs[1]["consent_to_name_client"] is False and recs[1]["end_year"] == 2021
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


def test_schemas_have_two_separately_named_consent_fields_defaulting_to_false():
    from desk.schemas import CONSENT_FIELDS
    assert set(SCHEMAS) == {"past_answers", "experience", "bios", "rate_schedules", "references", "standard_forms"}
    assert CONSENT_FIELDS == {"experience": "consent_to_name_client", "references": "consent_to_list_contact"}
    names = {name: [f[0] for f in SCHEMAS[name]] for name in SCHEMAS}
    assert "consent_to_list_contact" not in names["experience"] and "consent_to_name_client" not in names["references"]
    assert not any("client_consent" in fields for fields in names.values())
    for name, field in CONSENT_FIELDS.items():
        spec = next(f for f in SCHEMAS[name] if f[0] == field)
        assert spec[1] == "bool" and spec[3] is False


def test_reference_without_a_consent_column_loads_as_no_consent():
    rows = [{"id": "R1", "client_name": "X District", "contact_name": "A B"}]
    recs, errs = map_records(rows, "references")
    assert errs == [] and recs[0]["consent_to_list_contact"] is False


def test_old_single_consent_column_is_not_read_and_is_reported():
    from desk.loader import consent_warnings
    exp = [{"id": "E1", "client_name": "X District", "agency_type": "city", "practice": "general_counsel",
            "start_year": 2020, "client_consent": True}]
    refs = [{"id": "R1", "client_name": "X District", "contact_name": "A B", "client_consent": "yes"}]
    assert map_records(exp, "experience")[0][0]["consent_to_name_client"] is False
    assert map_records(refs, "references")[0][0]["consent_to_list_contact"] is False
    w = consent_warnings(exp, "experience") + consent_warnings(refs, "references")
    assert len(w) == 2 and all("client_consent" in x and "no longer read" in x for x in w)
    # an explicit mapping is the only way the old column counts, and only for the permission it is mapped to
    spec = {"fields": {"consent_to_name_client": "client_consent"}}
    assert map_records(exp, "experience", spec)[0][0]["consent_to_name_client"] is True
    assert consent_warnings(exp, "experience", spec) == []
    assert consent_warnings([{"id": "B1"}], "bios") == []


def test_demo_library_has_both_consent_columns_and_no_warnings(data):
    assert data.warnings == []
    assert all(isinstance(e["consent_to_name_client"], bool) for e in data.experience)
    assert all(isinstance(r["consent_to_list_contact"], bool) for r in data.references)
    assert any(r["consent_to_list_contact"] is False for r in data.references)


def test_check_data_reports_a_missing_consent_column(tmp_path, root, capsys):
    from desk.__main__ import main
    lib = tmp_path / "lib"
    shutil.copytree(os.path.join(root, "data", "library"), lib)
    rows = json.load(open(lib / "references.json", encoding="utf-8"))
    for r in rows:
        r["client_consent"] = r.pop("consent_to_list_contact")
    json.dump(rows, open(lib / "references.json", "w", encoding="utf-8"))
    d = load_data(str(lib))
    assert not any(r["consent_to_list_contact"] for r in d.references)
    main(["check-data", "--data", str(lib)])
    out = capsys.readouterr().out
    assert "WARNING references: no column for consent_to_list_contact" in out
    assert "reference records without consent to list the contact: 30 of 30" in out


def test_generator_is_seeded(tmp_path, root, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", os.path.join(root, "data", "generate_data.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    monkeypatch.setattr(gen, "OUT", str(tmp_path))
    gen.main()
    for f in ("past_answers.json", "experience.json", "references.json", "bios.json", "firm_facts.json"):
        assert open(tmp_path / f, encoding="utf-8").read() == open(os.path.join(root, "data", "library", f), encoding="utf-8").read()
