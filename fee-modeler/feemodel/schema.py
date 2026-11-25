"""Canonical schema. Every export is mapped onto these tables before anything else runs."""

from collections import namedtuple

Field = namedtuple("Field", "name type required description")

PHASES = ["assessment", "drafting", "discovery", "hearing", "closing"]
PHASE_LABELS = {
    "assessment": "Assessment",
    "drafting": "Drafting and pleadings",
    "discovery": "Discovery and diligence",
    "hearing": "Hearing",
    "closing": "Resolution and closing",
}

STATUS_VALUES = ["open", "closed"]
NORMAL_CLOSE = "completed"
CLOSE_REASONS = ["completed", "settled_early", "transferred", "other"]

SCHEMA = {
    "matters": [
        Field("matter_id", "str", True, "Unique matter identifier."),
        Field("matter_type", "str", True, "Matter type used to group comparable matters."),
        Field("status", "str", True, "open or closed."),
        Field("open_date", "date", True, "Date the matter opened."),
        Field("close_date", "date", False, "Date the matter closed. Required for closed matters."),
        Field("close_reason", "str", False,
              "completed, settled_early, transferred or other. Without it abnormal closes cannot be flagged."),
        Field("client_id", "str", False, "Client identifier. Not used in modeling."),
        Field("forum", "str", False, "Court, agency or other forum."),
        Field("num_parties", "int", False, "Number of parties."),
        Field("amount_band", "str", False, "Amount in controversy or deal size band."),
        Field("num_units", "int", False, "Number of facilities, contracts or similar units in scope."),
        Field("hearing_occurred", "bool", False, "Whether a contested hearing took place."),
        Field("hearing_date", "date", False, "Hearing date. Improves the date-window phase fallback."),
    ],
    "timekeepers": [
        Field("timekeeper_id", "str", True, "Timekeeper identifier."),
        Field("level", "str", True, "Level, matching a level in the rate card."),
        Field("effective_from", "date", False,
              "Date the level took effect. Blank means from the start. One row per level held."),
    ],
    "time_entries": [
        Field("entry_id", "str", True, "Unique time entry identifier."),
        Field("matter_id", "str", True, "Matter the time was recorded to."),
        Field("timekeeper_id", "str", True, "Who recorded the time."),
        Field("work_date", "date", True, "Date the work was done."),
        Field("hours_worked", "decimal", True, "Hours recorded before any write-down."),
        Field("rate", "decimal", True, "Hourly rate applied to the entry at the time."),
        Field("hours_billed", "decimal", False,
              "Hours billed after write-downs. If absent, billed is assumed equal to worked and flagged."),
        Field("level", "str", False,
              "Timekeeper level at the time of the entry. If absent, taken from the timekeepers table."),
        Field("task_code", "str", False, "Task or phase code. If absent, phase falls back to date windows."),
    ],
    "invoices": [
        Field("invoice_id", "str", True, "Unique invoice identifier."),
        Field("matter_id", "str", True, "Matter invoiced."),
        Field("invoice_date", "date", True, "Invoice date."),
        Field("amount_billed", "decimal", True, "Fees billed on the invoice."),
        Field("amount_collected", "decimal", True, "Cash collected against the invoice."),
        Field("amount_written_off", "decimal", False,
              "Amount written off. If absent, billed minus collected is reported as uncollected."),
    ],
}

# The timekeepers table can be left out when every time entry carries its own level.
OPTIONAL_TABLES = {"timekeepers"}


def required_fields(table):
    return [f.name for f in SCHEMA[table] if f.required]


def field(table, name):
    for f in SCHEMA[table]:
        if f.name == name:
            return f
    raise KeyError("%s.%s" % (table, name))
