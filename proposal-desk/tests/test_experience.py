import datetime as dt

from conftest import AS_OF, RFPS
from desk.experience import (check_min_quals, display_experience, match_experience, select_references, select_team)

META = {"agency": "X", "agency_type": "special_district", "practice": "general_counsel", "subjects": ["water", "governance"]}


def rec(**kw):
    base = {"id": "E-1", "client_name": "Secretive Water District", "client_consent": False,
            "anonymized_description": "a water district in the foothills", "agency_type": "special_district",
            "practice": "general_counsel", "subjects": ["water"], "role": "general counsel", "start_year": 2019,
            "end_year": None, "summary": "Served Secretive Water District as general counsel.", "lead_attorney_id": "B1"}
    base.update(kw)
    return base


def test_client_is_named_only_with_consent():
    shown = display_experience(rec(client_consent=True))
    assert shown["mode"] == "named" and "Secretive Water District" in shown["text"]


def test_without_consent_the_anonymized_description_is_printed_and_nothing_else_names_the_client():
    shown = display_experience(rec())
    assert shown["mode"] == "anonymized"
    assert shown["text"].startswith("A water district in the foothills")
    assert "Secretive" not in shown["text"]            # the summary names the client, so it is not printed


def test_without_consent_and_without_description_the_record_is_omitted():
    shown = display_experience(rec(anonymized_description="  "))
    assert shown == {"mode": "omitted", "name": None, "text": None}


def test_consent_must_be_exactly_true():
    for value in ("yes", "true", 1, None, "pending"):
        assert display_experience(rec(client_consent=value))["mode"] != "named"


def test_omitted_records_are_reported_not_printed():
    recs = [rec(id="E-1", anonymized_description=""), rec(id="E-2", client_consent=True), rec(id="E-3")]
    out = match_experience(META, recs, AS_OF)
    assert [s["record"]["id"] for s in out["selected"]] == ["E-2", "E-3"]
    assert [s["record"]["id"] for s in out["omitted"]] == ["E-1"]
    assert "no client consent" in out["omitted"][0]["reasons"][-1]


def test_match_reasons_cover_agency_type_subject_recency_and_role():
    out = match_experience(META, [rec(), rec(id="E-2", agency_type="city", practice="labor", subjects=[],
                                              role="chief negotiator", end_year=2012)], AS_OF)
    best, worst = out["selected"]
    assert best["record"]["id"] == "E-1" and best["score"] > worst["score"]
    joined = "; ".join(best["reasons"])
    for word in ("same agency type", "same practice", "shared subjects: water", "ongoing", "same role"):
        assert word in joined
    assert "ended 2012 (older)" in worst["reasons"]


def test_no_draft_output_names_a_client_without_consent(built, data):
    from desk import render
    hidden = [e["client_name"] for e in data.experience if not e["client_consent"]]
    named_ok = {e["client_name"] for e in data.experience if e["client_consent"]}
    hidden = [h for h in hidden if h not in named_ok]
    assert len(hidden) >= 20
    for name in RFPS:
        for text in (render.draft_markdown(built[name]), render.draft_html(built[name]),
                     render.matrix_csv(built[name]), render.go_no_go_markdown(built[name]),
                     render.match_markdown(built[name])):
            for h in hidden:
                assert h not in text, (name, h)
        assert built[name]["go_no_go"]["consent_flags"] == []


def test_samples_use_both_named_and_anonymized_records(built):
    modes = {it["mode"] for name in RFPS for s in built[name]["sections"] for p in s["parts"]
             if p["type"] == "experience" for it in p["items"]}
    assert modes == {"named", "anonymized"}


def test_departed_attorney_is_never_proposed(data):
    meta = {"agency_type": "school_district", "practice": "labor", "subjects": ["collective bargaining", "schools"]}
    team = select_team(meta, data.bios, AS_OF)
    names = [m["bio"]["name"] for m in team["members"]]
    assert "Corwin Halloway" not in names and "Corwin Halloway" in team["excluded_departed"]
    assert team["lead"]["bio"]["title"] in ("Partner", "Of Counsel")
    assert all(m["reasons"] for m in team["members"])


def test_team_roles_lead_backup_members(data):
    meta = {"agency_type": "transit", "practice": "capital_projects", "subjects": ["construction", "claims"]}
    team = select_team(meta, data.bios, AS_OF)
    assert [m["role"] for m in team["members"]][:2] == ["Lead attorney", "Backup attorney"]
    assert all("capital_projects" in m["bio"]["practices"] for m in team["members"])


def _team(admit_year):
    return {"lead": {"bio": {"name": "Test Lead", "admit_year": admit_year}}, "members": []}


FACTS = {"attorney_count": 46, "offices": [{"city": "Alder Bay", "county": "Larkspur County"}]}


def q(kind, value, text="text"):
    return {"id": "MQ-1", "label": "1", "text": text, "check_kind": kind, "value": value}


def test_years_admitted_met_and_not_met():
    assert check_min_quals([q("years_admitted", 10)], _team(2010), FACTS, AS_OF)[0]["status"] == "met"
    res = check_min_quals([q("years_admitted", 10)], _team(2019), FACTS, AS_OF)[0]
    assert res["status"] == "not_met" and "7 years against 10" in res["detail"]


def test_years_admitted_without_bio_data_is_not_checkable():
    assert check_min_quals([q("years_admitted", 10)], _team(None), FACTS, AS_OF)[0]["status"] == "not_checkable"
    assert check_min_quals([q("years_admitted", 10)], {"lead": None, "members": []}, FACTS, AS_OF)[0]["status"] == "not_met"


def test_office_location_checked_against_city_and_county():
    assert check_min_quals([q("office_location", "Larkspur County")], _team(2000), FACTS, AS_OF)[0]["status"] == "met"
    assert check_min_quals([q("office_location", "alder bay")], _team(2000), FACTS, AS_OF)[0]["status"] == "met"
    assert check_min_quals([q("office_location", "Hadley County")], _team(2000), FACTS, AS_OF)[0]["status"] == "not_met"


def test_other_qualifications_are_flagged_for_a_person():
    res = check_min_quals([q("not_checkable", None)], _team(2000), FACTS, AS_OF)[0]
    assert res["status"] == "not_checkable" and "a person must confirm" in res["detail"]


def test_min_qual_failure_shows_in_matrix_and_go_no_go(data):
    import copy
    from conftest import rfp_text
    from desk.pipeline import build
    d = copy.copy(data)
    d.bios = [dict(b, admit_year=2022) for b in data.bios]
    res = build(rfp_text("special_counsel_tannery_creek_transit"), d, AS_OF)
    row = next(r for r in res["matrix"] if r["id"] == "MQ-C.1.1")
    assert row["status"] == "failed" and row in res["disqualifiers"]
    assert res["go_no_go"]["min_quals"]["not_met"] == 1
    assert next(s for s in res["sections"] if s["qtype"] == "team")["status"] == "partial"


def test_references_need_consent_and_old_confirmations_are_marked(data):
    meta = {"agency_type": "special_district", "practice": "general_counsel"}
    out = select_references(meta, data.references, AS_OF, needed=4)
    assert all(s["record"]["client_consent"] is True for s in out["selected"])
    assert out["withheld_count"] > 0
    refs = [{"id": "R1", "client_consent": True, "practice": "general_counsel", "agency_type": "city",
             "last_confirmed": "2024-01-01"},
            {"id": "R2", "client_consent": True, "practice": "general_counsel", "agency_type": "special_district",
             "last_confirmed": "2026-10-01"},
            {"id": "R3", "client_consent": False, "practice": "general_counsel", "agency_type": "special_district",
             "last_confirmed": "2026-10-01"}]
    out = select_references(meta, refs, AS_OF, needed=3)
    assert [(s["record"]["id"], s["stale"]) for s in out["selected"]] == [("R2", False), ("R1", True)]
    assert out["withheld_ids"] == ["R3"]


def test_synthetic_records_have_the_planned_shape(data):
    assert len(data.experience) == 60 and len(data.bios) == 25
    assert sum(1 for b in data.bios if b["status"] == "departed") == 1
    assert 15 <= sum(1 for e in data.experience if not e["client_consent"]) <= 45
    assert any(not e["client_consent"] and not e["anonymized_description"] for e in data.experience)
