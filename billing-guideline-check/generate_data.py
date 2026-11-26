"""Seeded generator for the synthetic data in data/.

Everything here is invented: clients, timekeepers, matters, rates, guideline
documents and invoices. Run `python generate_data.py` to rebuild data/. The
output is deterministic for a given SEED.

The generator plants known violations in the invoices and writes
data/ANSWER_KEY.json listing each one. Tests compare the engine's findings
with that key.
"""

import datetime as dt
import json
import os
import random
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from billcheck import guidelines as G  # noqa: E402
from billcheck import intake  # noqa: E402
from billcheck.model import Invoice, Line, money  # noqa: E402
from billcheck.writers import write_csv, write_ledes  # noqa: E402

SEED = 20261105
D = Decimal
CONFIRMED_BY = "Billing manager (fictional)"
CONFIRMED_ON = "2026-09-15"
INVOICE_DATE = dt.date(2026, 11, 5)
PERIOD_START = dt.date(2026, 10, 1)
PERIOD_END = dt.date(2026, 10, 31)

SHORT = {
    "block_billing": "BLOCK",
    "minimum_increment": "INCR",
    "rounding_pattern": "ROUND",
    "daily_hour_cap": "DAYCAP",
    "staffing_matter_limit": "STAFF",
    "staffing_event_limit": "EVENT",
    "unapproved_timekeeper": "TK",
    "rate_above_card": "RATE",
    "rate_increase_notice": "RATEUP",
    "non_billable_task": "NONBILL",
    "internal_conference_limit": "CONF",
    "research_approval": "RESEARCH",
    "travel_time": "TRAVEL",
    "expense_overhead": "OVERHEAD",
    "expense_receipt_threshold": "RECEIPT",
    "expense_per_diem": "PERDIEM",
    "expense_markup": "MARKUP",
    "vague_description": "VAGUE",
    "required_codes": "CODES",
    "late_time": "LATE",
    "budget_cap": "BUDGET",
    "phase_cap": "PHASE",
    "duplicate_entries": "DUP",
    "ai_disclosure_required": "AIDISC",
    "ai_nonpayable_task": "AINOPAY",
}


def cats(*names, extra=None):
    out = {name: list(G.DEFAULT_CATEGORY_PHRASES[name]) for name in names}
    for name, phrases in (extra or {}).items():
        out[name] = out.get(name, []) + phrases
    return out


def vague(always=(), bare=()):
    return {
        "always_phrases": sorted(set(list(always) + G.DEFAULT_ALWAYS_VAGUE)),
        "bare_phrases": sorted(set(list(bare) + G.DEFAULT_BARE_VAGUE)),
        "min_words": 3,
    }


def R(sentence, *rules, status="confirmed"):
    """A sentence that is the source of one or more rules: (type, params[, severity])."""
    return {"sentence": sentence, "rules": list(rules), "status": status}


AI_PARAMS = {"disclosure_marker": "[AI-assisted]", "ai_terms": list(G.DEFAULT_AI_TERMS)}

# ----------------------------------------------------------------- guideline documents

CLIENTS = {
    "quillfeather": {
        "name": "Quillfeather Mutual Indemnity",
        "prefix": "QMI",
        "title": [
            "QUILLFEATHER MUTUAL INDEMNITY",
            "Litigation management and billing guidelines for panel counsel",
            "Fictional document written for a software demo",
        ],
        "body": [
            ("page", 1),
            ("heading", "1. Purpose"),
            ("para", [
                "These guidelines apply to every claim file assigned to panel counsel.",
                "Invoices that do not comply will be returned or reduced by the bill review unit.",
            ]),
            ("heading", "2.1 Assigned timekeepers"),
            ("para", [
                R("Only timekeepers approved in writing by the claims professional may bill time to a file.", ("unapproved_timekeeper", {})),
                R("No more than 3 timekeepers may bill to a file in any invoice period without prior approval.", ("staffing_matter_limit", {"max_timekeepers": 3})),
            ]),
            ("heading", "2.2 Depositions and hearings"),
            ("para", [
                R(
                    "The Company will pay for only 1 attorney to attend a deposition, hearing or mediation unless the claims professional approves a second attendee in advance.",
                    ("staffing_event_limit", {"max_attendees": 1, "events": ["deposition", "hearing", "mediation"]}),
                ),
            ]),
            ("heading", "2.3 Intra-office conferences"),
            ("para", [
                "Counsel should keep conferences among firm personnel short.",
                R("No more than 0.3 hour may be billed for any single intra-office conference.", ("internal_conference_limit", {"max_hours_per_entry": "0.3"})),
            ]),
            ("page", 2),
            ("heading", "3.1 Time increments"),
            ("para", [
                R("Time must be recorded in increments of 0.1 hour.", ("minimum_increment", {"increment": "0.1"})),
                R(
                    "Entries that are routinely rounded up to the half hour or hour will be questioned.",
                    ("rounding_pattern", {"block": "0.5", "min_entries": 5, "threshold_percent": 80}),
                ),
            ]),
            ("heading", "3.2 Task descriptions"),
            ("para", [
                R("Block billing is not permitted and each task must be entered separately with its own time.", ("block_billing", {"max_tasks": 1, "min_hours": 0})),
                R('Vague entries such as "attention to file" or "review documents" will not be paid.', ("vague_description", vague())),
                R(
                    "Every fee entry must carry a UTBMS task code and activity code, and every expense entry must carry an expense code.",
                    ("required_codes", {"require_task": True, "require_activity": True, "require_expense": True}),
                ),
            ]),
            ("heading", "3.3 Limits on time"),
            ("para", [
                R("The Company will not pay for more than 10 hours billed by one timekeeper in a single day without an explanation.", ("daily_hour_cap", {"max_hours": 10})),
                R("Time entries more than 60 days old on the invoice date will not be paid.", ("late_time", {"max_age_days": 60})),
                R("Duplicate entries will be rejected.", ("duplicate_entries", {})),
            ]),
            ("page", 3),
            ("heading", "4. Rates"),
            ("para", [
                R("Counsel may not bill at rates above the approved rate schedule for the file.", ("rate_above_card", {})),
                R("A rate increase takes effect only after 30 days written notice to the Company.", ("rate_increase_notice", {"notice_days": 30})),
            ]),
            ("heading", "5. Work the Company does not pay for"),
            ("para", [
                R(
                    "The Company does not pay for clerical work, training, conflicts checks or the preparation of invoices.",
                    ("non_billable_task", {"categories": cats("clerical", "training", "conflicts", "invoice_prep")}),
                ),
                R("Legal research exceeding 3 hours on a file requires prior approval from the claims professional.", ("research_approval", {"max_hours": 3})),
                R("Travel time is billed at 50% of the approved hourly rate.", ("travel_time", {"billable_percent": 50, "requires_approval": False})),
            ]),
            ("page", 4),
            ("heading", "6. Expenses"),
            ("para", [
                R(
                    "Overhead items such as postage, word processing, local telephone and office supplies are not reimbursable.",
                    ("expense_overhead", {"codes": list(G.DEFAULT_OVERHEAD_CODES), "phrases": list(G.DEFAULT_OVERHEAD_PHRASES)}),
                ),
                R("A receipt must accompany any single expense of $25.00 or more.", ("expense_receipt_threshold", {"threshold": "25.00", "inclusive": True})),
                R(
                    "Meals while traveling are reimbursed up to $50.00 per person per day and lodging up to $175.00 per night.",
                    ("expense_per_diem", {"caps": {"meal": "50.00", "lodging": "175.00"}}),
                ),
                R("Expenses must be billed at actual cost with no mark-up.", ("expense_markup", {})),
            ]),
        ],
    },
    "brackenmoor": {
        "name": "Brackenmoor Regional Water Agency",
        "prefix": "BRW",
        "title": [
            "BRACKENMOOR REGIONAL WATER AGENCY",
            "Office of the General Counsel",
            "Exhibit C to Legal Services Agreement: billing requirements",
            "Fictional document written for a software demo",
        ],
        "body": [
            ("page", 1),
            ("heading", "Article I. Compensation"),
            ("heading", "Section 1.1 Not-to-exceed amount"),
            ("para", [
                R(
                    "Total compensation under this Agreement shall not exceed the not-to-exceed amount stated in the task order, and Counsel shall not be paid for any amount above it without a written amendment.",
                    ("budget_cap", {}),
                ),
                R("Fees billed to any phase of the approved budget shall not exceed the amount allotted to that phase.", ("phase_cap", {})),
            ]),
            ("heading", "Section 1.2 Rates and personnel"),
            ("para", [
                R("Counsel shall bill only at the hourly rates listed in Exhibit B.", ("rate_above_card", {})),
                R("Services performed by personnel not listed in Exhibit B shall not be compensated.", ("unapproved_timekeeper", {})),
            ]),
            ("page", 2),
            ("heading", "Section 2.1 Time records"),
            ("para", [
                R("Time shall be recorded in increments of one-tenth of an hour.", ("minimum_increment", {"increment": "0.1"})),
                R("Any entry of more than 0.5 hour that combines two or more tasks shall be returned unpaid.", ("block_billing", {"max_tasks": 1, "min_hours": "0.5"}, "reject")),
                R(
                    "Each time entry shall identify the phase of the approved budget by task code.",
                    ("required_codes", {"require_task": True, "require_activity": False, "require_expense": False}),
                ),
                R("Time submitted more than 90 days after the date of service shall not be paid.", ("late_time", {"max_age_days": 90})),
                R("The Agency shall not pay twice for the same service, and duplicate entries shall be struck.", ("duplicate_entries", {})),
            ]),
            ("heading", "Section 2.2 Non-compensable time"),
            ("para", [
                R(
                    "Travel time shall not be compensated unless the General Counsel has approved the travel in writing in advance.",
                    ("travel_time", {"billable_percent": 100, "requires_approval": True}),
                ),
                R(
                    "Secretarial, clerical and file-management tasks are included in the hourly rates and shall not be billed separately.",
                    ("non_billable_task", {"categories": cats("clerical")}),
                ),
            ]),
            ("page", 3),
            ("heading", "Article III. Reimbursable costs"),
            ("para", [
                R(
                    "Meals shall be reimbursed at no more than $45.00 per person per day and lodging at no more than $160.00 per night.",
                    ("expense_per_diem", {"caps": {"meal": "45.00", "lodging": "160.00"}}),
                ),
                R("Each cost item of $10.00 or more shall be supported by a receipt.", ("expense_receipt_threshold", {"threshold": "10.00", "inclusive": True})),
            ]),
        ],
    },
    "ostervane": {
        "name": "Ostervane Industrial Holdings",
        "prefix": "OIH",
        "title": [
            "OSTERVANE INDUSTRIAL HOLDINGS",
            "Legal department: working with outside counsel",
            "Fictional document written for a software demo",
        ],
        "body": [
            ("page", 1),
            ("heading", "Part A. How we expect matters to be staffed"),
            ("para", [
                R(
                    "We expect lean staffing, and we will pay for no more than 2 of your lawyers at any hearing, deposition or mediation.",
                    ("staffing_event_limit", {"max_attendees": 2, "events": ["hearing", "deposition", "mediation"]}),
                ),
                R("We will question any day on which one person bills more than 12 hours.", ("daily_hour_cap", {"max_hours": 12}, "review")),
                R("Please obtain our approval before spending more than 5 hours on legal research for a matter.", ("research_approval", {"max_hours": 5})),
            ]),
            ("heading", "Part B. What your invoices should look like"),
            ("para", [
                R("Record time in increments of 0.1 hour.", ("minimum_increment", {"increment": "0.1"})),
                R("Do not block bill: an entry exceeding 1.0 hour must describe a single task.", ("block_billing", {"max_tasks": 1, "min_hours": "1.0"})),
                R(
                    'We cannot pay for entries that are too generic to evaluate, for example "work on discovery" or "attention to matter".',
                    ("vague_description", vague()),
                ),
                R(
                    "Each fee entry needs a task code and an activity code.",
                    ("required_codes", {"require_task": True, "require_activity": True, "require_expense": False}),
                ),
                R("If the same entry appears twice we will pay it once.", ("duplicate_entries", {})),
            ]),
            ("page", 2),
            ("heading", "Part C. Rates"),
            ("para", [
                R("Bill at the rates on the agreed rate card and no higher.", ("rate_above_card", {})),
                R("We need 60 days written notice before any rate increase applies to our matters.", ("rate_increase_notice", {"notice_days": 60})),
            ]),
            ("heading", "Part D. Things we do not pay for"),
            ("para", [
                R(
                    "We do not pay for clerical tasks or for time spent preparing, reviewing or correcting invoices.",
                    ("non_billable_task", {"categories": cats("clerical", "invoice_prep")}),
                ),
                R(
                    "We do not reimburse overhead such as word processing, overtime, postage and subscription databases.",
                    ("expense_overhead", {"codes": list(G.DEFAULT_OVERHEAD_CODES), "phrases": list(G.DEFAULT_OVERHEAD_PHRASES)}),
                ),
                R("Pass third-party costs through at cost, without mark-up.", ("expense_markup", {})),
            ]),
        ],
    },
    "luminqa": {
        "name": "Luminqa Data Systems",
        "prefix": "LDS",
        "title": [
            "LUMINQA DATA SYSTEMS",
            "Outside counsel terms, version 4",
            "Fictional document written for a software demo",
        ],
        "body": [
            ("page", 1),
            ("heading", "Schedule A: Billing"),
            ("para", [
                R("Time is to be kept in tenths of an hour.", ("minimum_increment", {"increment": "0.1"})),
                R("Entries that lump several tasks together under one time total will be sent back.", ("block_billing", {"max_tasks": 1, "min_hours": 0})),
                R(
                    'Narratives must say what was done and for what purpose; entries like "review documents" or "attention to file" are not enough.',
                    ("vague_description", vague()),
                ),
                R("Rates are fixed by the engagement rate card for the calendar year and may not be exceeded.", ("rate_above_card", {})),
                R("Internal conferences among your team are capped at 0.5 hour per entry.", ("internal_conference_limit", {"max_hours_per_entry": "0.5"})),
                R("Submit time within 45 days of the work; older time is written off.", ("late_time", {"max_age_days": 45})),
                R(
                    "General overhead, including research database subscriptions and word processing, is not chargeable.",
                    ("expense_overhead", {"codes": list(G.DEFAULT_OVERHEAD_CODES), "phrases": list(G.DEFAULT_OVERHEAD_PHRASES)}),
                ),
            ]),
            ("page", 2),
            ("heading", "Schedule B: Use of artificial intelligence tools"),
            ("para", [
                "This schedule is a term of our engagement with you and applies to every matter.",
                R(
                    'If any work billed to us was performed with the assistance of a generative artificial intelligence tool, the time entry must be marked "[AI-assisted]" on the invoice.',
                    ("ai_disclosure_required", dict(AI_PARAMS)),
                ),
                R(
                    "We will not pay for AI-assisted summaries of transcripts or documents, or for AI-assisted first-pass document review.",
                    ("ai_nonpayable_task", dict(AI_PARAMS, task_phrases=["summarize", "summary of", "summaries of", "first-pass document review", "first pass document review"])),
                ),
            ]),
        ],
    },
    "pellwick": {
        "name": "Pellwick Bakery Supply",
        "prefix": "PBS",
        "title": [
            "PELLWICK BAKERY SUPPLY",
            "Letter to outside counsel about bills",
            "Fictional document written for a software demo",
        ],
        "body": [
            ("page", 1),
            ("para", [
                "Thank you for taking on our matters.",
                "We are a small company and we read every bill ourselves.",
            ]),
            ("para", [
                R(
                    "Please bill in 0.1 hour increments at the rates in your engagement letter and not above them.",
                    ("minimum_increment", {"increment": "0.1"}),
                    ("rate_above_card", {}),
                ),
            ]),
            ("para", [R("We do not want to be charged twice for the same work.", ("duplicate_entries", {}))]),
            ("para", [R("Send a receipt with any expense over $75.00.", ("expense_receipt_threshold", {"threshold": "75.00", "inclusive": False}))]),
            ("para", [
                R("We would rather not see time that is more than 30 days old.", ("late_time", {"max_age_days": 30}), status="proposed"),
            ]),
        ],
    },
}


def build_document(spec):
    lines = []
    for title in spec["title"]:
        lines += [title, ""]
    for kind, value in spec["body"]:
        if kind == "page":
            lines += ["[Page %d]" % value, ""]
        elif kind == "heading":
            lines += [value, ""]
        else:
            sentences = [item if isinstance(item, str) else item["sentence"] for item in value]
            lines += [" ".join(sentences), ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def build_guideline(client_id, spec, text):
    rules = []
    for kind, value in spec["body"]:
        if kind != "para":
            continue
        for item in value:
            if isinstance(item, str):
                continue
            ref = intake.locate(text, item["sentence"])
            assert ref, "sentence not found in generated document: %s" % item["sentence"]
            for rule in item["rules"]:
                rule_type, params = rule[0], rule[1]
                severity = rule[2] if len(rule) > 2 else G.RULE_TYPES[rule_type]["severity"]
                entry = {
                    "rule_id": "%s-%s-01" % (spec["prefix"], SHORT[rule_type]),
                    "type": rule_type,
                    "status": item["status"],
                    "severity": severity,
                    "params": params,
                    "source_quote": item["sentence"],
                    "source_ref": ref,
                }
                if item["status"] == "confirmed":
                    entry["confirmed_by"] = CONFIRMED_BY
                    entry["confirmed_on"] = CONFIRMED_ON
                else:
                    entry["confidence"] = G.PROPOSED_CONFIDENCE
                    entry["notes"] = "Not confirmed. The letter states a preference; billing staff have not confirmed it is a requirement."
                rules.append(entry)
    return {
        "client_id": client_id,
        "client_name": spec["name"],
        "document": "data/guideline_docs/%s.txt" % client_id,
        "rules": rules,
    }


# ----------------------------------------------------------------- matters


def tk(name, classification, rate, last=None, notice=None):
    return {
        "name": name,
        "classification": classification,
        "approved_rate": "%d.00" % rate,
        "last_billed_rate": "%d.00" % (last if last is not None else rate),
        "rate_notice_date": notice,
    }


NO_APPROVALS = {"research": False, "travel": False, "staffing": False}

MATTERS = {
    "QMI-0147": {
        "client_id": "quillfeather",
        "name": "Claim file 22871, premises liability defense",
        "timekeepers": {
            "TK01": tk("Odalys Brightwater", "PT", 310),
            "TK02": tk("Idris Vantongeren", "AS", 225),
            "TK03": tk("Rowan Achterberg", "LA", 110),
        },
    },
    "QMI-0152": {
        "client_id": "quillfeather",
        "name": "Claim file 23310, wage claim defense",
        "timekeepers": {
            "TK01": tk("Odalys Brightwater", "PT", 310),
            "TK04": tk("Thandeka Oyelaran-Finch", "AS", 230),
            "TK05": tk("Bexley Okonkwo-Hale", "LA", 115, last=105),
        },
    },
    "BRW-2026-03": {
        "client_id": "brackenmoor",
        "name": "Pump station bid protest",
        "timekeepers": {
            "TK11": tk("Caspian Molyneux-Reyes", "PT", 395),
            "TK12": tk("Yusra Lindqvist-Amadi", "AS", 280),
            "TK13": tk("Marek Dunleavy-Osei", "LA", 140),
        },
    },
    "OIH-LIT-088": {
        "client_id": "ostervane",
        "name": "Supply agreement dispute",
        "timekeepers": {
            "TK21": tk("Leocadia Thornquist-Abara", "PT", 720),
            "TK22": tk("Emeka Villanueva-Stroud", "AS", 510),
            "TK23": tk("Saoirse Kowalczyk-Bello", "AS", 465, last=440, notice="2026-08-20"),
            "TK24": tk("Dmitri Oyama-Lindgren", "LA", 240),
        },
    },
    "OIH-COR-031": {
        "client_id": "ostervane",
        "name": "Distributor termination dispute",
        "timekeepers": {
            "TK21": tk("Leocadia Thornquist-Abara", "PT", 720),
            "TK22": tk("Emeka Villanueva-Stroud", "AS", 510),
            "TK24": tk("Dmitri Oyama-Lindgren", "LA", 240),
        },
    },
    "LDS-IP-014": {
        "client_id": "luminqa",
        "name": "Patent infringement defense",
        "timekeepers": {
            "TK31": tk("Anneliese Okafor-Brandt", "PT", 680),
            "TK32": tk("Tobias Nakagawa-Reed", "AS", 455),
            "TK33": tk("Priya Halvorsen-Mbeki", "AS", 420),
        },
    },
    "PBS-001": {
        "client_id": "pellwick",
        "name": "Equipment lease dispute",
        "timekeepers": {
            "TK41": tk("Wendeline Abernathy-Cruz", "PT", 450),
            "TK42": tk("Hollis Fairweather-Nkemelu", "AS", 300),
        },
    },
}
EXTRA_TIMEKEEPERS = {"TK09": ("Jun Castellanos-Wray", "AS")}

# ----------------------------------------------------------------- clean narrative pool
# Every narrative here is one task, specific, and free of any phrase a client lists.

POOL = [
    ("Draft responses to opposing party's second set of interrogatories", "L310", "A103"),
    ("Review documents produced by third-party vendor in response to subpoena", "L320", "A104"),
    ("Telephone conference with client representative regarding document collection", "L320", "A106"),
    ("Draft outline for deposition of operations supervisor", "L330", "A103"),
    ("Analyze contract correspondence for notice dates", "L110", "A104"),
    ("Email to opposing counsel regarding deposition scheduling", "L330", "A107"),
    ("Draft status report to client on discovery progress", "L120", "A103"),
    ("Review opposing party's supplemental document production", "L320", "A104"),
    ("Revise proposed protective order after comments from opposing counsel", "L250", "A103"),
    ("Draft meet-and-confer letter on deficient interrogatory answers", "L350", "A103"),
    ("Review amended scheduling order entered by the court", "L230", "A104"),
    ("Draft subpoena for contractor maintenance records", "L320", "A103"),
    ("Review expert's preliminary report on damages methodology", "L340", "A104"),
    ("Telephone conference with expert regarding preliminary findings", "L130", "A108"),
    ("Draft motion in limine regarding prior incident evidence", "L430", "A103"),
    ("Review opposing party's answers to requests for admission", "L310", "A104"),
    ("Draft privilege log entries for withheld correspondence", "L320", "A103"),
    ("Analyze indemnity provisions of the master services agreement", "L120", "A104"),
    ("Email to client representative regarding verification of interrogatory answers", "L310", "A106"),
    ("Draft witness interview memorandum for shift supervisor", "L110", "A103"),
    ("Review deposition transcript of shift supervisor for errata", "L330", "A104"),
    ("Draft joint case management statement", "L230", "A103"),
    ("Revise mediation statement after client comments", "L160", "A103"),
    ("Review docket entries for newly filed motions", "L250", "A104"),
]
CLEAN_HOURS = [D(h) for h in "0.2 0.3 0.4 0.6 0.7 0.8 0.9 1.1 1.2 1.3 1.4 1.6 1.7 1.8 2.1 2.3 2.4 2.6".split()]


def weekdays():
    day = PERIOD_START
    out = []
    while day <= PERIOD_END:
        if day.weekday() < 5:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


class Builder:
    def __init__(self, invoice_id, matter_id, fmt, invoice_date=INVOICE_DATE):
        self.invoice_id = invoice_id
        self.matter_id = matter_id
        self.matter = MATTERS[matter_id]
        self.client_id = self.matter["client_id"]
        self.fmt = fmt
        self.invoice_date = invoice_date
        self.rng = random.Random("%d-%s" % (SEED, invoice_id))
        self.rows = []  # dicts, numbered at build time
        self.invoice_plants = []
        self.total_delta = D("0")
        self.not_enforced = []

    def _date(self, day):
        return day if isinstance(day, dt.date) else dt.date(2026, 10, day)

    def _who(self, tk_id):
        if tk_id in self.matter["timekeepers"]:
            card = self.matter["timekeepers"][tk_id]
            return card["name"], card["classification"], D(card["approved_rate"])
        name, classification = EXTRA_TIMEKEEPERS[tk_id]
        return name, classification, None

    def fee(self, tk_id, day, hours, narrative, task, act, rate=None, plant=(), amount_delta="0", ai=None, tag=None):
        name, classification, card_rate = self._who(tk_id)
        rate = D(str(rate)) if rate is not None else card_rate
        hours = D(str(hours))
        if ai is None and self.client_id == "luminqa":
            ai = False
        self.rows.append(
            {
                "kind": "fee", "date": self._date(day), "tk": tk_id, "name": name, "cls": classification,
                "units": hours, "rate": rate, "amount": money(hours * rate) + D(amount_delta),
                "task": task, "act": act, "exp": "", "narrative": narrative,
                "receipt": None, "cost": None, "ai": ai, "plant": list(plant), "tag": tag,
            }
        )

    def exp(self, day, units, unit_cost, narrative, code, plant=(), receipt=True, cost=None):
        units = D(str(units))
        unit_cost = D(str(unit_cost))
        amount = money(units * unit_cost)
        csv = self.fmt == "csv"
        self.rows.append(
            {
                "kind": "expense", "date": self._date(day), "tk": "", "name": "", "cls": "",
                "units": units, "rate": unit_cost, "amount": amount,
                "task": "", "act": "", "exp": code, "narrative": narrative,
                "receipt": receipt if csv else None,
                "cost": (D(str(cost)) if cost is not None else amount) if csv else None,
                "ai": None, "plant": list(plant), "tag": None,
            }
        )

    def filler(self, count, tk_ids):
        days = weekdays()
        made = 0
        guard = 0
        while made < count:
            guard += 1
            assert guard < 5000, "could not place clean filler lines"
            narrative, task, act = self.rng.choice(POOL)
            tk_id = self.rng.choice(tk_ids)
            day = self.rng.choice(days)
            hours = self.rng.choice(CLEAN_HOURS)
            same_day = [r for r in self.rows if r["kind"] == "fee" and r["tk"] == tk_id and r["date"] == day]
            if sum((r["units"] for r in same_day), D("0")) + hours > D("6"):
                continue
            if any(r["narrative"] == narrative and r["tk"] == tk_id for r in self.rows):
                continue
            self.fee(tk_id, day, hours, narrative, task, act)
            made += 1

    def plant_invoice(self, rule_type, note, tk_id=""):
        self.invoice_plants.append((rule_type, note, tk_id))

    def build(self, rule_ids):
        ordered = sorted(enumerate(self.rows), key=lambda pair: (pair[1]["date"], pair[0]))
        lines = []
        planted = []
        hard_cases = []
        for number, (_, row) in enumerate(ordered, start=1):
            lines.append(
                Line(
                    line_no=number, kind=row["kind"], date=row["date"], timekeeper_id=row["tk"],
                    timekeeper_name=row["name"], classification=row["cls"], units=row["units"],
                    rate=row["rate"], adjustment=D("0.00"), amount=row["amount"], task_code=row["task"],
                    activity_code=row["act"], expense_code=row["exp"], narrative=row["narrative"],
                    receipt=row["receipt"], cost=row["cost"], ai_assisted=row["ai"],
                )
            )
            for item in row["plant"]:
                rule_type, note = item[0], item[1]
                planted.append(
                    {
                        "invoice_id": self.invoice_id,
                        "line_no": number,
                        "timekeeper_id": row["tk"],
                        "rule_type": rule_type,
                        "rule_id": rule_ids[rule_type],
                        "expected_status": item[2] if len(item) > 2 else "open",
                        "note": note,
                    }
                )
            if row["tag"] == "not_enforced":
                self.not_enforced.append({"invoice_id": self.invoice_id, "line_no": number})
            elif row["tag"]:
                hard_cases.append({"invoice_id": self.invoice_id, "line_no": number, "note": row["tag"], "narrative": row["narrative"]})
        for rule_type, note, tk_id in self.invoice_plants:
            planted.append(
                {
                    "invoice_id": self.invoice_id,
                    "line_no": None,
                    "timekeeper_id": tk_id,
                    "rule_type": rule_type,
                    "rule_id": rule_ids[rule_type],
                    "expected_status": "open",
                    "note": note,
                }
            )
        total = sum((ln.amount for ln in lines), D("0"))
        invoice = Invoice(
            invoice_id=self.invoice_id, client_id=self.client_id, matter_id=self.matter_id,
            invoice_date=self.invoice_date, billing_start=PERIOD_START, billing_end=PERIOD_END,
            declared_total=total + self.total_delta,
            description="Professional services for October 2026" if self.fmt == "ledes" else "",
            source_format="ledes1998b" if self.fmt == "ledes" else "csv", lines=lines,
        )
        return invoice, planted, hard_cases


# ----------------------------------------------------------------- invoices


def inv_q1001():
    b = Builder("INV-Q-1001", "QMI-0147", "ledes")
    b.fee("TK02", 13, "3.4", "Review deposition transcript of store manager; draft summary for adjuster; telephone conference with adjuster regarding reserves", "L330", "A104",
          plant=[("block_billing", "three tasks in one entry")])
    b.fee("TK01", 2, "0.25", "Telephone conference with adjuster regarding mediation dates", "L160", "A106",
          plant=[("minimum_increment", "0.25 hour is not a multiple of 0.1")])
    b.fee("TK02", 14, "4.2", "Draft motion for summary judgment on notice element", "L240", "A103")
    b.fee("TK02", 14, "3.9", "Review deposition transcripts of store employees for summary judgment record", "L240", "A104")
    b.fee("TK02", 14, "2.8", "Draft separate statement of undisputed facts", "L240", "A103",
          plant=[("daily_hour_cap", "day total 10.9 hours against a 10 hour limit; 0.9 hour of this entry is over")])
    b.fee("TK01", 20, "5.2", "Attend deposition of plaintiff's treating physician", "L330", "A109")
    b.fee("TK02", 20, "5.2", "Attend deposition of plaintiff's treating physician", "L330", "A109",
          plant=[("staffing_event_limit", "second attorney at a deposition, no approval")])
    b.fee("TK01", 27, "1.6", "Attend hearing on motion to compel", "L450", "A109")
    b.fee("TK02", 27, "1.6", "Attend hearing on motion to compel", "L450", "A109",
          plant=[("staffing_event_limit", "second attorney at a hearing; client approved it, see waiver W-001", "waived")])
    b.fee("TK09", 22, "1.6", "Review incident report and witness statements for coverage analysis", "L110", "A104", rate=225,
          plant=[("unapproved_timekeeper", "TK09 is not on the approved list")])
    b.plant_invoice("staffing_matter_limit", "four timekeepers on the invoice against a limit of three")
    b.fee("TK03", 5, "1.3", "Scanning and bates stamping of medical records", "L140", "A110",
          plant=[("non_billable_task", "clerical work")])
    b.fee("TK01", 29, "0.4", "Respond to billing inquiry from adjuster on prior invoice", "L190", "A106",
          plant=[("non_billable_task", "invoice preparation")])
    b.fee("TK01", 12, "0.8", "Office conference with associate regarding deposition outline", "L330", "A105",
          plant=[("internal_conference_limit", "0.8 hour against a 0.3 hour limit")])
    b.fee("TK02", 6, "2.4", "Research notice standard for transitory spill claims", "L120", "A102")
    b.fee("TK02", 8, "1.8", "Research admissibility of prior incident reports", "L120", "A102",
          plant=[("research_approval", "research reaches 4.2 hours against a 3 hour limit, no approval")])
    b.fee("TK01", 20, "1.4", "Travel to deposition of plaintiff's treating physician", "L330", "A109",
          plant=[("travel_time", "travel billed at full rate; client pays 50%")])
    b.fee("TK02", 16, "0.6", "Attention to file", "L190", "A104",
          plant=[("vague_description", "listed vague phrase")])
    b.fee("TK03", 19, "1.2", "Review documents", "L320", "A104",
          plant=[("vague_description", "no object")])
    b.fee("TK02", 21, "0.7", "Draft notice of deposition for store manager", "L330", "",
          plant=[("required_codes", "activity code missing")])
    b.fee("TK01", dt.date(2026, 8, 18), "0.7", "Telephone conference with adjuster regarding initial case assessment", "L120", "A106",
          plant=[("late_time", "79 days old on the invoice date; limit 60")])
    b.fee("TK03", 9, "1.1", "Draft index of medical records received from providers", "L140", "A103")
    b.fee("TK03", 9, "1.1", "Draft index of medical records received from providers", "L140", "A103",
          plant=[("duplicate_entries", "same as the entry before it")])
    b.fee("TK02", 23, "1.7", "Draft supplemental responses to requests for production", "L320", "A103", rate=240,
          plant=[("rate_above_card", "billed at 240 against an approved 225")])
    b.fee("TK03", 26, "0.9", "Draft subpoena for security camera vendor records", "L320", "A103", amount_delta="10.00",
          plant=[("ARITH-LINE", "0.9 x 110 is 99.00, line says 109.00")])
    b.exp(7, 1, "18.40", "Postage for service copies", "E108", plant=[("expense_overhead", "postage is overhead")])
    b.exp(20, 1, "84.00", "Lunch during deposition of treating physician, 1 person", "E111",
          plant=[("expense_per_diem", "84.00 against a 50.00 meal cap")])
    b.exp(28, 1, "386.50", "Deposition transcript of store manager", "E115")
    b.exp(15, 1, "60.00", "Court filing fee for motion to compel", "E112")
    b.filler(14, ["TK01", "TK02", "TK03"])
    return b


def inv_q1002():
    b = Builder("INV-Q-1002", "QMI-0152", "csv")
    rounded = [
        (5, "1.0", "Draft answer to amended complaint", "L210", "A103"),
        (7, "2.0", "Review payroll records produced by client for class period", "L320", "A104"),
        (9, "0.5", "Email to adjuster regarding litigation hold notice", "L140", "A106"),
        (13, "1.5", "Draft responses to first set of requests for production", "L310", "A103"),
        (16, "3.0", "Analyze timekeeping data for meal period exposure", "L120", "A104"),
        (22, "1.0", "Draft declaration of payroll manager in support of opposition", "L250", "A103"),
    ]
    for day, hours, narrative, task, act in rounded:
        b.fee("TK04", day, hours, narrative, task, act)
    b.plant_invoice("rounding_pattern", "all six TK04 entries are multiples of 0.5 hour", "TK04")
    b.fee("TK05", 6, "0.8", "Draft subpoena for payroll records of co-defendant", "L320", "A103",
          plant=[("rate_increase_notice", "115 billed, last billed 105, no notice on record")])
    b.fee("TK05", 12, "0.3", "Conflicts check for newly named co-defendant", "L190", "A110",
          plant=[("non_billable_task", "conflicts check"), ("rate_increase_notice", "115 billed, last billed 105, no notice on record")])
    b.fee("TK01", 14, "0.7", "Training on carrier's updated e-billing portal", "L190", "A111",
          plant=[("non_billable_task", "training")])
    b.fee("TK01", 8, "2.6", "Draft motion to compel; sections on relevance; proportionality; and meet-and-confer history", "L350", "A103",
          tag="one task described with semicolons")
    b.fee("TK01", 19, "1.8", "Review plaintiff's production: invoices, purchase orders, and shipping records", "L320", "A104",
          tag="list of documents after a colon")
    b.fee("TK01", 21, "0.9", "Review and revise draft protective order", "L250", "A103", tag='"and" inside one task')
    b.fee("TK01", 23, "0.6", "Telephone conference with client and adjuster regarding settlement authority", "L160", "A106",
          tag='"and" joining two people, one task')
    b.exp(15, 1, "180.00", "Court reporter appearance fee", "E115", receipt=False,
          plant=[("expense_receipt_threshold", "180.00 with no receipt; threshold 25.00")])
    b.exp(20, 1, "96.00", "Outside copy vendor, medical records", "E102", cost="80.00",
          plant=[("expense_markup", "billed 96.00 against a cost of 80.00")])
    b.exp(27, 1, "412.50", "Deposition transcript, payroll manager", "E115")
    b.exp(15, 1, "12.00", "Parking at courthouse", "E109", receipt=False)
    b.filler(7, ["TK01"])
    b.total_delta = D("100.00")
    b.plant_invoice("ARITH-TOTAL", "declared total is 100.00 more than the lines")
    return b


def inv_b2001():
    b = Builder("INV-B-2001", "BRW-2026-03", "ledes")
    b.fee("TK12", 6, "2.2", "Review agency procurement file; draft chronology of bid protest events; email to agency counsel regarding gaps", "L110", "A104",
          plant=[("block_billing", "three tasks in one entry over 0.5 hour")])
    b.fee("TK12", 8, "0.4", "Email to agency counsel regarding site access; review reply", "L110", "A106",
          tag="two tasks but at 0.4 hour it is under this client's 0.5 hour threshold")
    b.fee("TK11", 13, "1.8", "Travel to pump station site inspection", "L110", "A109",
          plant=[("travel_time", "travel time with no approval on record")])
    b.fee("TK12", 15, "1.3", "Draft response to bid protest letter from unsuccessful bidder", "L210", "A103", rate=295,
          plant=[("rate_above_card", "billed at 295 against an approved 280")])
    b.fee("TK13", 19, "0.9", "Organizing files for off-site storage", "L140", "A110",
          plant=[("non_billable_task", "clerical work")])
    b.fee("TK13", 21, "0.6", "Draft exhibit list for protest hearing", "", "A103",
          plant=[("required_codes", "task code missing")])
    b.fee("TK11", dt.date(2026, 7, 28), "0.8", "Telephone conference with general counsel regarding protest timeline", "L120", "A106",
          plant=[("late_time", "100 days old on the invoice date; limit 90")])
    b.fee("TK13", 22, "0.7", "Draft table of bid submission dates from procurement file", "L110", "A103")
    b.fee("TK13", 22, "0.7", "Draft table of bid submission dates from procurement file", "L110", "A103",
          plant=[("duplicate_entries", "same as the entry before it")])
    b.fee("TK12", 27, "1.25", "Draft written discovery to protesting bidder", "L310", "A103",
          plant=[("minimum_increment", "1.25 hours is not a multiple of 0.1")])
    b.exp(13, 2, "189.00", "Hotel for site inspection, 2 nights", "E110",
          plant=[("expense_per_diem", "189.00 a night against a 160.00 cap")])
    b.exp(13, 1, "38.00", "Dinner during site inspection, 1 person", "E111")
    b.filler(16, ["TK11", "TK12", "TK13"])
    b.plant_invoice("budget_cap", "invoice takes the matter 1,850.00 over the not-to-exceed amount")
    b.plant_invoice("phase_cap", "phase L300 goes 640.00 over its allotted amount")
    return b


def inv_o3001():
    b = Builder("INV-O-3001", "OIH-LIT-088", "csv")
    b.fee("TK22", 5, "2.7", "Draft opposition to motion to transfer venue; telephone conference with client regarding declaration; review exhibits for filing", "L250", "A103",
          plant=[("block_billing", "three tasks in one entry over 1.0 hour")])
    b.fee("TK22", 9, "0.8", "Email to opposing counsel regarding extension; review stipulation", "L250", "A107",
          tag="two tasks but at 0.8 hour it is under this client's 1.0 hour threshold")
    b.fee("TK21", 15, "2.2", "Attend hearing on motion to transfer venue", "L450", "A109")
    b.fee("TK22", 15, "2.2", "Attend hearing on motion to transfer venue", "L450", "A109")
    b.fee("TK23", 15, "2.2", "Attend hearing on motion to transfer venue", "L450", "A109",
          plant=[("staffing_event_limit", "third lawyer at a hearing; limit is two"),
                 ("rate_increase_notice", "new rate billed before the 60 day notice period ended on 2026-10-19")])
    b.fee("TK23", 7, "3.1", "Research enforceability of forum selection clauses in supply agreements", "L250", "A102",
          plant=[("rate_increase_notice", "new rate billed before the 60 day notice period ended on 2026-10-19")])
    b.fee("TK23", 21, "2.6", "Research transfer factors applied in recent district decisions", "L250", "A102",
          plant=[("research_approval", "research reaches 5.7 hours against a 5 hour limit; waiver W-002 expired 2026-09-30")])
    b.fee("TK23", 23, "1.4", "Draft supplemental declaration of logistics manager", "L250", "A103")
    b.fee("TK22", 12, "1.1", "Work on discovery", "L310", "A103", plant=[("vague_description", "generic phrase, no object")])
    b.fee("TK24", 14, "1.2", "Draft index of exhibits for transfer hearing", "L250", "A103", rate=255,
          plant=[("rate_above_card", "billed at 255 against an approved 240")])
    b.fee("TK24", 28, "0.5", "Prepare invoice backup for client auditor", "L190", "A111",
          plant=[("non_billable_task", "invoice preparation")])
    b.fee("TK21", 16, "0.75", "Telephone conference with general counsel regarding hearing outcome", "L120", "A106",
          plant=[("minimum_increment", "0.75 hour is not a multiple of 0.1")])
    b.fee("TK22", 20, "1.3", "Draft deposition notice for purchasing director", "", "A103",
          plant=[("required_codes", "task code missing")])
    b.exp(15, 1, "65.00", "Word processing overtime charge", "E103", plant=[("expense_overhead", "word processing is overhead")])
    b.exp(14, 1, "230.00", "Outside printing vendor, hearing binders", "E102", cost="200.00",
          plant=[("expense_markup", "billed 230.00 against a cost of 200.00")])
    b.exp(29, 1, "318.75", "Court reporter fee, hearing transcript", "E116")
    b.filler(15, ["TK21", "TK22", "TK24"])
    return b


def inv_o3002():
    b = Builder("INV-O-3002", "OIH-COR-031", "ledes")
    b.exp(22, 1, "145.00", "Process server fee for third-party subpoena", "E113")
    b.filler(13, ["TK21", "TK22", "TK24"])
    return b


def inv_l4001():
    b = Builder("INV-L-4001", "LDS-IP-014", "csv")
    b.fee("TK32", 6, "2.3", "Draft claim chart for the 412 patent family", "L120", "A103", ai=True,
          plant=[("ai_disclosure_required", "flagged AI-assisted in the time system, no marker on the entry")])
    b.fee("TK32", 8, "1.9", "Draft responses to invalidity contentions [AI-assisted]", "L310", "A103", ai=True,
          tag="AI-assisted and disclosed; not a task the client refuses to pay for")
    b.fee("TK33", 13, "1.2", "Summarize deposition transcript of lead engineer [AI-assisted]", "L330", "A104", ai=True,
          plant=[("ai_nonpayable_task", "AI-assisted transcript summary")])
    b.fee("TK33", 15, "0.8", "Review output of generative AI tool for prior art search", "L120", "A104",
          plant=[("ai_disclosure_required", "narrative mentions an AI tool, no marker on the entry")])
    b.fee("TK31", 19, "1.1", "Internal conference with team regarding claim construction strategy", "L120", "A105",
          plant=[("internal_conference_limit", "1.1 hours against a 0.5 hour limit")])
    b.fee("TK31", dt.date(2026, 9, 10), "0.9", "Telephone conference with general counsel regarding litigation budget", "L150", "A106",
          plant=[("late_time", "56 days old on the invoice date; limit 45")])
    b.fee("TK33", 20, "0.9", "Review documents", "L320", "A104", plant=[("vague_description", "no object")])
    b.fee("TK32", 22, "3.1", "Review prior art references cited by examiner, draft claim amendments, and telephone conference with inventor regarding embodiments", "L120", "A104",
          plant=[("block_billing", "three tasks joined by commas")])
    b.fee("TK33", 27, "1.6", "Draft proposed claim constructions for disputed terms", "L250", "A103", rate=440,
          plant=[("rate_above_card", "billed at 440 against an approved 420")])
    b.exp(12, 1, "45.00", "Patent database subscription allocation", "E106", plant=[("expense_overhead", "subscription is overhead")])
    b.exp(26, 1, "60.00", "Certified copy of prosecution file history", "E124")
    b.filler(14, ["TK31", "TK32", "TK33"])
    return b


def inv_p5001():
    b = Builder("INV-P-5001", "PBS-001", "ledes")
    b.fee("TK42", 7, "1.2", "Draft demand letter to equipment lessor", "L160", "A103")
    b.fee("TK42", 7, "1.2", "Draft demand letter to equipment lessor", "L160", "A103",
          plant=[("duplicate_entries", "same as the entry before it")])
    b.fee("TK41", 14, "0.15", "Email to client regarding lessor's response", "L160", "A106",
          plant=[("minimum_increment", "0.15 hour is not a multiple of 0.1")])
    b.fee("TK42", 21, "1.4", "Draft complaint for breach of equipment lease", "L210", "A103", rate=325,
          plant=[("rate_above_card", "billed at 325 against an approved 300")])
    b.fee("TK41", dt.date(2026, 9, 16), "0.6", "Telephone conference with owner regarding lease history", "L110", "A106",
          tag="not_enforced")
    b.exp(28, 1, "90.00", "Filing fee for complaint", "E112")
    b.filler(7, ["TK41", "TK42"])
    return b


BUILDERS = [inv_q1001, inv_q1002, inv_b2001, inv_o3001, inv_o3002, inv_l4001, inv_p5001]

WAIVERS = [
    {
        "waiver_id": "W-001",
        "client_id": "quillfeather",
        "matter_id": "QMI-0147",
        "rule_id": "QMI-EVENT-01",
        "timekeeper_id": "TK02",
        "invoice_id": "",
        "line_no": None,
        "approved_by": "Claims supervisor, Quillfeather Mutual Indemnity (fictional)",
        "approved_on": "2026-10-23",
        "reference": "Email of 2026-10-23, subject: second attendee at motion to compel hearing",
        "effective_from": "2026-10-27",
        "expires_on": "2026-10-27",
        "note": "Second attorney approved for the 27 October hearing only.",
    },
    {
        "waiver_id": "W-002",
        "client_id": "ostervane",
        "matter_id": "OIH-LIT-088",
        "rule_id": "OIH-RESEARCH-01",
        "timekeeper_id": "",
        "invoice_id": "",
        "line_no": None,
        "approved_by": "Associate general counsel, Ostervane Industrial Holdings (fictional)",
        "approved_on": "2026-08-04",
        "reference": "Email of 2026-08-04, subject: research on venue motion",
        "effective_from": "2026-08-04",
        "expires_on": "2026-09-30",
        "note": "Research over the limit approved through the end of September.",
    },
]

UTBMS_SAMPLE = {
    "label": "litigation code set (1997), names checked against a secondary source, not against the publisher's spreadsheets",
    "note": "Checked on 2026-11-26. Code names were compared with the lists in the Wikipedia article 'Uniform Task-Based Management System'. The counts (5 phases and 29 task codes, 11 activity codes, 24 expense codes) match the ABA code set pages on utbms.com, which is hosted by the LEDES Oversight Committee. The publisher's own spreadsheets could not be opened from the build environment, so wording may differ from the published definitions. The later revised activity and expense codes are not included. Use the client's or the publisher's current list.",
    "task_codes": {
        "L100": "Case Assessment, Development and Administration",
        "L110": "Fact Investigation/Development",
        "L120": "Analysis/Strategy",
        "L130": "Experts/Consultants",
        "L140": "Document/File Management",
        "L150": "Budgeting",
        "L160": "Settlement/Non-Binding ADR",
        "L190": "Other Case Assessment, Development and Administration",
        "L200": "Pre-Trial Pleadings and Motions",
        "L210": "Pleadings",
        "L220": "Preliminary Injunctions/Provisional Remedies",
        "L230": "Court Mandated Conferences",
        "L240": "Dispositive Motions",
        "L250": "Other Written Motions and Submissions",
        "L260": "Class Action Certification and Notice",
        "L300": "Discovery",
        "L310": "Written Discovery",
        "L320": "Document Production",
        "L330": "Depositions",
        "L340": "Expert Discovery",
        "L350": "Discovery Motions",
        "L390": "Other Discovery",
        "L400": "Trial Preparation and Trial",
        "L410": "Fact Witnesses",
        "L420": "Expert Witnesses",
        "L430": "Written Motions and Submissions",
        "L440": "Other Trial Preparation and Support",
        "L450": "Trial and Hearing Attendance",
        "L460": "Post-Trial Motions and Submissions",
        "L470": "Enforcement",
        "L500": "Appeal",
        "L510": "Appellate Motions and Submissions",
        "L520": "Appellate Briefs",
        "L530": "Oral Argument",
    },
    "activity_codes": {
        "A101": "Plan and prepare for",
        "A102": "Research",
        "A103": "Draft/revise",
        "A104": "Review/analyze",
        "A105": "Communicate (in firm)",
        "A106": "Communicate (with client)",
        "A107": "Communicate (other outside counsel)",
        "A108": "Communicate (other external)",
        "A109": "Appear for/attend",
        "A110": "Manage data/files",
        "A111": "Other",
    },
    "expense_codes": {
        "E101": "Copying",
        "E102": "Outside printing",
        "E103": "Word processing",
        "E104": "Facsimile",
        "E105": "Telephone",
        "E106": "Online research",
        "E107": "Delivery services/messengers",
        "E108": "Postage",
        "E109": "Local travel",
        "E110": "Out-of-town travel",
        "E111": "Meals",
        "E112": "Court fees",
        "E113": "Subpoena fees",
        "E114": "Witness fees",
        "E115": "Deposition transcripts",
        "E116": "Trial transcripts",
        "E117": "Trial exhibits",
        "E118": "Litigation support vendors",
        "E119": "Experts",
        "E120": "Private investigators",
        "E121": "Arbitrators/mediators",
        "E122": "Local counsel",
        "E123": "Other professionals",
        "E124": "Other",
    },
}


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def generate(out_dir):
    """Write all synthetic data under out_dir. Returns the answer key dict."""
    rule_ids = {}
    for client_id, spec in CLIENTS.items():
        text = build_document(spec)
        _write(os.path.join(out_dir, "guideline_docs", client_id + ".txt"), text)
        guideline = build_guideline(client_id, spec, text)
        problems = G.validate(guideline)
        assert not problems, problems
        _write(os.path.join(out_dir, "guidelines", client_id + ".json"), G.dumps(guideline))
        rule_ids[client_id] = {r["type"]: r["rule_id"] for r in guideline["rules"]}
        rule_ids[client_id]["ARITH-LINE"] = "ARITH-LINE"
        rule_ids[client_id]["ARITH-TOTAL"] = "ARITH-TOTAL"

    matters = {mid: dict(m, matter_id=mid, approvals=dict(NO_APPROVALS)) for mid, m in MATTERS.items()}
    planted, hard_cases, not_enforced, counts = [], [], [], {}
    for make in BUILDERS:
        b = make()
        invoice, plants, hards = b.build(rule_ids[b.client_id])
        planted += plants
        hard_cases += hards
        for item in b.not_enforced:
            item["rule_id"] = rule_ids[b.client_id]["late_time"]
            item["note"] = "50 days old. The 30 day rule is only proposed, so it must not produce a finding."
            not_enforced.append(item)
        counts[invoice.invoice_id] = len(invoice.lines)
        if b.fmt == "ledes":
            _write(os.path.join(out_dir, "invoices", invoice.invoice_id + ".ledes.txt"), write_ledes([invoice]))
        else:
            _write(os.path.join(out_dir, "invoices", invoice.invoice_id + ".csv"), write_csv([invoice]))
        if invoice.invoice_id == "INV-B-2001":
            total = sum((ln.amount for ln in invoice.lines), D("0"))
            phase = sum((ln.amount for ln in invoice.lines if ln.kind == "fee" and ln.task_code.startswith("L3")), D("0"))
            cap, phase_cap = D("60000.00"), D("20000.00")
            matters["BRW-2026-03"]["budget"] = {
                "cap": format(cap, "f"),
                "billed_to_date": format(cap - total + D("1850.00"), "f"),
                "phases": {
                    "L200": {"cap": "15000.00", "billed_to_date": "4000.00"},
                    "L300": {"cap": format(phase_cap, "f"), "billed_to_date": format(phase_cap - phase + D("640.00"), "f")},
                },
            }
    _write(os.path.join(out_dir, "matters.json"), G.dumps({"note": "Fictional matter records: approved timekeepers, rate cards, approvals and budgets.", "matters": list(matters.values())}))
    _write(os.path.join(out_dir, "waivers.json"), G.dumps({"note": "Fictional client-approved exceptions.", "waivers": WAIVERS}))
    _write(os.path.join(out_dir, "utbms_sample_codes.json"), json.dumps(UTBMS_SAMPLE, indent=2) + "\n")
    key = {
        "note": "Every violation planted in the synthetic invoices by generate_data.py. Fictional data.",
        "seed": SEED,
        "invoice_line_counts": counts,
        "planted": planted,
        "not_enforced": not_enforced,
        "hard_cases_clean": hard_cases,
    }
    _write(os.path.join(out_dir, "ANSWER_KEY.json"), json.dumps(key, indent=2) + "\n")
    return key


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data")
    answer_key = generate(target)
    print("wrote synthetic data to %s" % target)
    print("invoices: %d, planted violations: %d" % (len(answer_key["invoice_line_counts"]), len(answer_key["planted"])))
