"""Check engine: run a client's confirmed rules against a draft invoice.

Every check is deterministic. Findings are prompts for a person. Nothing here
changes an invoice, rewrites a narrative or guesses what a timekeeper did.

Amount at risk
--------------
Each finding carries its own estimate of what the client may not pay:
the full entry for a likely rejection, or the excess over the limit where the
rule sets a limit (hours over a cap, rate over the card, cost over a per-diem).

Totals never count an entry twice. For each entry the amount at risk is the
largest single reduction among its open findings, capped at the entry amount.
Invoice-level findings (budget and phase caps, a total that does not add up)
overlap with entry reductions, because cutting entries also lowers the bill.
So the invoice total at risk is the larger of (a) the sum of per-entry amounts
and (b) the largest invoice-level amount, capped at the sum of the lines.
Waived findings count for nothing.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
import datetime as dt

from . import guidelines as G
from .blockbilling import analyze
from .model import ZERO, dec, fmt_money, fmt_num, money
from .readers import validate_arithmetic
from .waivers import waiver_state

ARITH_LINE = "ARITH-LINE"
ARITH_TOTAL = "ARITH-TOTAL"
HUNDRED = Decimal("100")

_TRAVEL = re.compile(r"\btravel(?:l?ing|led|ed)?\b", re.I)
_RESEARCH = re.compile(r"\bresearch(?:ing|ed)?\b", re.I)
_ATTEND = r"\b(?:attend|attending|attended|appear|appearing|appeared|defend|defending|defended|take|taking|took|participate|participating|participated)\b"
_MEAL = re.compile(r"\b(?:meals?|breakfast|lunch|dinner)\b", re.I)
_LODGING = re.compile(r"\b(?:hotel|lodging|motel)\b", re.I)


def phrase_regex(phrases):
    ordered = sorted((p for p in phrases if p), key=len, reverse=True)
    if not ordered:
        return re.compile(r"(?!x)x")
    return re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(p) for p in ordered), re.I)


def normalize_text(text):
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


@dataclass
class Finding:
    invoice_id: str
    line_no: Optional[int]
    timekeeper_id: str
    timekeeper_name: str
    entry_date: Optional[dt.date]
    entry_amount: Optional[Decimal]
    rule_id: str
    rule_type: str
    rule_label: str
    severity: str
    source_quote: str
    source_ref: str
    explanation: str
    suggested_fix: str
    amount_at_risk: Decimal
    status: str = "open"  # "open" or "waived"
    entry_kind: str = ""
    entry_units: Optional[Decimal] = None
    entry_rate: Optional[Decimal] = None
    entry_narrative: str = ""
    waiver: Optional[dict] = None
    note: str = ""

    @property
    def severity_label(self):
        return G.SEVERITIES[self.severity]

    def to_dict(self):
        return {
            "invoice_id": self.invoice_id,
            "line_no": self.line_no,
            "timekeeper_id": self.timekeeper_id,
            "timekeeper_name": self.timekeeper_name,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "entry_amount": format(money(self.entry_amount), "f") if self.entry_amount is not None else None,
            "entry_kind": self.entry_kind,
            "entry_units": format(self.entry_units, "f") if self.entry_units is not None else None,
            "entry_rate": format(self.entry_rate, "f") if self.entry_rate is not None else None,
            "entry_narrative": self.entry_narrative,
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "rule_label": self.rule_label,
            "severity": self.severity,
            "severity_label": self.severity_label,
            "source_quote": self.source_quote,
            "source_ref": self.source_ref,
            "explanation": self.explanation,
            "suggested_fix": self.suggested_fix,
            "amount_at_risk": format(money(self.amount_at_risk), "f"),
            "status": self.status,
            "waiver": self.waiver,
            "note": self.note,
        }


@dataclass
class CheckResult:
    invoice: object
    guideline: object
    matter: Optional[dict]
    findings: List[Finding] = field(default_factory=list)
    not_checked: List[str] = field(default_factory=list)
    rules_run: List[str] = field(default_factory=list)
    rules_not_enforced: List[str] = field(default_factory=list)
    entry_at_risk: dict = field(default_factory=dict)
    entry_risk_total: Decimal = ZERO
    invoice_level_risk: Decimal = ZERO
    total_at_risk: Decimal = ZERO

    @property
    def open_findings(self):
        return [f for f in self.findings if f.status == "open"]

    @property
    def waived_findings(self):
        return [f for f in self.findings if f.status == "waived"]

    def severity_counts(self):
        counts = {name: 0 for name in G.SEVERITIES}
        for f in self.open_findings:
            counts[f.severity] += 1
        return counts

    def to_dict(self):
        inv = self.invoice
        return {
            "notice": "Personal portfolio demo. Fictional data. Not legal or billing advice.",
            "invoice": {
                "invoice_id": inv.invoice_id,
                "client_id": inv.client_id,
                "client_name": self.guideline.client_name,
                "matter_id": inv.matter_id,
                "invoice_date": inv.invoice_date.isoformat(),
                "declared_total": format(money(inv.declared_total), "f"),
                "line_total": format(money(inv.line_total), "f"),
                "line_count": len(inv.lines),
                "source_format": inv.source_format,
            },
            "totals": {
                "open_findings": len(self.open_findings),
                "waived_findings": len(self.waived_findings),
                "by_severity": self.severity_counts(),
                "entry_risk_total": format(money(self.entry_risk_total), "f"),
                "invoice_level_risk": format(money(self.invoice_level_risk), "f"),
                "total_at_risk": format(money(self.total_at_risk), "f"),
                "at_risk_rule": "Per entry: largest single reduction among open findings, capped at the entry amount. Invoice: the larger of the per-entry sum and the largest invoice-level amount, capped at the sum of the lines.",
            },
            "entry_at_risk": {str(k): format(money(v), "f") for k, v in sorted(self.entry_at_risk.items())},
            "rules_run": self.rules_run,
            "rules_not_enforced": self.rules_not_enforced,
            "not_checked": self.not_checked,
            "findings": [f.to_dict() for f in self.findings],
        }


class _Ctx:
    def __init__(self, invoice, guideline, matter, code_table):
        self.invoice = invoice
        self.guideline = guideline
        self.matter = matter
        self.code_table = code_table
        self.findings = []
        self.not_checked = []
        self.fees = sorted(invoice.fee_lines, key=lambda ln: ln.line_no)
        self.expenses = sorted(invoice.expense_lines, key=lambda ln: ln.line_no)
        self.names = {}
        for ln in self.fees:
            if ln.timekeeper_id and ln.timekeeper_name:
                self.names.setdefault(ln.timekeeper_id, ln.timekeeper_name)

    def card(self, timekeeper_id):
        if not self.matter:
            return None
        return self.matter.get("timekeepers", {}).get(timekeeper_id)

    def approved(self, what):
        return bool(self.matter and self.matter.get("approvals", {}).get(what))

    def skip(self, rule, why):
        self.not_checked.append("%s (%s): %s" % (rule.rule_id, rule.label, why))

    def add(self, rule, line, amount, explanation, fix, timekeeper_id="", severity=None, note=""):
        amount = money(max(dec(amount), ZERO))
        if line is not None:
            amount = min(amount, money(max(line.amount, ZERO)))
            timekeeper_id = line.timekeeper_id
        self.findings.append(
            Finding(
                invoice_id=self.invoice.invoice_id,
                line_no=line.line_no if line is not None else None,
                timekeeper_id=timekeeper_id,
                timekeeper_name=(line.timekeeper_name if line is not None else "") or self.names.get(timekeeper_id, ""),
                entry_date=line.date if line is not None else None,
                entry_amount=line.amount if line is not None else None,
                rule_id=rule.rule_id,
                rule_type=rule.type,
                rule_label=rule.label,
                severity=severity or rule.severity,
                source_quote=rule.source_quote,
                source_ref=rule.source_ref,
                explanation=explanation,
                suggested_fix=fix,
                amount_at_risk=amount,
                note=note,
                entry_kind=line.kind if line is not None else "",
                entry_units=line.units if line is not None else None,
                entry_rate=line.rate if line is not None else None,
                entry_narrative=line.narrative if line is not None else "",
            )
        )


# ---------------------------------------------------------------- checks


def chk_block_billing(ctx, rule):
    max_tasks = rule.params["max_tasks"]
    min_hours = dec(rule.params["min_hours"])
    for ln in ctx.fees:
        if ln.units <= min_hours:
            continue
        result = analyze(ln.narrative)
        count = result["task_count"]
        if count > max_tasks:
            listing = " ".join("(%d) %s." % (i, t) for i, t in enumerate(result["tasks"], 1))
            ctx.add(
                rule,
                ln,
                ln.amount,
                "The narrative appears to describe %d tasks under one time total of %s hours." % (count, fmt_num(ln.units)),
                "Ask the timekeeper to enter each task on its own line with its own time. "
                "Tasks the check detected: %s The tool does not know how the time divides between them "
                "and does not rewrite the narrative." % listing,
            )


def chk_minimum_increment(ctx, rule):
    increment = dec(rule.params["increment"])
    for ln in ctx.fees:
        if ln.units % increment != 0:
            ctx.add(
                rule,
                ln,
                ln.amount,
                "%s hours is not a multiple of the %s hour increment." % (fmt_num(ln.units), fmt_num(increment)),
                "Ask the timekeeper to restate the time in %s hour increments from their own records." % fmt_num(increment),
            )


def chk_rounding_pattern(ctx, rule):
    block = dec(rule.params["block"])
    min_entries = rule.params["min_entries"]
    threshold = dec(rule.params["threshold_percent"])
    by_tk = defaultdict(list)
    for ln in ctx.fees:
        by_tk[ln.timekeeper_id].append(ln)
    for tk, lines in sorted(by_tk.items()):
        if len(lines) < min_entries:
            continue
        rounded = [ln for ln in lines if ln.units % block == 0]
        share = Decimal(len(rounded)) * HUNDRED / Decimal(len(lines))
        if share >= threshold:
            ctx.add(
                rule,
                None,
                ZERO,
                "%d of %d entries by this timekeeper are whole multiples of %s hour. The pattern suggests time may be rounded up."
                % (len(rounded), len(lines), fmt_num(block)),
                "Ask the timekeeper to confirm these entries against contemporaneous records. Amount at risk is not quantified.",
                timekeeper_id=tk,
            )


def chk_daily_hour_cap(ctx, rule):
    cap = dec(rule.params["max_hours"])
    by_day = defaultdict(list)
    for ln in ctx.fees:
        by_day[(ln.timekeeper_id, ln.date)].append(ln)
    for (tk, day), lines in sorted(by_day.items()):
        total = sum((ln.units for ln in lines), ZERO)
        if total <= cap:
            continue
        running = ZERO
        for ln in lines:
            before = running
            running += ln.units
            if running <= cap:
                continue
            excess = running - max(before, cap)
            ctx.add(
                rule,
                ln,
                excess * ln.rate,
                "This timekeeper has %s hours on %s. The limit is %s hours in a day; %s hours of this entry fall over it."
                % (fmt_num(total), day.isoformat(), fmt_num(cap), fmt_num(excess)),
                "Confirm the day's entries with the timekeeper. If the time is right, add the explanation the client asks for or seek approval.",
            )


def chk_staffing_matter_limit(ctx, rule):
    limit = rule.params["max_timekeepers"]
    tks = sorted({ln.timekeeper_id for ln in ctx.fees if ln.timekeeper_id})
    if len(tks) > limit and not ctx.approved("staffing"):
        ctx.add(
            rule,
            None,
            ZERO,
            "%d timekeepers billed to this matter in this invoice (%s). The limit without approval is %d."
            % (len(tks), ", ".join(tks), limit),
            "Check whether the client approved the added timekeeper. If so, record the approval. Amount at risk is not quantified.",
        )


def chk_staffing_event_limit(ctx, rule):
    limit = rule.params["max_attendees"]
    events = [e.lower() for e in rule.params["events"]]
    groups = defaultdict(list)
    for ln in ctx.fees:
        for event in events:
            if re.search(_ATTEND + r"[^.;]*\b" + re.escape(event) + r"s?\b", ln.narrative, re.I):
                groups[(ln.date, event)].append(ln)
                break
    for (day, event), lines in sorted(groups.items()):
        by_tk = {}
        for ln in lines:
            by_tk.setdefault(ln.timekeeper_id, []).append(ln)
        if len(by_tk) <= limit:
            continue
        ranked = sorted(by_tk, key=lambda tk: (-max(ln.rate for ln in by_tk[tk]), min(ln.line_no for ln in by_tk[tk])))
        for tk in ranked[limit:]:
            for ln in by_tk[tk]:
                ctx.add(
                    rule,
                    ln,
                    ln.amount,
                    "%d timekeepers billed for attending a %s on %s. The limit is %d. "
                    "The check keeps the highest-rate attendee(s) and flags the rest; that choice is an assumption."
                    % (len(by_tk), event, day.isoformat(), limit),
                    "Decide which attendance to bill, or record the client's approval of the additional attendee.",
                )


def chk_unapproved_timekeeper(ctx, rule):
    if not ctx.matter:
        ctx.skip(rule, "no matter record with an approved timekeeper list was supplied")
        return
    for ln in ctx.fees:
        if ctx.card(ln.timekeeper_id) is None:
            ctx.add(
                rule,
                ln,
                ln.amount,
                "Timekeeper %s (%s) is not on the approved list for this matter." % (ln.timekeeper_id, ln.timekeeper_name or "no name"),
                "Ask the client to approve the timekeeper before the bill goes out, or move the time off the bill.",
            )


def chk_rate_above_card(ctx, rule):
    if not ctx.matter:
        ctx.skip(rule, "no matter record with a rate card was supplied")
        return
    for ln in ctx.fees:
        card = ctx.card(ln.timekeeper_id)
        if card is None:
            continue
        approved = dec(card["approved_rate"])
        if ln.rate > approved:
            ctx.add(
                rule,
                ln,
                (ln.rate - approved) * ln.units,
                "Billed at %s an hour. The approved rate for this timekeeper is %s." % (fmt_money(ln.rate), fmt_money(approved)),
                "Correct the rate to the approved rate card, or attach the client's approval of the higher rate.",
            )


def chk_rate_increase_notice(ctx, rule):
    if not ctx.matter:
        ctx.skip(rule, "no matter record with prior rates was supplied")
        return
    notice_days = rule.params["notice_days"]
    card_rule = ctx.guideline.rule_of_type("rate_above_card")
    card_rule = card_rule is not None and card_rule.confirmed
    for ln in ctx.fees:
        card = ctx.card(ln.timekeeper_id)
        if card is None or card.get("last_billed_rate") in (None, ""):
            continue
        last = dec(card["last_billed_rate"])
        if ln.rate <= last:
            continue
        if card_rule and ln.rate > dec(card["approved_rate"]):
            continue  # already reported once, by the rate card rule
        notice = card.get("rate_notice_date")
        if notice:
            notice_date = dt.date.fromisoformat(notice)
            effective = notice_date + dt.timedelta(days=notice_days)
            if ln.date >= effective:
                continue
            detail = "Notice was given on %s, so the new rate applies from %s." % (notice_date.isoformat(), effective.isoformat())
        else:
            detail = "No notice of a rate increase is on record for this timekeeper."
        ctx.add(
            rule,
            ln,
            (ln.rate - last) * ln.units,
            "Billed at %s an hour; the last billed rate was %s. %s" % (fmt_money(ln.rate), fmt_money(last), detail),
            "Bill this entry at the prior rate, or record the notice the client received.",
        )


def chk_non_billable_task(ctx, rule):
    compiled = [(name, phrase_regex(phrases)) for name, phrases in rule.params["categories"].items()]
    for ln in ctx.fees:
        for name, regex in compiled:
            match = regex.search(ln.narrative)
            if match:
                ctx.add(
                    rule,
                    ln,
                    ln.amount,
                    'The narrative contains "%s", which is on this client\'s list of non-billable %s work.'
                    % (match.group(0), name.replace("_", " ")),
                    "Move the entry off the bill, or ask the timekeeper whether the description is accurate.",
                )
                break


def _is_internal_conference(ln, rule):
    phrases = rule.params.get("phrases") or G.DEFAULT_INTERNAL_CONFERENCE_PHRASES
    return ln.activity_code.upper() == "A105" or bool(phrase_regex(phrases).search(ln.narrative))


def chk_internal_conference_limit(ctx, rule):
    limit = dec(rule.params["max_hours_per_entry"])
    for ln in ctx.fees:
        if _is_internal_conference(ln, rule) and ln.units > limit:
            ctx.add(
                rule,
                ln,
                (ln.units - limit) * ln.rate,
                "Internal conference of %s hours. The limit is %s hours per entry." % (fmt_num(ln.units), fmt_num(limit)),
                "Reduce the entry to the limit, or ask the client to approve the longer conference.",
            )


def chk_research_approval(ctx, rule):
    if ctx.approved("research"):
        return
    limit = dec(rule.params["max_hours"])
    running = ZERO
    lines = [ln for ln in ctx.fees if ln.activity_code.upper() == "A102" or _RESEARCH.search(ln.narrative)]
    for ln in sorted(lines, key=lambda l: (l.date, l.line_no)):
        before = running
        running += ln.units
        if running <= limit:
            continue
        excess = running - max(before, limit)
        ctx.add(
            rule,
            ln,
            excess * ln.rate,
            "Research on this invoice reaches %s hours with this entry. The limit without approval is %s hours; %s hours of this entry fall over it."
            % (fmt_num(running), fmt_num(limit), fmt_num(excess)),
            "Ask the client to approve the research, or hold the excess time. Research billed on earlier invoices is not counted here.",
        )


def chk_travel_time(ctx, rule):
    percent = dec(rule.params["billable_percent"])
    needs_approval = rule.params["requires_approval"]
    for ln in ctx.fees:
        if not _TRAVEL.search(ln.narrative):
            continue
        if needs_approval and not ctx.approved("travel"):
            ctx.add(
                rule,
                ln,
                ln.amount,
                "Travel time with no client approval on record for this matter.",
                "Obtain and record the client's approval, or move the travel time off the bill.",
                severity="reject",
            )
            continue
        if percent >= HUNDRED:
            continue
        card = ctx.card(ln.timekeeper_id)
        if card is not None:
            reference = dec(card["approved_rate"])
            basis = "approved rate"
        else:
            reference = max(l.rate for l in ctx.fees if l.timekeeper_id == ln.timekeeper_id)
            basis = "highest rate billed by this timekeeper on the invoice"
        allowed = reference * percent / HUNDRED
        if ln.rate > allowed:
            ctx.add(
                rule,
                ln,
                (ln.rate - allowed) * ln.units,
                "Travel time billed at %s an hour. The client pays travel at %s%% of the %s (%s)."
                % (fmt_money(ln.rate), fmt_num(percent), basis, fmt_money(allowed)),
                "Bill the travel time at the reduced rate.",
            )


def chk_expense_overhead(ctx, rule):
    codes = {c.upper() for c in rule.params["codes"]}
    regex = phrase_regex(rule.params["phrases"])
    for ln in ctx.expenses:
        match = regex.search(ln.narrative)
        if ln.expense_code.upper() in codes or match:
            reason = 'expense code %s' % ln.expense_code if ln.expense_code.upper() in codes else '"%s"' % match.group(0)
            ctx.add(
                rule,
                ln,
                ln.amount,
                "This expense looks like an overhead item the client does not reimburse (%s)." % reason,
                "Remove the expense from the bill.",
            )


def chk_expense_receipt_threshold(ctx, rule):
    threshold = dec(rule.params["threshold"])
    inclusive = rule.params.get("inclusive", True)
    unknown = 0
    for ln in ctx.expenses:
        over = ln.amount >= threshold if inclusive else ln.amount > threshold
        if not over:
            continue
        if ln.receipt is None:
            unknown += 1
        elif ln.receipt is False:
            ctx.add(
                rule,
                ln,
                ln.amount,
                "Expense of %s has no receipt attached. The client asks for a receipt at %s%s."
                % (fmt_money(ln.amount), fmt_money(threshold), " or more" if inclusive else " and above (exclusive)"),
                "Attach the receipt before the bill goes out.",
            )
    if unknown:
        ctx.skip(rule, "%d expense line(s) at or over the threshold could not be checked because the file does not say whether a receipt is attached" % unknown)


def chk_expense_per_diem(ctx, rule):
    caps = rule.params["caps"]
    for ln in ctx.expenses:
        kind = None
        if "meal" in caps and (ln.expense_code.upper() == "E111" or _MEAL.search(ln.narrative)):
            kind = "meal"
        elif "lodging" in caps and _LODGING.search(ln.narrative):
            kind = "lodging"
        if kind is None:
            continue
        cap = dec(caps[kind])
        if ln.rate > cap:
            ctx.add(
                rule,
                ln,
                (ln.rate - cap) * ln.units,
                "The %s cost of %s per unit is over the client's cap of %s." % (kind, fmt_money(ln.rate), fmt_money(cap)),
                "Reduce the expense to the cap. The check reads each unit as one person-day (meals) or one night (lodging).",
            )


def chk_expense_markup(ctx, rule):
    unknown = 0
    for ln in ctx.expenses:
        if ln.cost is None:
            unknown += 1
        elif ln.amount > ln.cost:
            ctx.add(
                rule,
                ln,
                ln.amount - ln.cost,
                "Billed at %s; the recorded cost is %s." % (fmt_money(ln.amount), fmt_money(ln.cost)),
                "Bill the expense at cost.",
            )
    if unknown:
        ctx.skip(rule, "%d expense line(s) could not be checked for mark-up because the file has no cost for them" % unknown)


def chk_vague_description(ctx, rule):
    always = phrase_regex(rule.params["always_phrases"])
    bare = {normalize_text(p) for p in rule.params["bare_phrases"]}
    min_words = rule.params.get("min_words", 3)
    for ln in ctx.fees:
        text = normalize_text(ln.narrative)
        match = always.search(ln.narrative)
        if match:
            reason = 'It contains "%s", a phrase on the client\'s list of vague descriptions.' % match.group(0)
        elif text in bare:
            reason = 'It is only "%s", with no subject or purpose.' % ln.narrative.strip()
        elif len(text.split()) < min_words:
            reason = "It has fewer than %d words." % min_words
        else:
            continue
        ctx.add(
            rule,
            ln,
            ln.amount,
            "The description does not say what was done. " + reason,
            "Ask the timekeeper to say what was reviewed or done and for what purpose. Do not fill this in for them.",
        )


def chk_required_codes(ctx, rule):
    p = rule.params
    table = ctx.code_table if p.get("check_against_sample_table") else None
    for ln in ctx.fees:
        missing = []
        if p["require_task"] and not ln.task_code:
            missing.append("task code")
        if p["require_activity"] and not ln.activity_code:
            missing.append("activity code")
        unknown = []
        if table:
            if ln.task_code and ln.task_code.upper() not in table["task"]:
                unknown.append("task code %s" % ln.task_code)
            if ln.activity_code and ln.activity_code.upper() not in table["activity"]:
                unknown.append("activity code %s" % ln.activity_code)
        _codes_finding(ctx, rule, ln, missing, unknown)
    for ln in ctx.expenses:
        missing = ["expense code"] if p["require_expense"] and not ln.expense_code else []
        unknown = []
        if table and ln.expense_code and ln.expense_code.upper() not in table["expense"]:
            unknown.append("expense code %s" % ln.expense_code)
        _codes_finding(ctx, rule, ln, missing, unknown)


def _codes_finding(ctx, rule, ln, missing, unknown):
    if missing:
        ctx.add(
            rule,
            ln,
            ln.amount,
            "The entry has no %s." % " or ".join(missing),
            "Add the missing code. The timekeeper or billing staff should choose it; the check does not guess.",
        )
    elif unknown:
        ctx.add(
            rule,
            ln,
            ZERO,
            "Not in the sample code table: %s. The table is a subset and unverified, so this may be a valid code." % ", ".join(unknown),
            "Check the code against the client's code list.",
            severity="review",
        )


def chk_late_time(ctx, rule):
    max_age = rule.params["max_age_days"]
    for ln in ctx.fees:
        age = (ctx.invoice.invoice_date - ln.date).days
        if age > max_age:
            ctx.add(
                rule,
                ln,
                ln.amount,
                "The work is dated %s, %d days before the invoice date. The limit is %d days."
                % (ln.date.isoformat(), age, max_age),
                "Ask the client whether it will accept the late time, or write it off.",
            )


def chk_budget_cap(ctx, rule):
    budget = (ctx.matter or {}).get("budget") or {}
    if not budget.get("cap"):
        ctx.skip(rule, "no budget cap is recorded for this matter")
        return
    cap = dec(budget["cap"])
    billed = dec(budget.get("billed_to_date", 0))
    total = ctx.invoice.line_total
    over = billed + total - cap
    if over > ZERO:
        ctx.add(
            rule,
            None,
            min(over, total),
            "Billed to date (%s) plus this invoice (%s) is %s. The cap is %s, so %s is over it."
            % (fmt_money(billed), fmt_money(total), fmt_money(billed + total), fmt_money(cap), fmt_money(over)),
            "Raise the overage with the client before sending the bill. An amendment or written approval may be needed.",
        )


def chk_phase_cap(ctx, rule):
    phases = ((ctx.matter or {}).get("budget") or {}).get("phases") or {}
    if not phases:
        ctx.skip(rule, "no phase budget is recorded for this matter")
        return
    sums = defaultdict(lambda: ZERO)
    for ln in ctx.fees:
        code = ln.task_code.upper()
        if len(code) >= 2:
            sums[code[:2] + "00"] += ln.amount
    for phase in sorted(phases):
        cap = dec(phases[phase]["cap"])
        billed = dec(phases[phase].get("billed_to_date", 0))
        this = sums.get(phase, ZERO)
        over = billed + this - cap
        if this > ZERO and over > ZERO:
            ctx.add(
                rule,
                None,
                min(over, this),
                "Phase %s: billed to date (%s) plus this invoice (%s) is %s over the phase amount of %s."
                % (phase, fmt_money(billed), fmt_money(this), fmt_money(over), fmt_money(cap)),
                "Raise the phase overage with the client before sending the bill.",
                note="phase %s" % phase,
            )


def chk_duplicate_entries(ctx, rule):
    seen = {}
    for ln in sorted(ctx.fees + ctx.expenses, key=lambda l: l.line_no):
        key = (ln.kind, ln.timekeeper_id, ln.date, ln.units, ln.rate, normalize_text(ln.narrative))
        if key in seen:
            ctx.add(
                rule,
                ln,
                ln.amount,
                "Same timekeeper, date, quantity and description as line %d." % seen[key],
                "Confirm with the timekeeper whether the work was done twice. If not, remove one entry.",
            )
        else:
            seen[key] = ln.line_no


def _ai_related(ln, rule):
    if ln.ai_assisted is True:
        return True
    marker = rule.params["disclosure_marker"]
    if marker.lower() in ln.narrative.lower():
        return True
    return bool(phrase_regex(rule.params["ai_terms"]).search(ln.narrative))


def _ai_flag_note(ctx, rule):
    if any(ln.ai_assisted is None for ln in ctx.fees):
        ctx.skip(rule, "the file has no AI-assisted flag for some entries, so only the narrative text was checked for them")


def chk_ai_disclosure_required(ctx, rule):
    marker = rule.params["disclosure_marker"]
    _ai_flag_note(ctx, rule)
    for ln in ctx.fees:
        if _ai_related(ln, rule) and marker.lower() not in ln.narrative.lower():
            source = "is flagged as AI-assisted in the time system" if ln.ai_assisted else "mentions an AI tool"
            ctx.add(
                rule,
                ln,
                ln.amount,
                'The entry %s but the narrative does not carry the client\'s disclosure marker "%s".' % (source, marker),
                'Confirm with the timekeeper whether AI assistance was used. If so, add "%s" to the entry.' % marker,
            )


def chk_ai_nonpayable_task(ctx, rule):
    regex = phrase_regex(rule.params["task_phrases"])
    for ln in ctx.fees:
        if not _ai_related(ln, rule):
            continue
        match = regex.search(ln.narrative)
        if match:
            ctx.add(
                rule,
                ln,
                ln.amount,
                'The entry is AI-assisted and describes a task ("%s") that this client\'s terms say it will not pay for when AI-assisted.'
                % match.group(0),
                "Move the entry off the bill, or raise it with the client before billing.",
            )


CHECKS = {
    "block_billing": chk_block_billing,
    "minimum_increment": chk_minimum_increment,
    "rounding_pattern": chk_rounding_pattern,
    "daily_hour_cap": chk_daily_hour_cap,
    "staffing_matter_limit": chk_staffing_matter_limit,
    "staffing_event_limit": chk_staffing_event_limit,
    "unapproved_timekeeper": chk_unapproved_timekeeper,
    "rate_above_card": chk_rate_above_card,
    "rate_increase_notice": chk_rate_increase_notice,
    "non_billable_task": chk_non_billable_task,
    "internal_conference_limit": chk_internal_conference_limit,
    "research_approval": chk_research_approval,
    "travel_time": chk_travel_time,
    "expense_overhead": chk_expense_overhead,
    "expense_receipt_threshold": chk_expense_receipt_threshold,
    "expense_per_diem": chk_expense_per_diem,
    "expense_markup": chk_expense_markup,
    "vague_description": chk_vague_description,
    "required_codes": chk_required_codes,
    "late_time": chk_late_time,
    "budget_cap": chk_budget_cap,
    "phase_cap": chk_phase_cap,
    "duplicate_entries": chk_duplicate_entries,
    "ai_disclosure_required": chk_ai_disclosure_required,
    "ai_nonpayable_task": chk_ai_nonpayable_task,
}


def _arithmetic_rule(rule_id, quote):
    return G.Rule(
        rule_id=rule_id,
        type="arithmetic",
        status="confirmed",
        severity="reject",
        params={},
        source_quote=quote,
        source_ref="built-in file check, not a client rule",
    )


def _arithmetic(ctx):
    lines = {ln.line_no: ln for ln in ctx.invoice.lines}
    for issue in validate_arithmetic(ctx.invoice):
        if issue["scope"] == "line":
            ln = lines[issue["line_no"]]
            rule = _arithmetic_rule(ARITH_LINE, "Units times rate, plus any adjustment, must equal the line amount within one cent.")
            ctx.add(
                rule,
                ln,
                abs(issue["difference"]),
                "%s x %s%s is %s, but the line amount is %s (difference %s)."
                % (
                    fmt_num(ln.units),
                    fmt_money(ln.rate),
                    " plus adjustment %s" % fmt_money(ln.adjustment) if ln.adjustment else "",
                    fmt_money(issue["expected"]),
                    fmt_money(issue["stated"]),
                    fmt_money(abs(issue["difference"])),
                ),
                "Correct the line in the billing system. An e-billing system is likely to reject a file that does not add up.",
            )
        else:
            rule = _arithmetic_rule(ARITH_TOTAL, "The line amounts must add up to the invoice total within one cent.")
            ctx.add(
                rule,
                None,
                abs(issue["difference"]),
                "The lines add up to %s, but the invoice total is stated as %s (difference %s)."
                % (fmt_money(issue["expected"]), fmt_money(issue["stated"]), fmt_money(abs(issue["difference"]))),
                "Correct the invoice total in the billing system.",
            )


def check_invoice(invoice, guideline, matter=None, waivers=(), code_table=None):
    """Run every confirmed rule in the guideline against the invoice."""
    if guideline.client_id != invoice.client_id:
        raise ValueError(
            "invoice %s is for client %r but the guideline is for %r"
            % (invoice.invoice_id, invoice.client_id, guideline.client_id)
        )
    ctx = _Ctx(invoice, guideline, matter, code_table)
    result = CheckResult(invoice=invoice, guideline=guideline, matter=matter)
    _arithmetic(ctx)
    for rule in guideline.rules:
        if not rule.confirmed:
            result.rules_not_enforced.append(rule.rule_id)
            continue
        CHECKS[rule.type](ctx, rule)
        result.rules_run.append(rule.rule_id)
    for finding in ctx.findings:
        for waiver in waivers:
            state = waiver_state(waiver, finding, invoice)
            if state == "applies":
                finding.status = "waived"
                finding.waiver = waiver.to_dict()
                finding.note = (finding.note + " " if finding.note else "") + "Waived: %s approved on %s (%s). Expires %s." % (
                    waiver.approved_by,
                    waiver.approved_on.isoformat(),
                    waiver.reference,
                    waiver.expires_on.isoformat(),
                )
                break
            if state == "expired":
                finding.note = (finding.note + " " if finding.note else "") + "Waiver %s expired on %s and does not cover this work." % (
                    waiver.waiver_id,
                    waiver.expires_on.isoformat(),
                )
    ctx.findings.sort(
        key=lambda f: (
            G.SEVERITY_ORDER[f.severity],
            f.line_no if f.line_no is not None else -1,
            f.rule_id,
            f.timekeeper_id,
        )
    )
    result.findings = ctx.findings
    result.not_checked = ctx.not_checked
    _total_risk(result)
    return result


def _total_risk(result):
    per_entry = {}
    invoice_level = ZERO
    for f in result.findings:
        if f.status != "open":
            continue
        if f.line_no is None:
            invoice_level = max(invoice_level, f.amount_at_risk)
        else:
            per_entry[f.line_no] = max(per_entry.get(f.line_no, ZERO), f.amount_at_risk)
    amounts = {ln.line_no: ln.amount for ln in result.invoice.lines}
    for line_no in per_entry:
        per_entry[line_no] = money(min(per_entry[line_no], max(amounts.get(line_no, ZERO), ZERO)))
    entry_total = sum(per_entry.values(), ZERO)
    ceiling = max(result.invoice.line_total, ZERO)
    result.entry_at_risk = per_entry
    result.entry_risk_total = money(entry_total)
    result.invoice_level_risk = money(invoice_level)
    result.total_at_risk = money(min(max(entry_total, invoice_level), ceiling))
