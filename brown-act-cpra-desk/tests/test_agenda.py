import copy
import json
from pathlib import Path

from desk import agenda

S = Path(__file__).resolve().parent.parent / "sample_data"
load = lambda n: json.loads((S / f"agenda_{n}.json").read_text(encoding="utf-8"))
codes = lambda fs, level: {f["code"] for f in fs if f["level"] == level}


def test_clean_agenda_has_no_fail_or_review():
    r = agenda.validate(load("clean"))
    assert r["counts"]["fail"] == 0 and r["counts"]["review"] == 0


def test_72_hour_boundary():
    a = load("clean")
    a["posting"]["website_posted_at"] = "2027-01-23T18:00"  # exactly 72h
    assert "regular_agenda" not in codes(agenda.check_clocks(a), "fail")
    a["posting"]["website_posted_at"] = "2027-01-23T18:01"
    assert "regular_agenda" in codes(agenda.check_clocks(a), "fail")


def test_no_website_skips_website_clock():
    a = load("clean")
    a["posting"] = {"has_website": False, "physical_posted_at": "2027-01-22T15:00"}
    assert not codes(agenda.check_clocks(a), "fail")


def test_special_meeting_24_hours_and_waiver():
    a = load("special")
    assert "special_notice" in codes(agenda.check_clocks(a), "fail")
    a["posting"]["member_waivers_filed"] = True
    assert "special_notice" not in codes(agenda.check_clocks(a), "fail")


def test_emergency_one_hour_media_notice():
    a = load("clean")
    a["meeting"]["type"] = "emergency"
    a["posting"] = {"media_requested_notice": True, "media_notified_at": "2027-01-26T17:30"}
    assert "emergency_media" in codes(agenda.check_clocks(a), "fail")
    a["posting"]["media_notified_at"] = "2027-01-26T17:00"
    assert "emergency_media" in codes(agenda.check_clocks(a), "pass")


def test_quorum_majority_of_seats():
    assert [agenda.quorum_needed(n) for n in (3, 5, 7, 9, 4)] == [2, 3, 4, 5, 3]


def test_ada_member_counts_toward_in_person_quorum_for_just_cause():
    a = load("clean")  # 4 in person + 1 ADA + 1 just cause
    a["attendance"][0]["mode"] = "absent"  # 3 in person + 1 ADA = 4 of 7
    assert "jc_inperson_quorum" in codes(agenda.check_quorum(a), "pass")
    a["attendance"][1]["mode"] = "absent"  # 2 + 1 = 3
    assert "jc_inperson_quorum" in codes(agenda.check_quorum(a), "fail")


def test_just_cause_caps_by_meeting_frequency():
    assert [agenda.just_cause_cap(m) for m in (0.5, 1, 2, 3, 4)] == [2, 2, 5, 7, 7]
    a = load("clean")
    pell = next(x for x in a["attendance"] if x["mode"] == "just_cause")
    pell["just_cause_uses_this_year"] = 5
    assert "jc_cap" in codes(agenda.check_quorum(a), "fail")


def test_just_cause_sunset_and_audio_video():
    a = load("clean")
    a["meeting"]["start"] = "2030-01-08T18:00"
    a["posting"] = {"has_website": False, "physical_posted_at": "2030-01-02T18:00"}
    assert "jc_sunset" in codes(agenda.check_quorum(a), "fail")
    b = load("clean")
    next(x for x in b["attendance"] if x["mode"] == "just_cause")["audio_visual"] = False
    assert "jc_av" in codes(agenda.check_quorum(b), "fail")


def test_ada_audio_only_needs_recorded_need():
    a = load("clean")
    m = next(x for x in a["attendance"] if x["mode"] == "ada_remote")
    m["audio_visual"] = False
    assert "ada_av" in codes(agenda.check_quorum(a), "fail")
    m["audio_only_disability_need"] = True
    assert "ada_av" not in codes(agenda.check_quorum(a), "fail")


def test_traditional_teleconference_needs_quorum_inside_territory():
    a = load("clean")
    a["attendance"] = [{"member": f"M{i}", "mode": "in_person"} for i in range(2)] + [
        {"member": f"T{i}", "mode": "teleconf_posted", "location_on_agenda": True, "location_public": True,
         "agenda_posted_at_location": True, "location_in_jurisdiction": False} for i in range(3)]
    assert "teleconf_jurisdiction_quorum" in codes(agenda.check_quorum(a), "fail")
    for x in a["attendance"][2:4]:
        x["location_in_jurisdiction"] = True
    assert "teleconf_jurisdiction_quorum" in codes(agenda.check_quorum(a), "pass")


def test_alt_track_needs_public_remote_access():
    a = load("clean")
    a["meeting"]["public_remote_access"] = "phone_only"
    assert "alt_public_access" in codes(agenda.check_quorum(a), "fail")


def test_closed_session_forms():
    ok = {"no": "1", "section": "closed", "authority": "Gov. Code § 54956.8",
          "text": "CONFERENCE WITH REAL PROPERTY NEGOTIATORS\nProperty: APN 1\nAgency negotiator: A\nNegotiating parties: B\nUnder negotiation: Price"}
    assert codes(agenda.check_closed_item(ok), "pass") == {"closed_ok"}
    bad = copy.deepcopy(ok)
    bad["text"] = bad["text"].replace("\nNegotiating parties: B", "")
    assert "closed_fields" in codes(agenda.check_closed_item(bad), "fail")
    vague = copy.deepcopy(ok)
    vague["text"] = vague["text"].replace("Price", "All matters")
    assert "closed_field_value" in codes(agenda.check_closed_item(vague), "review")


def test_cyber_item_uses_existing_threat_form():
    it = {"no": "8", "section": "closed", "authority": "54957(a)", "title": "Cybersecurity",
          "text": "THREAT TO PUBLIC SERVICES OR FACILITIES\nConsultation with: Security Operations Manager"}
    fs = agenda.check_closed_item(it)
    assert "closed_ok" in codes(fs, "pass") and "closed_cyber" in codes(fs, "info")
    it["text"] = "CYBERSECURITY BRIEFING\nRansomware discussion"
    assert "closed_label" in codes(agenda.check_closed_item(it), "review")


def test_authority_matching_does_not_confuse_54957_with_54957_6():
    it = {"no": "2", "section": "closed", "authority": "54957", "text": "PUBLIC EMPLOYEE PERFORMANCE EVALUATION\nTitle: General Manager"}
    assert codes(agenda.check_closed_item(it), "pass") == {"closed_ok"}
    lab = {"no": "3", "section": "closed", "authority": "54957.6",
           "text": "CONFERENCE WITH LABOR NEGOTIATORS\nAgency designated representatives: A\nUnrepresented employee: General Manager"}
    assert codes(agenda.check_closed_item(lab), "pass") == {"closed_ok"}


def test_anticipated_litigation_needs_number():
    it = {"no": "4", "section": "closed", "authority": "54956.9(d)(4)",
          "text": "CONFERENCE WITH LEGAL COUNSEL—ANTICIPATED LITIGATION\nInitiation of litigation pursuant to paragraph (4) of subdivision (d) of Section 54956.9: two potential cases"}
    assert "closed_ok" in codes(agenda.check_closed_item(it), "pass")
    it["text"] = it["text"].replace("two potential cases", "to be discussed")
    assert "closed_number" in codes(agenda.check_closed_item(it), "review")


def test_unknown_authority_is_review_not_pass():
    it = {"no": "5", "section": "closed", "authority": "54956.75", "text": "AUDIT BY CALIFORNIA STATE AUDITOR'S OFFICE"}
    assert codes(agenda.check_closed_item(it), "review") == {"closed_no_form"}


def test_agenda_creep_and_length():
    it = {"no": "4", "description": "Discussion of the water rate study.",
          "staff_report": "Staff recommends that the Board adopt Resolution 1 to increase rates."}
    assert "creep_action" in codes(agenda.check_open_item(it), "fail")
    it["description"] = "Adopt resolution to increase water rates 9 percent."
    assert "creep_action" not in codes(agenda.check_open_item(it), "fail") | codes(agenda.check_open_item(it), "review")
    long = {"no": "5", "description": " ".join(["word"] * 25)}
    assert "desc_long" in codes(agenda.check_open_item(long), "info")  # over 20 words is allowed


def test_special_meeting_pay_bar_has_budget_exception():
    it = {"no": "1", "description": "Approve amendment increasing the General Manager's salary."}
    assert "special_pay" in codes(agenda.check_open_item(it, "special"), "fail")
    assert "special_pay" not in codes(agenda.check_open_item(it, "regular"), "fail")
    it["description"] = "Adopt the budget including General Manager salary line."
    assert "special_pay" not in codes(agenda.check_open_item(it, "special"), "fail")


def test_sample_regular_agenda_expected_failures():
    r = agenda.validate(load("regular"))
    fails = {f["code"] for v in r["sections"].values() for f in v if f["level"] == "fail"}
    assert fails == {"regular_agenda", "teleconf_agenda_posted_at_location", "creep_action", "closed_fields"}
