"""Guideline model: each client's billing rules as structured data.

A rule is a contract term between a client and its outside counsel, stored as
data. A rule is enforced only when its status is "confirmed".
"""

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List

from .model import DataError, dec, parse_iso_date

SEVERITIES = {
    "reject": "will likely be rejected",
    "reduce": "likely reduced",
    "review": "review",
}
SEVERITY_ORDER = {"reject": 0, "reduce": 1, "review": 2}
STATUSES = ("confirmed", "proposed")
PROPOSED_CONFIDENCE = "proposed, needs confirmation"

# name -> (kind, required). Kinds: number, int, bool, list, dict, str.
RULE_TYPES = {
    "block_billing": {
        "label": "Block billing prohibited",
        "severity": "reduce",
        "params": {"max_tasks": ("int", True), "min_hours": ("number", True)},
    },
    "minimum_increment": {
        "label": "Minimum time increment",
        "severity": "reject",
        "params": {"increment": ("number", True)},
    },
    "rounding_pattern": {
        "label": "Rounding-up pattern",
        "severity": "review",
        "params": {
            "block": ("number", True),
            "min_entries": ("int", True),
            "threshold_percent": ("number", True),
        },
    },
    "daily_hour_cap": {
        "label": "Daily hour cap per timekeeper",
        "severity": "reduce",
        "params": {"max_hours": ("number", True)},
    },
    "staffing_matter_limit": {
        "label": "Staffing limit per matter",
        "severity": "review",
        "params": {"max_timekeepers": ("int", True)},
    },
    "staffing_event_limit": {
        "label": "Staffing limit per event",
        "severity": "reduce",
        "params": {"max_attendees": ("int", True), "events": ("list", True)},
    },
    "unapproved_timekeeper": {
        "label": "Unapproved timekeeper",
        "severity": "reject",
        "params": {},
    },
    "rate_above_card": {
        "label": "Rate above approved rate card",
        "severity": "reduce",
        "params": {},
    },
    "rate_increase_notice": {
        "label": "Rate increase without notice",
        "severity": "reduce",
        "params": {"notice_days": ("int", True)},
    },
    "non_billable_task": {
        "label": "Non-billable task categories",
        "severity": "reject",
        "params": {"categories": ("dict", True)},
    },
    "internal_conference_limit": {
        "label": "Internal conference limit",
        "severity": "reduce",
        "params": {"max_hours_per_entry": ("number", True), "phrases": ("list", False)},
    },
    "research_approval": {
        "label": "Research needs approval above a limit",
        "severity": "reduce",
        "params": {"max_hours": ("number", True)},
    },
    "travel_time": {
        "label": "Travel time",
        "severity": "reduce",
        "params": {"billable_percent": ("number", True), "requires_approval": ("bool", True)},
    },
    "expense_overhead": {
        "label": "Overhead expenses not reimbursable",
        "severity": "reject",
        "params": {"codes": ("list", True), "phrases": ("list", True)},
    },
    "expense_receipt_threshold": {
        "label": "Receipt threshold",
        "severity": "reject",
        "params": {"threshold": ("number", True), "inclusive": ("bool", False)},
    },
    "expense_per_diem": {
        "label": "Per-diem caps",
        "severity": "reduce",
        "params": {"caps": ("dict", True)},
    },
    "expense_markup": {
        "label": "Expense mark-up prohibited",
        "severity": "reduce",
        "params": {},
    },
    "vague_description": {
        "label": "Vague descriptions",
        "severity": "reduce",
        "params": {
            "always_phrases": ("list", True),
            "bare_phrases": ("list", True),
            "min_words": ("int", False),
        },
    },
    "required_codes": {
        "label": "Required task and activity codes",
        "severity": "reject",
        "params": {
            "require_task": ("bool", True),
            "require_activity": ("bool", True),
            "require_expense": ("bool", True),
            "check_against_sample_table": ("bool", False),
        },
    },
    "late_time": {
        "label": "Late time",
        "severity": "reject",
        "params": {"max_age_days": ("int", True)},
    },
    "budget_cap": {
        "label": "Matter budget or not-to-exceed cap",
        "severity": "reject",
        "params": {},
    },
    "phase_cap": {
        "label": "Phase budget cap",
        "severity": "reduce",
        "params": {},
    },
    "duplicate_entries": {
        "label": "Duplicate entries",
        "severity": "reject",
        "params": {},
    },
    "ai_disclosure_required": {
        "label": "AI-assisted work must be disclosed on the invoice",
        "severity": "reject",
        "params": {"disclosure_marker": ("str", True), "ai_terms": ("list", True)},
    },
    "ai_nonpayable_task": {
        "label": "Client will not pay for certain AI-assisted tasks",
        "severity": "reject",
        "params": {
            "disclosure_marker": ("str", True),
            "ai_terms": ("list", True),
            "task_phrases": ("list", True),
        },
    },
}

# Default phrase lists. They are starting points that a person can edit in the JSON.
DEFAULT_CATEGORY_PHRASES = {
    "clerical": [
        "scanning",
        "scan documents",
        "photocopying",
        "bates stamping",
        "organizing files",
        "organize files",
        "data entry",
        "updating file index",
        "saving documents to",
    ],
    "training": ["training", "orientation", "getting up to speed"],
    "conflicts": ["conflicts check", "conflict check", "new matter intake"],
    "invoice_prep": [
        "prepare invoice",
        "preparing invoice",
        "prebill",
        "pre-bill",
        "billing inquiry",
        "invoice backup",
        "correct invoice",
    ],
}
DEFAULT_OVERHEAD_CODES = ["E103", "E104", "E105", "E108"]
DEFAULT_OVERHEAD_PHRASES = [
    "postage",
    "word processing",
    "local telephone",
    "office supplies",
    "overtime",
    "subscription",
]
DEFAULT_ALWAYS_VAGUE = [
    "attention to file",
    "attention to matter",
    "various tasks",
    "work on case",
    "work on matter",
]
DEFAULT_BARE_VAGUE = [
    "review documents",
    "review file",
    "work on discovery",
    "legal research",
    "draft correspondence",
    "telephone call",
    "prepare for hearing",
    "trial preparation",
]
DEFAULT_AI_TERMS = [
    "generative ai",
    "artificial intelligence",
    "ai tool",
    "ai-assisted",
    "ai assisted",
    "large language model",
    "machine-generated",
]
DEFAULT_INTERNAL_CONFERENCE_PHRASES = [
    "internal conference",
    "internal meeting",
    "intra-office conference",
    "office conference",
    "team meeting",
    "confer with associate",
    "confer with partner",
    "confer with paralegal",
    "conference with associate",
    "conference with partner",
    "conference with paralegal",
]


@dataclass
class Rule:
    rule_id: str
    type: str
    status: str
    severity: str
    params: dict
    source_quote: str
    source_ref: str
    confidence: str = ""
    confirmed_by: str = ""
    confirmed_on: str = ""
    notes: str = ""

    @property
    def confirmed(self):
        return self.status == "confirmed"

    @property
    def label(self):
        if self.type == "arithmetic":
            return "Arithmetic"
        return RULE_TYPES[self.type]["label"]

    def to_dict(self):
        out = {
            "rule_id": self.rule_id,
            "type": self.type,
            "status": self.status,
            "severity": self.severity,
            "params": self.params,
            "source_quote": self.source_quote,
            "source_ref": self.source_ref,
        }
        for name in ("confidence", "confirmed_by", "confirmed_on", "notes"):
            if getattr(self, name):
                out[name] = getattr(self, name)
        return out


@dataclass
class Guideline:
    client_id: str
    client_name: str
    document: str
    rules: List[Rule] = field(default_factory=list)

    @property
    def confirmed_rules(self):
        return [r for r in self.rules if r.confirmed]

    @property
    def proposed_rules(self):
        return [r for r in self.rules if not r.confirmed]

    def rule_of_type(self, rule_type):
        for rule in self.rules:
            if rule.type == rule_type:
                return rule
        return None

    def to_dict(self):
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "document": self.document,
            "rules": [r.to_dict() for r in self.rules],
        }


def loads(text):
    """json.loads that never produces a binary float."""
    return json.loads(text, parse_float=Decimal)


def to_jsonable(value):
    """Convert Decimals and dates so json.dumps can write them without floats."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def dumps(value):
    return json.dumps(to_jsonable(value), indent=2, ensure_ascii=False) + "\n"


SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "guidelines", "schema.json"
)


def _type_ok(value, expected):
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return True


def schema_errors(value, schema, path="$"):
    """Check a value against the small JSON Schema subset used by schema.json.

    Supported keywords: type, required, properties, items, enum, minLength.
    """
    errors = []
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        return ["%s: expected %s" % (path, expected)]
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r is not one of %s" % (path, value, ", ".join(map(str, schema["enum"]))))
    if "minLength" in schema and isinstance(value, str) and len(value.strip()) < schema["minLength"]:
        errors.append("%s: must not be empty" % path)
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append("%s: missing %r" % (path, name))
        for name, sub in schema.get("properties", {}).items():
            if name in value:
                errors.extend(schema_errors(value[name], sub, "%s.%s" % (path, name)))
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], "%s[%d]" % (path, index)))
    return errors


def _param_errors(rule, path):
    errors = []
    spec = RULE_TYPES[rule["type"]]["params"]
    params = rule.get("params", {})
    for name, (kind, required) in spec.items():
        if name not in params:
            if required:
                errors.append("%s.params: missing %r for rule type %s" % (path, name, rule["type"]))
            continue
        value = params[name]
        ok = True
        if kind == "number":
            try:
                dec(value)
            except DataError:
                ok = False
        elif kind == "int":
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "bool":
            ok = isinstance(value, bool)
        elif kind == "list":
            ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
        elif kind == "dict":
            ok = isinstance(value, dict)
        elif kind == "str":
            ok = isinstance(value, str) and bool(value)
        if not ok:
            errors.append("%s.params.%s: expected %s" % (path, name, kind))
    for name in params:
        if name not in spec:
            errors.append("%s.params: unknown parameter %r for rule type %s" % (path, name, rule["type"]))
    return errors


def validate(data, schema=None):
    """Return a list of problems with a guideline dict. Empty list means valid."""
    if schema is None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
    errors = schema_errors(data, schema)
    if errors:
        return errors
    seen = set()
    for index, rule in enumerate(data["rules"]):
        path = "$.rules[%d]" % index
        if rule["rule_id"] in seen:
            errors.append("%s: rule_id %r is repeated" % (path, rule["rule_id"]))
        seen.add(rule["rule_id"])
        errors.extend(_param_errors(rule, path))
        if rule["status"] == "confirmed":
            if not rule.get("confirmed_by", "").strip():
                errors.append("%s: a confirmed rule needs confirmed_by" % path)
            try:
                parse_iso_date(rule.get("confirmed_on", ""))
            except DataError:
                errors.append("%s: a confirmed rule needs confirmed_on as YYYY-MM-DD" % path)
    return errors


def from_dict(data):
    errors = validate(data)
    if errors:
        raise DataError("guideline file is not valid:\n  " + "\n  ".join(errors))
    rules = [
        Rule(
            rule_id=r["rule_id"],
            type=r["type"],
            status=r["status"],
            severity=r["severity"],
            params=r.get("params", {}),
            source_quote=r["source_quote"],
            source_ref=r["source_ref"],
            confidence=r.get("confidence", ""),
            confirmed_by=r.get("confirmed_by", ""),
            confirmed_on=r.get("confirmed_on", ""),
            notes=r.get("notes", ""),
        )
        for r in data["rules"]
    ]
    return Guideline(
        client_id=data["client_id"],
        client_name=data["client_name"],
        document=data.get("document", ""),
        rules=rules,
    )


def load_guideline(path):
    with open(path, "r", encoding="utf-8") as handle:
        return from_dict(loads(handle.read()))


def guideline_paths(directory):
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".json") and name != "schema.json"
    )


def load_all(directory):
    return [load_guideline(p) for p in guideline_paths(directory)]


def load_matters(path):
    """Load matter context: approved timekeepers, rate card, approvals and budget."""
    with open(path, "r", encoding="utf-8") as handle:
        data = loads(handle.read())
    return {m["matter_id"]: m for m in data.get("matters", [])}


def load_code_table(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        "task": set(data.get("task_codes", {})),
        "activity": set(data.get("activity_codes", {})),
        "expense": set(data.get("expense_codes", {})),
    }
