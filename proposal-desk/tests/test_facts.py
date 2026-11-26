import pytest

from desk import facts as F

CUR = "Redwood Flats Water District"
OTHERS = ["Harlan Springs Fire Protection District", "City of Cinder Falls", "Quarry Hollow Transit District",
          "Redwood Flats Sanitary District", "City of Alder Bay", CUR]


def wrong(text, current=CUR, others=OTHERS, offices=("Alder Bay", "Stonemill")):
    return F.find_wrong_agency(text, current, others, offices)


def levels(flags):
    return [f["level"] for f in flags]


# ---- wrong agency name left in: the essential check

def test_full_name_of_another_agency_is_blocking():
    flags = wrong("We propose to serve Harlan Springs Fire Protection District with one lead attorney.")
    assert levels(flags) == ["blocking"] and "full name" in flags[0]["message"]


@pytest.mark.parametrize("text", [
    "Harlan Springs Fire Protection District's Board meets monthly.",
    "Harlan Springs Fire Protection District’s Board meets monthly.",      # curly apostrophe
    "the City of Cinder Falls' budget",
    "the City of Cinder Falls's budget",
])
def test_possessive_forms_are_caught(text):
    flags = wrong(text)
    assert len(flags) == 1 and flags[0]["level"] == "blocking"


@pytest.mark.parametrize("text", [
    "HARLAN SPRINGS FIRE PROTECTION DISTRICT",                 # heading in capitals
    "harlan springs fire protection district",
    "Harlan Springs Fire\nProtection   District",              # broken across a line
])
def test_case_and_line_breaks_do_not_hide_a_full_name(text):
    assert levels(wrong(text)) == ["blocking"]


@pytest.mark.parametrize("text,match", [
    ("Our work for QHTD on its maintenance facility.", "QHTD"),
    ("We reviewed QHTD's design-build contract.", "QHTD"),
    ("We advised Q.H.T.D. on claims.", "Q.H.T.D."),
    ("We have served HSFPD since 2019.", "HSFPD"),
])
def test_abbreviations_are_caught(text, match):
    flags = wrong(text)
    assert len(flags) == 1 and flags[0]["level"] == "blocking" and "abbreviation" in flags[0]["message"]
    assert flags[0]["match"].startswith(match[:4])


def test_abbreviation_inside_a_longer_word_is_not_a_match():
    assert wrong("The XQHTDX code and the lowercase qhtd are not agency names.") == []


def test_supplied_abbreviation_is_used():
    flags = F.find_wrong_agency("We act for Harlan Fire on labor matters and for HS Fire too.", CUR, OTHERS, (),
                                {"Harlan Springs Fire Protection District": ["HS Fire"]})
    assert any(f["match"] == "HS Fire" for f in flags)


@pytest.mark.parametrize("text", [
    "attends every regular meeting of Cinder Falls' City Council",
    "our work in Harlan Springs was similar",
    "Quarry Hollow's board approved the contract",
])
def test_place_name_alone_is_blocking(text):
    flags = wrong(text)
    assert len(flags) == 1 and flags[0]["level"] == "blocking" and "place name" in flags[0]["message"]


def test_this_rfps_own_agency_name_is_never_flagged():
    text = ("We propose to serve Redwood Flats Water District. Redwood Flats Water District's Board and "
            "REDWOOD FLATS WATER DISTRICT staff will have one lead attorney.")
    assert wrong(text) == []


def test_other_agency_sharing_the_place_name_is_flagged_only_by_its_full_name():
    assert wrong("We also know Redwood Flats well.") == []                      # place is part of this agency's name
    flags = wrong("We serve Redwood Flats Sanitary District.")
    assert levels(flags) == ["blocking"]


def test_place_name_that_is_also_a_firm_office_is_a_warning_not_blocking():
    flags = wrong("Our Alder Bay office is closest.")
    assert levels(flags) == ["warning"]
    assert levels(wrong("We serve the City of Alder Bay.")) == ["blocking"]      # the full name is still blocking


def test_each_agency_is_reported_once_per_form():
    flags = wrong("Harlan Springs Fire Protection District and Harlan Springs Fire Protection District again.")
    assert len(flags) == 1


def test_two_different_agencies_are_both_reported():
    flags = wrong("We served the City of Cinder Falls and QHTD.")
    assert len(flags) == 2


def test_agency_word_that_does_not_fit_this_rfp():
    flags = F.find_wrong_agency_words("We give the City written advice. The Authority's staff may call us.",
                                      "District", "special_district")
    assert sorted(f["match"] for f in flags) == ["The Authority", "the City"]
    assert all(f["level"] == "blocking" for f in flags)
    assert F.find_wrong_agency_words("We give the District written advice.", "District", "special_district") == []
    assert F.find_wrong_agency_words("each city and the district office", "District", "special_district") == []


def test_governing_body_term_that_this_agency_does_not_have():
    flags = F.find_wrong_agency_words("We attend every City Council meeting with the City Manager.",
                                      "District", "special_district", "Board of Directors General Manager")
    assert sorted(f["match"] for f in flags) == ["City Council", "City Manager"]
    # a term the RFP itself uses is allowed even if unusual for the agency type
    assert F.find_wrong_agency_words("We report to the Board of Trustees.", "District", "special_district",
                                     "governed by a Board of Trustees") == []
    assert F.find_wrong_agency_words("We attend every City Council meeting.", "City", "city") == []


def test_library_answer_with_source_agency_left_in_is_blocking_in_context(data, ctx):
    from desk.library import fill_placeholders
    a = next(x for x in data.answers if x["proposal_id"] == "P-2025-02" and x["question_type"] == "approach")
    flags = F.check_passage(fill_placeholders(a["answer_text"], ctx), ctx)
    assert any(f["kind"] == "wrong_agency" and "Cinder Falls" in f["match"] for f in flags)
    assert F.has_blocking(flags)


def test_every_known_agency_name_is_caught_when_pasted_into_a_passage(data, ctx):
    for name in F.known_agencies(data):
        flags = F.check_passage("We have served %s for many years." % name, ctx)
        assert any(f["kind"] == "wrong_agency" and f["level"] == "blocking" for f in flags), name


# ---- people

def test_departed_attorney_full_name_and_title_form(ctx):
    assert F.has_blocking(F.find_departed("Corwin Halloway will serve as chief negotiator.", ctx["departed"]))
    assert F.has_blocking(F.find_departed("Mr. Halloway leads the team.", ctx["departed"]))
    assert F.has_blocking(F.find_departed("Corwin\nHalloway's team", ctx["departed"]))
    f = F.find_departed("The Halloway memo is attached.", ctx["departed"])
    assert [x["level"] for x in f] == ["warning"]
    assert F.find_departed("Priya Raghunathan will serve as chief negotiator.", ctx["departed"]) == []


# ---- firm facts

@pytest.mark.parametrize("text,ok", [
    ("The firm has 46 attorneys.", True),
    ("The firm has 43 attorneys.", False),
    ("The firm has forty-six attorneys.", True),
    ("The firm has forty-three attorneys.", False),
    ("a firm of more than 40 attorneys", True),
    ("a firm of more than 50 attorneys", False),
    ("We have approximately 45 lawyers.", True),
    ("We have approximately 60 lawyers.", False),
    ("The firm was founded in 1987.", True),
    ("The firm was founded in 1978.", False),
    ("Example Firm LLP has advised public agencies since 1987.", True),
    ("Example Firm LLP has advised public agencies since 1990.", False),
    ("The firm has three offices.", True),
    ("The firm has four offices.", False),
    ("Our offices are in Alder Bay, Stonemill and Port Verity.", True),
    ("Our offices are in Alder Bay and Stonemill.", False),                 # incomplete list
    ("Our offices are in Alder Bay, Stonemill and Greyhaven.", False),      # closed office
    ("Our Stonemill office will be the base.", True),
    ("Our Greyhaven office will be the base.", False),
    ("We currently represent 85 public agencies.", True),
    ("We currently represent 60 public agencies.", False),
    ("with 17 partners", True),
    ("with 20 partners", False),
    ("Our attorneys are admitted in the State of Westmark.", True),
    ("Our attorneys are admitted in the State of Borland.", False),
    ("We have completed more than 100 negotiations.", True),
    ("We have completed 200 negotiations.", False),
])
def test_firm_fact_statements(text, ok, data):
    flags, _ = F.find_fact_conflicts(text, data.facts)
    assert (flags == []) is ok, flags


def test_fact_with_no_entry_in_firm_facts_is_blocking(data):
    facts = dict(data.facts, matter_counts={})
    flags, _ = F.find_fact_conflicts("We have advised on 30 capital projects.", facts)
    assert flags and flags[0]["kind"] == "fact_not_on_file" and flags[0]["level"] == "blocking"


def test_ordinary_staffing_sentences_are_not_treated_as_firm_facts(data):
    flags, _ = F.find_fact_conflicts("We propose one lead attorney and two associates. A second partner is the backup.", data.facts)
    assert flags == []


def test_fact_message_gives_the_as_of_date(data):
    flags, _ = F.find_fact_conflicts("The firm has 38 attorneys.", data.facts)
    assert data.facts["as_of"] in flags[0]["message"] and "46" in flags[0]["message"]


def test_numbers_the_guard_cannot_check_are_listed_as_a_warning(ctx):
    flags = F.check_passage("We answer within 2 hours and have handled 310 hearings since 2015.", ctx)
    w = [f for f in flags if f["kind"] == "unverified_number"]
    assert len(w) == 1 and w[0]["level"] == "warning"
    assert all(n in w[0]["match"] for n in ("2", "310", "2015"))


def test_unfilled_placeholder_is_blocking(ctx):
    flags = F.check_passage("We propose to serve {AGENCY_NAME} well.", ctx)
    assert any(f["kind"] == "unfilled_placeholder" and f["level"] == "blocking" for f in flags)


def test_facts_block_is_built_from_firm_facts_and_passes_its_own_guard(data, ctx):
    block = F.facts_block(data.facts)
    assert "46 attorneys" in block and "1987" in block and "Port Verity" in block
    assert F.check_passage(block, ctx) == []
    changed = dict(data.facts, attorney_count=51)
    assert "51 attorneys" in F.facts_block(changed)


def test_old_library_answers_with_old_head_counts_are_flagged(data, ctx):
    from desk.library import fill_placeholders
    old = [a for a in data.answers if a["question_type"] == "firm_overview" and a["submitted"] < "2025-01-01"]
    assert old
    for a in old:
        assert F.has_blocking(F.check_passage(fill_placeholders(a["answer_text"], ctx), ctx)), a["id"]


# ---- consent check on a whole draft

def test_consent_check_finds_a_client_named_without_consent_to_name(data):
    rec = next(e for e in data.experience if not e["consent_to_name_client"])
    flags = F.check_consent("Our work for %s is a good example." % rec["client_name"].upper(), data)
    assert [f["kind"] for f in flags] == ["client_named_without_consent"]
    ok = next(e for e in data.experience if e["consent_to_name_client"])
    assert F.check_consent("Our work for %s is a good example." % ok["client_name"], data) == []


def test_consent_check_finds_a_contact_listed_without_consent_to_list(data):
    ref = next(r for r in data.references if not r["consent_to_list_contact"])
    flags = F.check_consent("Please call %s." % ref["contact_name"], data)
    assert [f["kind"] for f in flags] == ["contact_listed_without_consent"]


def test_the_two_consents_are_checked_separately(data):
    import copy
    d = copy.copy(data)
    exp = dict(next(e for e in data.experience if e["consent_to_name_client"]))
    ref = {"id": "REF-X", "experience_id": exp["id"], "client_name": exp["client_name"],
           "contact_name": "Ignatius Wetherby", "consent_to_list_contact": False}
    d.experience, d.references = [exp], [ref]
    line = "Ignatius Wetherby, General Manager, %s." % exp["client_name"]
    assert [f["kind"] for f in F.check_consent(line, d)] == ["contact_listed_without_consent"]
    ref["consent_to_list_contact"] = True
    assert F.check_consent(line, d) == []
    exp["consent_to_name_client"] = False          # the contact agreed; the client did not
    assert [f["kind"] for f in F.check_consent(line, d)] == ["client_named_without_consent"]
    del exp["consent_to_name_client"], ref["consent_to_list_contact"]      # both missing: both blocked
    assert sorted(f["kind"] for f in F.check_consent(line, d)) == ["client_named_without_consent",
                                                                  "contact_listed_without_consent"]
