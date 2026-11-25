"""Prop 218 protest tabulator and AB 2257 objection gate.

Portfolio demo. Fictional data only. Not legal advice and not a firm tool.
Every legal number comes from rules.json, which records its source and
verification status. Standard library only; all logic is deterministic.

Three parts:
  1. tally_fee_protests   - art. XIII D § 6 written protests, one per parcel
  2. tally_assessment     - art. XIII D § 4 ballots, weighted by assessment amount
  3. check_calendar / objection_gate - Gov. Code §§ 53759, 53759.1, 53759.2
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- rules

def load_rules(path: Path | None = None) -> dict:
    with open(path or HERE / "rules.json", encoding="utf-8") as f:
        return json.load(f)


def rule(rules: dict, key: str):
    return rules["rules"][key]["value"]


def cite(rules: dict, key: str) -> str:
    return rules["rules"][key]["source"]


# ---------------------------------------------------------------- normalizing

_SUFFIXES = {"JR", "SR", "II", "III", "IV"}
_STREET = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN",
           "COURT": "CT", "BOULEVARD": "BLVD", "PLACE": "PL", "WAY": "WAY",
           "APARTMENT": "UNIT", "APT": "UNIT", "SUITE": "UNIT", "STE": "UNIT", "#": "UNIT"}


def norm_apn(s: str) -> str:
    """Digits and letters only, so '901-020-007', '901 020 007' and '901020007' match."""
    return re.sub(r"[^0-9A-Z]", "", (s or "").upper())


def split_apns(s: str) -> list[str]:
    return [a for a in (norm_apn(p) for p in re.split(r"[;,]", s or "")) if a]


def name_tokens(s: str) -> frozenset[str]:
    toks = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()
    return frozenset(t for t in toks if len(t) > 1 and t not in _SUFFIXES)


def names_match(a: str, b: str) -> bool:
    """True when one name's tokens contain the other's and at least two tokens agree.
    'Okafor, Daniel R.' matches 'Daniel Okafor'. A surname alone does not match."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) >= 2 and (ta <= tb or tb <= ta)


def norm_address(s: str) -> str:
    toks = re.sub(r"[^A-Z0-9# ]", " ", (s or "").upper()).replace("#", " # ").split()
    return " ".join(_STREET.get(t, t) for t in toks)


def parse_dt(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    return datetime.fromisoformat(s if "T" in s or " " in s else s + "T00:00:00")


def parse_date(s: str) -> date | None:
    d = parse_dt(s)
    return d.date() if d else None


def truthy(s) -> bool:
    return str(s).strip().lower() in {"1", "y", "yes", "true"}


# ---------------------------------------------------------------- § 6 fee protests

@dataclass
class Line:
    """One submission applied to one parcel. The audit log is a list of these."""
    submission_id: str
    received: str
    apn: str
    signer: str
    status: str
    reason: str
    resolved_by: str = ""


def majority_threshold(n_parcels: int) -> int:
    """Smallest whole number of parcels that is more than half of n."""
    return n_parcels // 2 + 1


def _index_parcels(parcels: list[dict], accounts: list[dict]):
    by_apn = {norm_apn(p["apn"]): p for p in parcels}
    by_acct = {a["account_no"].strip().upper(): a for a in accounts}
    by_addr: dict[str, set[str]] = {}
    for p in parcels:
        by_addr.setdefault(norm_address(p.get("situs_address", "")), set()).add(norm_apn(p["apn"]))
    for a in accounts:
        by_addr.setdefault(norm_address(a.get("service_address", "")), set()).add(norm_apn(a["apn"]))
    by_addr.pop("", None)
    accts_by_apn: dict[str, list[dict]] = {}
    for a in accounts:
        accts_by_apn.setdefault(norm_apn(a["apn"]), []).append(a)
    return by_apn, by_acct, by_addr, accts_by_apn


def _resolve(sub: dict, by_apn, by_acct, by_addr) -> tuple[list[str], str, str]:
    """Find the parcel(s) a submission is about. Order: APN, account number, address.
    Returns (apns, how, problem). An address shared by two parcels is not resolved."""
    apns = split_apns(sub.get("apn_as_written", ""))
    if apns:
        return apns, "apn", ""
    acct = (sub.get("account_no") or "").strip().upper()
    if acct:
        if acct in by_acct:
            return [norm_apn(by_acct[acct]["apn"])], "account", ""
        return [], "", "account number not found"
    addr = norm_address(sub.get("service_address", ""))
    if addr:
        hits = by_addr.get(addr, set())
        if len(hits) == 1:
            return [next(iter(hits))], "address", ""
        return [], "", "address matches %d parcels" % len(hits)
    return [], "", "no parcel, account, or address given"


def _eligibility(signer: str, parcel: dict, accts: list[dict], policy: dict) -> str:
    """'owner', 'tenant', or '' when the signer is on neither the roll nor an account."""
    for owner in parcel.get("record_owners", "").split("|"):
        if names_match(signer, owner):
            return "owner"
    for a in accts:
        if names_match(signer, a.get("customer_name", "")):
            if a.get("customer_role", "").lower() == "owner":
                return "owner"
            if a.get("customer_role", "").lower() == "tenant":
                return "tenant"
    return ""


def tally_fee_protests(parcels: list[dict], accounts: list[dict], submissions: list[dict],
                       hearing_close: datetime, rules: dict, policy: dict | None = None) -> dict:
    """Count § 6 written protests. One counted protest per identified parcel
    (Gov. Code § 53755(b)); majority is measured against all identified parcels
    (art. XIII D § 6(a)(2))."""
    policy = {**rules["agency_policy_defaults"], **(policy or {})}
    by_apn, by_acct, by_addr, accts_by_apn = _index_parcels(parcels, accounts)
    identified = {a for a, p in by_apn.items() if truthy(p.get("identified", "Y"))}
    n = len(identified)
    threshold = majority_threshold(n)

    lines: list[Line] = []
    active: dict[str, dict[frozenset, Line]] = {}   # apn -> signer -> live protest
    review_parcels: set[str] = set()                 # parcels that only a review item could add
    unresolved_review = 0

    ordered = sorted(submissions, key=lambda s: (parse_dt(s["received"]) or datetime.max, s["submission_id"]))
    for sub in ordered:
        sid, signer = sub["submission_id"], sub.get("signer_name", "")
        received = parse_dt(sub["received"])
        action = (sub.get("action") or "protest").lower()

        def add(apn, status, reason, how=""):
            ln = Line(sid, sub["received"], apn, signer, status, reason, how)
            lines.append(ln)
            return ln

        # Form checks apply to the whole submission.
        if sub.get("channel", "").lower() not in policy["accepted_channels"]:
            add("", "INVALID", "channel '%s' is not an accepted written channel (agency policy)" % sub.get("channel", ""))
            continue
        if received is None or received > hearing_close:
            add("", "INVALID", "received after the close of the hearing")
            continue
        if policy["require_signature"] and not truthy(sub.get("signed", "")):
            add("", "INVALID", "not signed (agency policy)")
            continue

        apns, how, problem = _resolve(sub, by_apn, by_acct, by_addr)
        if not apns:
            add("", "REVIEW", "parcel not resolved: " + problem)
            if action == "protest":
                unresolved_review += 1
            continue

        for apn in apns:
            if apn not in by_apn:
                add(apn, "REVIEW", "APN is not on the parcel roll", how)
                if action == "protest":
                    unresolved_review += 1
                continue
            if apn not in identified:
                add(apn, "NOT_COUNTED", "parcel is on the roll but is not an identified parcel for this fee", how)
                continue
            role = _eligibility(signer, by_apn[apn], accts_by_apn.get(apn, []), policy)
            key = name_tokens(signer)
            if action == "withdraw":
                if not policy["allow_withdrawal"]:
                    add(apn, "NOT_COUNTED", "withdrawals are not accepted (agency policy)", how)
                    continue
                prior = [k for k in active.get(apn, {}) if names_match(" ".join(k), signer) or k == key]
                if not prior:
                    add(apn, "NOT_COUNTED", "withdrawal with no earlier protest by this signer for the parcel", how)
                    continue
                for k in prior:
                    old = active[apn].pop(k)
                    old.status, old.reason = "WITHDRAWN", "withdrawn by %s" % sid
                add(apn, "WITHDRAWAL_APPLIED", "removed this signer's earlier protest", how)
                continue
            if not role:
                add(apn, "REVIEW", "signer is not a record owner or a customer of record for the parcel", how)
                review_parcels.add(apn)
                continue
            ln = add(apn, "PENDING", "%s of the parcel" % role, how)
            if key in active.setdefault(apn, {}):
                ln.status, ln.reason = "DUPLICATE", "same signer already protested for this parcel"
            else:
                active[apn][key] = ln

    counted_parcels = set()
    for apn, live in active.items():
        first = True
        for ln in live.values():           # insertion order is receipt order
            if ln.status != "PENDING":
                continue
            if first:
                ln.status, ln.reason = "COUNTED", ln.reason + "; first valid protest for the parcel"
                counted_parcels.add(apn)
                first = False
            else:
                ln.status = "DUPLICATE"
                ln.reason = "parcel already counted once (Gov. Code § 53755(b)); " + ln.reason

    counted = len(counted_parcels)
    possible_extra = len(review_parcels - counted_parcels) + unresolved_review
    if counted >= threshold:
        outcome = "MAJORITY_PROTEST"
    elif counted + possible_extra >= threshold:
        outcome = "UNDETERMINED_PENDING_REVIEW"
    else:
        outcome = "NO_MAJORITY_PROTEST"

    by_status: dict[str, int] = {}
    for ln in lines:
        by_status[ln.status] = by_status.get(ln.status, 0) + 1
    return {
        "identified_parcels": n,
        "threshold": threshold,
        "threshold_rule": cite(rules, "fee_majority_protest"),
        "counted_protests": counted,
        "review_items_that_could_add_a_parcel": possible_extra,
        "max_possible_protests": counted + possible_extra,
        "outcome": outcome,
        "shortfall_to_majority": max(0, threshold - counted),
        "submissions_received": len(submissions),
        "lines_by_status": dict(sorted(by_status.items())),
        "lines": lines,
    }


# ---------------------------------------------------------------- § 4 assessment ballots

def tally_assessment(parcels: list[dict], ballots: list[dict], testimony_close: datetime) -> dict:
    """Weighted § 4 ballot tally. Majority protest when weighted 'no' exceeds weighted 'yes'
    among ballots submitted and not withdrawn (art. XIII D § 4(e); Gov. Code § 53753(e)).
    parcels: apn, assessment_cents, owners as 'Name:interest|Name:interest' (interest optional).
    ballots: ballot_id, received, apn, owner_name, vote (yes/no/withdraw), signed."""
    by_apn = {norm_apn(p["apn"]): p for p in parcels}
    log: list[dict] = []
    live: dict[tuple[str, str], dict] = {}      # (apn, owner on record) -> latest ballot

    def owners_of(p):
        out = []
        for part in p["owners"].split("|"):
            nm, _, share = part.partition(":")
            out.append((nm.strip(), Fraction(share) if share.strip() else None))
        return out

    for b in sorted(ballots, key=lambda b: (parse_dt(b["received"]) or datetime.max, b["ballot_id"])):
        apn = norm_apn(b["apn"])
        rec = {"ballot_id": b["ballot_id"], "apn": apn, "owner": b["owner_name"], "status": "", "reason": ""}
        log.append(rec)
        received = parse_dt(b["received"])
        if apn not in by_apn:
            rec.update(status="REVIEW", reason="APN is not an identified parcel"); continue
        if received is None or received > testimony_close:
            rec.update(status="INVALID", reason="received after the conclusion of public testimony"); continue
        if not truthy(b.get("signed", "")):
            rec.update(status="INVALID", reason="not signed (Gov. Code § 53753(c))"); continue
        match = [nm for nm, _ in owners_of(by_apn[apn]) if names_match(nm, b["owner_name"])]
        if len(match) != 1:
            rec.update(status="REVIEW", reason="signer is not a record owner of the parcel"); continue
        key = (apn, match[0])
        vote = b["vote"].strip().lower()
        if vote in {"yes", "no", "withdraw"} and key in live:
            live[key]["_rec"].update(status="SUPERSEDED", reason="changed or withdrawn by %s" % b["ballot_id"])
        if vote == "withdraw":
            live.pop(key, None)
            rec.update(status="WITHDRAWAL_APPLIED", reason="ballot withdrawn before close of testimony")
        elif vote in {"yes", "no"}:
            live[key] = {"vote": vote, "_rec": rec}
            rec.update(status="COUNTED", reason="")
        else:
            rec.update(status="INVALID", reason="no support or opposition marked")

    yes = no = Fraction(0)
    review = []
    for apn, p in by_apn.items():
        returned = [(nm, sh) for nm, sh in owners_of(p) if (apn, nm) in live]
        if not returned:
            continue
        amount = Fraction(int(p["assessment_cents"]))
        if len(returned) == 1:
            weights = {returned[0][0]: amount}
        elif any(sh is None for _, sh in returned):
            review.append(apn)
            for nm, _ in returned:
                live[(apn, nm)]["_rec"].update(status="REVIEW", reason="co-owner interests not on the record (Gov. Code § 53753(e)(3))")
            continue
        else:
            total = sum(sh for _, sh in returned)
            weights = {nm: amount * sh / total for nm, sh in returned}
        for nm, w in weights.items():
            item = live[(apn, nm)]
            item["_rec"]["weight_cents"] = str(w) if w.denominator != 1 else int(w)
            if item["vote"] == "yes":
                yes += w
            else:
                no += w

    return {
        "weighted_yes_cents": float(yes), "weighted_no_cents": float(no),
        "weighted_yes_exact": str(yes), "weighted_no_exact": str(no),
        "majority_protest": no > yes,
        "parcels_in_review": sorted(review),
        "outcome": "UNDETERMINED_PENDING_REVIEW" if review and _review_could_flip(by_apn, review, yes, no)
                   else ("MAJORITY_PROTEST" if no > yes else "NO_MAJORITY_PROTEST"),
        "log": log,
    }


def _review_could_flip(by_apn, review, yes, no) -> bool:
    swing = sum(Fraction(int(by_apn[a]["assessment_cents"])) for a in review)
    return (no > yes) != (no + swing > yes) or (no > yes) != (no > yes + swing)


# ---------------------------------------------------------------- calendar and AB 2257

@dataclass
class Check:
    id: str
    ok: bool | None          # None = not applicable or needs a person
    detail: str
    source: str


def check_calendar(case: dict, rules: dict) -> list[Check]:
    out: list[Check] = []
    mailed = parse_date(case["notice_mailed"])
    hearing = parse_date(case["hearing_date"])
    kind = case.get("proceeding", "section_6_fee")
    key = "fee_hearing_min_days_after_notice" if kind == "section_6_fee" else "assessment_hearing_min_days_after_notice"
    need = rule(rules, key)
    gap = (hearing - mailed).days
    out.append(Check("hearing_gap", gap >= need,
                     "Hearing is %d days after the notice was mailed; at least %d required." % (gap, need), cite(rules, key)))

    ab = case.get("ab2257")
    if ab:
        service = case.get("service", "")
        in_scope = service in rule(rules, "ab2257_scope")
        out.append(Check("ab2257_scope", in_scope,
                         "Service type '%s' %s the § 53759.1 definition of fee or assessment." % (service, "is within" if in_scope else "is NOT within"),
                         cite(rules, "ab2257_scope")))
        deadline = parse_dt(ab["objection_deadline"]).date()
        avail = parse_date(ab["proposed_fee_available"])
        need = rule(rules, "ab2257_fee_available_min_days_before_objection_deadline")
        out.append(Check("fee_available", (deadline - avail).days >= need,
                         "Proposed fee was public %d days before the objection deadline; at least %d required." % ((deadline - avail).days, need),
                         cite(rules, "ab2257_fee_available_min_days_before_objection_deadline")))
        need = rule(rules, "ab2257_objection_deadline_min_days_after_notice")
        out.append(Check("objection_window", (deadline - mailed).days >= need,
                         "Objection deadline is %d days after notice; at least %d required." % ((deadline - mailed).days, need),
                         cite(rules, "ab2257_objection_deadline_min_days_after_notice")))
        out.append(Check("deadline_before_hearing", deadline <= hearing,
                         "Objection deadline %s is %s the hearing date %s." % (deadline, "on or before" if deadline <= hearing else "after", hearing),
                         cite(rules, "ab2257_complete_before_hearing_ends")))
        n = ab.get("notice", {})
        out.append(Check("written_basis_posted", bool(n.get("written_basis_on_website")) and bool(n.get("website_link_in_notice")),
                         "Written basis posted on the website and linked in the mailed notice.",
                         cite(rules, "ab2257_written_basis_on_website_and_link_in_notice")))
        out.append(Check("notice_statement", bool(n.get("exhaustion_statement_prominent")) and bool(n.get("objection_requirements_stated")),
                         "Notice carries the prominent failure-to-object statement and the requirements for objecting.",
                         cite(rules, "ab2257_notice_statement")))
        reqs = ab.get("written_basis_mail_requests", [])
        unmailed = [r["requester"] for r in reqs if not r.get("mailed")]
        out.append(Check("mail_on_request", not unmailed,
                         "%d request(s) for a mailed copy of the written basis; %d not yet mailed." % (len(reqs), len(unmailed)),
                         cite(rules, "ab2257_mail_written_basis_on_request")))

    if case.get("service") in {"water", "sewer"}:
        n = (case.get("ab2257") or {}).get("notice", case.get("notice", {}))
        out.append(Check("sol_statement", bool(n.get("sol_120_day_statement")),
                         "Notice states the 120-day statute of limitations.", cite(rules, "sol_statement_in_notice")))
    return out


def sol_deadline(case: dict, rules: dict) -> dict | None:
    """Last day to sue under Gov. Code § 53759(a): 120 days from the later of the
    effective date and the adoption date. Water and sewer fees only."""
    if case.get("service") not in {"water", "sewer"} or not case.get("adoption_date"):
        return None
    adopted = parse_date(case["adoption_date"])
    if adopted <= parse_date(rule(rules, "sol_applies_to_fees_adopted_after")):
        return None
    start = max(adopted, parse_date(case.get("effective_date") or case["adoption_date"]))
    last = start + timedelta(days=rule(rules, "sol_days"))
    return {
        "runs_from": start.isoformat(), "last_day_raw": last.isoformat(),
        "falls_on_weekend": last.weekday() >= 5,
        "note": "Weekend and holiday roll-forward rules were not checked; an attorney must confirm.",
        "source": cite(rules, "sol_days"),
    }


def keyword_hits(text: str, rules: dict) -> list[str]:
    t = (text or "").lower()
    return [k for k in rules["objection_keywords"]["terms"] if k in t]


def objection_gate(case: dict, objections: list[dict], responses: list[dict],
                   submissions: list[dict], rules: dict) -> dict:
    """Every timely written objection needs a written response that explains the
    substantive basis, dated before the hearing closed, and presented to the governing
    body before or during the hearing (Gov. Code § 53759.1(c)(5)). The gate also blocks
    while any protest letter with objection-like wording has not been triaged by a person."""
    ab = case["ab2257"]
    deadline = parse_dt(ab["objection_deadline"])
    close = parse_dt(case["hearing_close"])
    resp = {r["objection_id"]: r for r in responses}
    rows, open_items = [], []
    for o in sorted(objections, key=lambda o: o["objection_id"]):
        oid, received = o["objection_id"], parse_dt(o["received"])
        row = {"objection_id": oid, "received": o["received"], "submitter": o.get("submitter", ""),
               "issue_tags": o.get("issue_tags", ""), "response_exhibit": "", "status": "", "problems": ""}
        rows.append(row)
        if received is None or received > deadline:
            row["status"] = "UNTIMELY"
            row["problems"] = "received after the objection deadline; no response is required by § 53759.1(c)(5)"
            continue
        problems = []
        if not o.get("grounds_text", "").strip():
            problems.append("objection states no grounds; respond anyway and note it (does not block)")
        r = resp.get(oid)
        blocking = []
        if not r:
            blocking.append("no written response")
        else:
            row["response_exhibit"] = r.get("exhibit_ref", "")
            when = parse_dt(r.get("responded_at", ""))
            if when is None or when > close:
                blocking.append("response not dated before the close of the hearing")
            if not truthy(r.get("explains_substantive_basis", "")):
                blocking.append("response not marked as explaining the substantive basis")
            shown = parse_dt(r.get("presented_to_board_at", ""))
            if shown is None or shown > close:
                blocking.append("objection and response not presented to the governing body before or during the hearing")
        row["status"] = "OPEN" if blocking else "ANSWERED"
        row["problems"] = "; ".join(blocking + problems)
        if blocking:
            open_items.append(oid)

    triage = []
    for s in sorted(submissions, key=lambda s: s["submission_id"]):
        hits = keyword_hits(s.get("letter_text", ""), rules)
        if hits and not (s.get("objection_triage") or "").strip():
            received = parse_dt(s["received"])
            if received and received <= deadline:
                triage.append({"submission_id": s["submission_id"], "received": s["received"], "keywords": ", ".join(hits)})

    timely = [r for r in rows if r["status"] != "UNTIMELY"]
    return {
        "timely_objections": len(timely),
        "answered": sum(r["status"] == "ANSWERED" for r in rows),
        "open": open_items,
        "untimely": sum(r["status"] == "UNTIMELY" for r in rows),
        "protest_letters_awaiting_triage": triage,
        "gate": "CLEAR" if not open_items and not triage else "BLOCKED",
        "rows": rows,
        "source": cite(rules, "ab2257_respond_in_writing_before_hearing_close"),
    }


def record_index(case: dict, rules: dict) -> list[dict]:
    cats = rule(rules, "ab2257_record_categories")
    docs = case.get("record_documents", [])
    return [{"category": c, "description": d,
             "documents": [x["title"] for x in docs if x["category"] == c],
             "present": any(x["category"] == c for x in docs)} for c, d in cats.items()]


# ---------------------------------------------------------------- io and report

def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], cols: list[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


OUTCOME_TEXT = {
    "MAJORITY_PROTEST": "Majority protest. The fee may not be imposed.",
    "NO_MAJORITY_PROTEST": "No majority protest, even if every item in review were counted.",
    "UNDETERMINED_PENDING_REVIEW": "Not yet determined. The items in review could change the result.",
}


def run(data_dir: Path, out_dir: Path, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    case = json.loads((data_dir / "case.json").read_text(encoding="utf-8"))
    parcels = read_csv(data_dir / "parcels.csv")
    accounts = read_csv(data_dir / "accounts.csv")
    subs = read_csv(data_dir / "submissions.csv")
    objections = read_csv(data_dir / "objections.csv")
    responses = read_csv(data_dir / "responses.csv")
    close = parse_dt(case["hearing_close"])

    tally = tally_fee_protests(parcels, accounts, subs, close, rules, case.get("policy"))
    checks = check_calendar(case, rules)
    gate = objection_gate(case, objections, responses, subs, rules)
    sol = sol_deadline(case, rules)
    record = record_index(case, rules)

    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [vars(l) for l in tally.pop("lines")]
    write_csv(out_dir / "protest_audit_log.csv", lines,
              ["submission_id", "received", "apn", "signer", "status", "reason", "resolved_by"])
    write_csv(out_dir / "review_queue.csv", [l for l in lines if l["status"] == "REVIEW"],
              ["submission_id", "received", "apn", "signer", "reason"])
    write_csv(out_dir / "objection_gate.csv", gate["rows"],
              ["objection_id", "received", "submitter", "issue_tags", "response_exhibit", "status", "problems"])
    result = {
        "disclaimer": "Fictional data. Portfolio demo, not legal advice.",
        "case": {k: case[k] for k in ("agency", "proceeding", "service", "notice_mailed", "hearing_date", "hearing_close")},
        "protest_tally": tally,
        "calendar_checks": [vars(c) for c in checks],
        "objection_gate": {k: v for k, v in gate.items() if k != "rows"},
        "statute_of_limitations": sol,
        "record_index": record,
        "rules_verified_on": rules["verified_on"],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(result, gate["rows"]), encoding="utf-8")
    return result


def render_report(r: dict, gate_rows: list[dict]) -> str:
    t, g, c = r["protest_tally"], r["objection_gate"], r["case"]
    mark = lambda ok: "n/a" if ok is None else ("pass" if ok else "FAIL")
    L = ["# Protest tabulation and objection gate", "",
         "%s. Fictional data. Portfolio demo, not legal advice." % c["agency"], "",
         "## Protest tally (art. XIII D § 6)", "",
         "**%s**" % OUTCOME_TEXT[t["outcome"]], "",
         "| | |", "|---|---|",
         "| Identified parcels | %d |" % t["identified_parcels"],
         "| Protests needed for a majority | %d |" % t["threshold"],
         "| Parcels with a counted protest | %d |" % t["counted_protests"],
         "| Items in review that could add a parcel | %d |" % t["review_items_that_could_add_a_parcel"],
         "| Most protests possible | %d |" % t["max_possible_protests"],
         "| Submissions received | %d |" % t["submissions_received"], "",
         "Dispositions, one line per submission per parcel: " +
         ", ".join("%s %d" % kv for kv in t["lines_by_status"].items()) + ".", "",
         "## Calendar and notice checks", "", "| Check | Result | Detail | Source |", "|---|---|---|---|"]
    L += ["| %s | %s | %s | %s |" % (k["id"], mark(k["ok"]), k["detail"], k["source"]) for k in r["calendar_checks"]]
    L += ["", "## Objection gate (Gov. Code § 53759.1(c)(5))", "",
          "**Gate: %s.** %d timely objections, %d answered, %d open, %d untimely, %d protest letters awaiting triage." %
          (g["gate"], g["timely_objections"], g["answered"], len(g["open"]), g["untimely"], len(g["protest_letters_awaiting_triage"])), "",
          "| Objection | Received | Tags | Exhibit | Status | Problems |", "|---|---|---|---|---|---|"]
    L += ["| %(objection_id)s | %(received)s | %(issue_tags)s | %(response_exhibit)s | %(status)s | %(problems)s |" % x for x in gate_rows]
    if g["protest_letters_awaiting_triage"]:
        L += ["", "Protest letters with objection-like wording that nobody has triaged yet:", ""]
        L += ["- %(submission_id)s (received %(received)s): %(keywords)s" % x for x in g["protest_letters_awaiting_triage"]]
    s = r["statute_of_limitations"]
    if s:
        L += ["", "## Statute of limitations (Gov. Code § 53759)", "",
              "Runs from %s. Raw 120th day: %s%s. %s" % (s["runs_from"], s["last_day_raw"],
              " (a weekend)" if s["falls_on_weekend"] else "", s["note"])]
    L += ["", "## Record of proceedings index (Gov. Code § 53759.2(b)(1))", "", "| | Category | Documents |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % (x["category"], x["description"], "; ".join(x["documents"]) or "**none listed**") for x in r["record_index"]]
    L += ["", "Rules read against primary text on %s. See rules.json for each source and status." % r["rules_verified_on"], ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Prop 218 protest tabulator (fictional-data demo)")
    ap.add_argument("--data", default=str(HERE / "sample_data"))
    ap.add_argument("--out", default=str(HERE / "output"))
    ap.add_argument("--assessment", action="store_true", help="run the small art. XIII D § 4 ballot example instead")
    a = ap.parse_args()
    if a.assessment:
        d, out = Path(a.data) / "assessment", Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        r = tally_assessment(read_csv(d / "parcels.csv"), read_csv(d / "ballots.csv"), parse_dt("2026-10-06T20:30:00"))
        write_csv(out / "assessment_ballot_log.csv", r.pop("log"), ["ballot_id", "apn", "owner", "status", "reason", "weight_cents"])
        (out / "assessment_result.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
        print("%s  weighted no $%.2f, weighted yes $%.2f, %d parcel(s) in review" %
              (r["outcome"], r["weighted_no_cents"] / 100, r["weighted_yes_cents"] / 100, len(r["parcels_in_review"])))
        return
    r = run(Path(a.data), Path(a.out))
    t, g = r["protest_tally"], r["objection_gate"]
    print("%s  counted %d of %d identified parcels, %d needed, %d in review" %
          (t["outcome"], t["counted_protests"], t["identified_parcels"], t["threshold"], t["review_items_that_could_add_a_parcel"]))
    print("Objection gate %s  (%d open, %d awaiting triage)" % (g["gate"], len(g["open"]), len(g["protest_letters_awaiting_triage"])))
    print("Wrote", a.out)


if __name__ == "__main__":
    main()
