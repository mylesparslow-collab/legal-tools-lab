"""Deadline arithmetic under the California Code of Civil Procedure.

Counting rules implemented (text read on leginfo 2026-11-25):

* § 12   Exclude the first day, include the last, unless the last day is a
         holiday, and then it is also excluded.
* § 12a  If the last day to act is a holiday (Saturday, Sunday or judicial
         holiday), the period runs to the next day that is not a holiday.
* § 12c  Days before a hearing are counted backward from the hearing date,
         excluding the hearing day; extra days for a method of service are
         counted backward from the day found that way.
* § 1013 Service by mail extends a period to act after service by 5 calendar
         days (10 out of state, 12 for a Safe at Home address, 20 outside the
         United States). Express mail, overnight delivery and fax: 2 court days.
* § 1010.6(a)(3)(B) Electronic service: 2 court days. § 1010.6(a)(4): a document
         served electronically on a noncourt day is deemed served on the next court day.
* § 1005(b) Motion papers: 16 court days before the hearing; mail adds 5, 10,
         12 or 20 calendar days; fax, express mail and overnight delivery add
         2 calendar days; § 1013 does not apply. Opposition 9 court days and
         reply 5 court days before the hearing.
* § 437c(a)(2)-(3), (b)(2), (b)(4) Summary judgment: 81 days' notice; mail adds
         5, 10 or 20 days; fax, express mail and overnight delivery add 2 court
         days; hearing at least 30 days before trial; opposition 20 days and
         reply 11 days before the hearing.

Every function returns a Result with the date, the steps taken and any warnings.
Court orders, local rules and case-specific statutes can change any of these
dates. This is a demonstration, not legal advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .holidays import holiday_source, is_court_day, why_closed
from .rules import RESPONSE_RULES

ONE = timedelta(days=1)

# method -> (label, forward extension under § 1013 / § 1010.6 as (n, unit))
SERVICE_METHODS: dict[str, tuple[str, tuple[int, str]]] = {
    "personal": ("personal delivery", (0, "calendar")),
    "mail": ("mail within California", (5, "calendar")),
    "mail_out_of_state": ("mail to or from another state", (10, "calendar")),
    "mail_safe_at_home": ("mail to a Safe at Home (address confidentiality) address", (12, "calendar")),
    "mail_outside_us": ("mail to or from outside the United States", (20, "calendar")),
    "overnight": ("express mail or overnight delivery", (2, "court")),
    "fax": ("fax (by written agreement)", (2, "court")),
    "electronic": ("electronic service", (2, "court")),
}

# § 1005(b): additions to the 16-court-day notice period, counted backward.
_MOTION_EXTENSION: dict[str, tuple[int, str, str]] = {
    "personal": (0, "calendar", "Code Civ. Proc. § 1005(b)"),
    "mail": (5, "calendar", "Code Civ. Proc. § 1005(b)"),
    "mail_out_of_state": (10, "calendar", "Code Civ. Proc. § 1005(b)"),
    "mail_safe_at_home": (12, "calendar", "Code Civ. Proc. § 1005(b)"),
    "mail_outside_us": (20, "calendar", "Code Civ. Proc. § 1005(b)"),
    "overnight": (2, "calendar", "Code Civ. Proc. § 1005(b)"),
    "fax": (2, "calendar", "Code Civ. Proc. § 1005(b)"),
    "electronic": (2, "court", "Code Civ. Proc. § 1010.6(a)(3)(B)"),
}

# § 437c(a)(2): additions to the 81-day notice period, counted backward.
_MSJ_EXTENSION: dict[str, tuple[int, str, str]] = {
    "personal": (0, "calendar", "Code Civ. Proc. § 437c(a)(2)"),
    "mail": (5, "calendar", "Code Civ. Proc. § 437c(a)(2)"),
    "mail_out_of_state": (10, "calendar", "Code Civ. Proc. § 437c(a)(2)"),
    "mail_outside_us": (20, "calendar", "Code Civ. Proc. § 437c(a)(2)"),
    "overnight": (2, "court", "Code Civ. Proc. § 437c(a)(2)"),
    "fax": (2, "court", "Code Civ. Proc. § 437c(a)(2)"),
    "electronic": (2, "court", "Code Civ. Proc. § 1010.6(a)(3)(B)"),
}


@dataclass
class Result:
    label: str
    date: date
    authority: str
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safe_date: date | None = None  # earlier court day, when a backward count lands on a closed day

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "date": self.date.isoformat(),
            "weekday": self.date.strftime("%A"),
            "safe_date": self.safe_date.isoformat() if self.safe_date else None,
            "authority": self.authority,
            "steps": self.steps,
            "warnings": self.warnings,
        }


def _fmt(d: date) -> str:
    return d.strftime("%a %Y-%m-%d")


def _source_warnings(*dates: date) -> list[str]:
    lo, hi = min(dates), max(dates)
    out = []
    years = [y for y in range(lo.year, hi.year + 1) if holiday_source(y) == "computed"]
    if years:
        out.append(
            "Holidays for " + ", ".join(map(str, years)) + " are computed from Code Civ. Proc. § 135 "
            "and Gov. Code §§ 6700-6701, not taken from a published Judicial Council schedule. "
            "Check the published schedule."
        )
    if lo <= date(2027, 12, 31) <= hi:
        out.append(
            "January 1, 2028 is a Saturday. The published 2027 schedule does not list "
            "December 31, 2027 as a holiday; check the 2028 schedule when it is published."
        )
    return out


def _roll_forward(d: date, steps: list[str]) -> date:
    """§ 12a: move a last day that is a holiday to the next day that is not."""
    while not is_court_day(d):
        steps.append(f"{_fmt(d)} is closed ({why_closed(d)}); move to the next day (§ 12a).")
        d += ONE
    return d


def _step_court_days(start: date, n: int, direction: int) -> date:
    d = start
    left = n
    while left:
        d += ONE * direction
        if is_court_day(d):
            left -= 1
    return d


def add_calendar_days(start: date, n: int, label: str = "", authority: str = "Code Civ. Proc. §§ 12, 12a") -> Result:
    """Last day to act within n calendar days after a triggering date."""
    if n < 0:
        raise ValueError("n must not be negative")
    steps = [f"Start {_fmt(start)} (excluded, § 12). Add {n} calendar days: {_fmt(start + ONE * n)}."]
    d = _roll_forward(start + ONE * n, steps)
    return Result(label or f"{n} calendar days after {start.isoformat()}", d, authority, steps,
                  _source_warnings(start, d))


def add_court_days(start: date, n: int, label: str = "", authority: str = "Code Civ. Proc. §§ 12, 12a") -> Result:
    """Date that is n court days after a triggering date."""
    if n < 0:
        raise ValueError("n must not be negative")
    d = _step_court_days(start, n, +1)
    steps = [f"Start {_fmt(start)} (excluded). Count {n} court days forward: {_fmt(d)}."]
    return Result(label or f"{n} court days after {start.isoformat()}", d, authority, steps,
                  _source_warnings(start, d))


def back_court_days(hearing: date, n: int, label: str = "", authority: str = "Code Civ. Proc. § 12c") -> Result:
    """Last day that is at least n court days before a hearing date."""
    if n < 0:
        raise ValueError("n must not be negative")
    d = _step_court_days(hearing, n, -1)
    steps = [f"Hearing {_fmt(hearing)} (excluded, § 12c(a)). Count {n} court days back: {_fmt(d)}."]
    return Result(label or f"{n} court days before {hearing.isoformat()}", d, authority, steps,
                  _source_warnings(d, hearing))


def _safe(d: date, steps: list[str]) -> date | None:
    """For backward counts: the court day on or before d, if d itself is closed."""
    if is_court_day(d):
        return None
    s = d
    while not is_court_day(s):
        s -= ONE
    steps.append(
        f"{_fmt(d)} is closed ({why_closed(d)}). The statutes do not say that a backward-counted "
        f"deadline moves; the earlier court day {_fmt(s)} is shown as the safe date."
    )
    return s


def back_calendar_days(hearing: date, n: int, label: str = "", authority: str = "Code Civ. Proc. § 12c") -> Result:
    """Last day that is at least n calendar days before a hearing date."""
    if n < 0:
        raise ValueError("n must not be negative")
    d = hearing - ONE * n
    steps = [f"Hearing {_fmt(hearing)} (excluded, § 12c(a)). Count {n} calendar days back: {_fmt(d)}."]
    safe = _safe(d, steps)
    return Result(label or f"{n} calendar days before {hearing.isoformat()}", d, authority, steps,
                  _source_warnings(d, hearing), safe)


def _check_method(method: str, table: dict) -> None:
    if method not in table:
        raise ValueError(f"unknown or unsupported service method '{method}'; choose from {sorted(table)}")


def _check_hearing(hearing: date) -> None:
    if not is_court_day(hearing):
        raise ValueError(f"{hearing.isoformat()} is not a court day ({why_closed(hearing)})")


def _extend_back(base: date, method: str, table: dict, steps: list[str]) -> tuple[date, str]:
    n, unit, auth = table[method]
    if n == 0:
        return base, auth
    if unit == "calendar":
        d = base - ONE * n
    else:
        d = _step_court_days(base, n, -1)
    steps.append(
        f"Service by {SERVICE_METHODS[method][0]}: count {n} more {unit} days back from {_fmt(base)} "
        f"(§ 12c(b); {auth}): {_fmt(d)}."
    )
    return d, auth


def motion_schedule(hearing: date, method: str = "personal") -> dict[str, Result]:
    """Last days to serve and file moving, opposition and reply papers (§ 1005(b))."""
    _check_method(method, _MOTION_EXTENSION)
    _check_hearing(hearing)
    moving = back_court_days(hearing, 16, "Moving papers: last day to serve and file",
                             "Code Civ. Proc. §§ 1005(b), 12c")
    d, auth = _extend_back(moving.date, method, _MOTION_EXTENSION, moving.steps)
    moving.date = d
    moving.safe_date = _safe(d, moving.steps)
    if "1010.6" in auth:
        moving.authority += ", 1010.6(a)(3)(B)"
    moving.warnings = _source_warnings(d, hearing)
    opp = back_court_days(hearing, 9, "Opposition: last day to file and serve",
                          "Code Civ. Proc. §§ 1005(b), 12c")
    rep = back_court_days(hearing, 5, "Reply: last day to file and serve",
                          "Code Civ. Proc. §§ 1005(b), 12c")
    for r in (opp, rep):
        r.steps.append(
            "Opposition and reply papers must be served by a means reasonably calculated to ensure "
            "delivery by the close of the next business day after filing (§ 1005(c)). "
            "No days are added for the method of service."
        )
    return {"moving": moving, "opposition": opp, "reply": rep}


def msj_schedule(hearing: date, method: str = "personal", trial: date | None = None) -> dict[str, Result]:
    """Summary judgment notice, opposition and reply dates (§ 437c)."""
    _check_method(method, _MSJ_EXTENSION)
    _check_hearing(hearing)
    moving = back_calendar_days(hearing, 81, "Notice of motion and supporting papers: last day to serve",
                                "Code Civ. Proc. §§ 437c(a)(2), 12c")
    d, auth = _extend_back(moving.date, method, _MSJ_EXTENSION, moving.steps)
    moving.date = d
    moving.safe_date = _safe(d, moving.steps)
    if "1010.6" in auth:
        moving.authority += ", 1010.6(a)(3)(B)"
    moving.warnings = _source_warnings(d, hearing)
    opp = back_calendar_days(hearing, 20, "Opposition: last day to serve and file",
                             "Code Civ. Proc. §§ 437c(b)(2), 12c")
    rep = back_calendar_days(hearing, 11, "Reply: last day to serve and file",
                             "Code Civ. Proc. §§ 437c(b)(4), 12c")
    out = {"moving": moving, "opposition": opp, "reply": rep}
    if trial is not None:
        latest = back_calendar_days(trial, 30, "Latest hearing date (30 days before trial)",
                                    "Code Civ. Proc. § 437c(a)(3)")
        if hearing > latest.date:
            latest.warnings.append(
                f"The hearing on {_fmt(hearing)} is less than 30 days before trial on {_fmt(trial)}. "
                "The motion must be heard no later than 30 days before trial unless the court "
                "orders otherwise for good cause."
            )
        out["latest_hearing"] = latest
    return out


def response_deadline(served: date, rule: str | int, method: str = "personal") -> Result:
    """Last day to respond or act after service of a paper.

    `rule` is a key in rules.RESPONSE_RULES, or a number of calendar days for a
    generic period that §§ 1013 and 1010.6 extend.
    """
    _check_method(method, SERVICE_METHODS)
    if isinstance(rule, int):
        days, label, authority, extends = rule, f"{rule} days after service", "Code Civ. Proc. §§ 12, 12a", True
        note = ""
    else:
        if rule not in RESPONSE_RULES:
            raise ValueError(f"unknown rule '{rule}'; choose from {sorted(RESPONSE_RULES)}")
        r = RESPONSE_RULES[rule]
        days, label, authority, extends, note = r.days, r.label, r.authority, r.service_extension, r.note
    steps: list[str] = []
    if method == "electronic" and not is_court_day(served):
        deemed = served
        while not is_court_day(deemed):
            deemed += ONE
        steps.append(
            f"Electronic service on {_fmt(served)}, a noncourt day, is deemed made on the next "
            f"court day, {_fmt(deemed)} (§ 1010.6(a)(4))."
        )
        served = deemed
    base = served + ONE * days
    steps.append(f"Served {_fmt(served)} (excluded, § 12). Add {days} calendar days: {_fmt(base)}.")
    n, unit = SERVICE_METHODS[method][1]
    d = base
    if n and not extends:
        steps.append("This period is not extended by the method of service (§ 1013; § 1010.6(a)(3)(B)).")
    elif n and unit == "calendar":
        d = base + ONE * n
        steps.append(f"Service by {SERVICE_METHODS[method][0]}: add {n} calendar days (§ 1013(a)): {_fmt(d)}.")
        authority += "; § 1013(a)"
    elif n:
        d = _step_court_days(base, n, +1)
        sec = "§ 1010.6(a)(3)(B)" if method == "electronic" else "§ 1013(c), (e)"
        steps.append(
            f"Service by {SERVICE_METHODS[method][0]}: add {n} court days ({sec}), counted from "
            f"{_fmt(base)} without first moving it off a closed day: {_fmt(d)}. "
            "This is the earlier of the two readings."
        )
        authority += f"; {sec}"
    d = _roll_forward(d, steps)
    res = Result(label, d, authority, steps, _source_warnings(served, d))
    if note:
        res.warnings.append(note)
    return res
