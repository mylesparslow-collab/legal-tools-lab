"""Canonical record schemas.

Each field: (name, type, required, default). Types: str, int, bool, date (ISO
string), list (list of strings), raw (kept as loaded). A firm's own export is
mapped onto these names by a mapping file; see SWAP_IN_REAL_DATA.md.

No field here is taken from any named product. They are the minimum the tool
needs to do its job.
"""

SCHEMAS = {
    "past_answers": [
        ("id", "str", True, None),
        ("proposal_id", "str", True, None),
        ("proposal_agency", "str", True, None),      # agency the source proposal was written for
        ("agency_type", "str", True, None),          # city | special_district | school_district | transit | county | other
        ("practice", "str", True, None),             # general_counsel | labor | capital_projects | other
        ("submitted", "date", True, None),
        ("outcome", "str", False, "pending"),        # won | lost | pending
        ("question_type", "str", True, None),
        ("question_text", "str", False, ""),
        ("answer_text", "str", True, None),
        ("approved", "bool", False, False),          # approved for reuse by the practice lead
        ("approver", "str", False, ""),
        ("review_by", "date", True, None),           # after this date the answer is stale
        ("tags", "list", False, []),
    ],
    "experience": [
        ("id", "str", True, None),
        ("client_name", "str", True, None),
        ("client_consent", "bool", False, False),    # client has agreed to be named in proposals
        ("anonymized_description", "str", False, ""),  # approved wording used when the client is not named
        ("agency_type", "str", True, None),
        ("practice", "str", True, None),
        ("subjects", "list", False, []),
        ("role", "str", False, ""),
        ("start_year", "int", True, None),
        ("end_year", "int", False, None),            # empty means ongoing
        ("summary", "str", False, ""),
        ("lead_attorney_id", "str", False, ""),
    ],
    "bios": [
        ("id", "str", True, None),
        ("name", "str", True, None),
        ("title", "str", True, None),
        ("status", "str", False, "active"),          # active | departed
        ("admit_year", "int", False, None),
        ("office", "str", False, ""),
        ("practices", "list", False, []),
        ("agency_types", "list", False, []),
        ("subjects", "list", False, []),
        ("roles", "list", False, []),
        ("bio_text", "str", False, ""),
        ("departed_date", "str", False, ""),
    ],
    "rate_schedules": [
        ("id", "str", True, None),
        ("name", "str", True, None),
        ("effective", "date", True, None),
        ("expires", "date", True, None),
        ("approved_by", "str", False, ""),
        ("rates", "raw", True, None),                # list of {title, hourly}
    ],
    "references": [
        ("id", "str", True, None),
        ("experience_id", "str", False, ""),
        ("client_name", "str", True, None),
        ("contact_name", "str", True, None),
        ("contact_title", "str", False, ""),
        ("phone", "str", False, ""),
        ("email", "str", False, ""),
        ("client_consent", "bool", False, False),    # contact has agreed to be listed as a reference
        ("last_confirmed", "date", False, None),
        ("agency_type", "str", False, ""),
        ("practice", "str", False, ""),
    ],
    "standard_forms": [
        ("id", "str", True, None),
        ("name", "str", True, None),
        ("aliases", "list", False, []),
        ("file", "str", False, ""),
        ("requires_signature", "bool", False, True),
        ("requires_notary", "bool", False, False),
        ("last_reviewed", "date", False, None),
    ],
}

QUESTION_TYPES = ["firm_overview", "approach", "team", "experience", "references", "conflicts", "rates",
                  "diversity_local", "transition"]
OUTCOMES = ["won", "lost", "pending"]
TRUE_WORDS = {"true", "yes", "y", "1"}
