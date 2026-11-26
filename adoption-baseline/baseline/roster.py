"""Roster loading and the denominator rule.

The roster is the only source of denominators. A person with no usage rows is
still in the denominator and counts as zero.
"""
import csv
from collections import namedtuple
from datetime import date, datetime, timedelta

ROLES = ("partner", "counsel", "associate", "paralegal", "staff")
TRUE_VALUES = {"yes", "y", "true", "1"}
FALSE_VALUES = {"no", "n", "false", "0", ""}

Assignment = namedtuple("Assignment", "effective_from role practice office")

ELIGIBLE, NOT_STARTED, LEFT, ON_LEAVE = "eligible", "not_started", "left", "on_leave"


class RosterError(ValueError):
    pass


def parse_iso(value):
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def normalise_identifier(value):
    """Case-fold and collapse white space. Used for email and name matching."""
    return " ".join(str(value).split()).casefold()


class Person:
    def __init__(self, person_id, name, email, licences, start_date, end_date, leave):
        self.person_id = person_id
        self.name = name
        self.email = email
        self.licences = licences          # tool name -> bool
        self.start_date = start_date
        self.end_date = end_date
        self.leave = leave                # list of (first day, last day), inclusive
        self.assignments = []             # sorted list of Assignment

    def assignment_on(self, day):
        """Role, practice and office in effect on a day.

        Before the first dated row the earliest row applies.
        """
        current = self.assignments[0]
        for a in self.assignments:
            if a.effective_from is None or a.effective_from <= day:
                current = a
        return current

    def changed_practice(self):
        return len({a.practice for a in self.assignments}) > 1

    def on_leave(self, day):
        return any(a <= day <= b for a, b in self.leave)

    def employed_on(self, day):
        return self.start_date <= day and (self.end_date is None or self.end_date >= day)

    def week_status(self, monday):
        """The denominator rule for one ISO week (Monday to Sunday).

        not_started: start date is after the Sunday of the week.
        left:        end date is before the Monday of the week.
        on_leave:    leave covers every weekday, Monday to Friday.
        Otherwise the person is eligible, including part weeks.
        """
        sunday = monday + timedelta(days=6)
        if self.start_date > sunday:
            return NOT_STARTED
        if self.end_date is not None and self.end_date < monday:
            return LEFT
        if all(self.on_leave(monday + timedelta(days=i)) for i in range(5)):
            return ON_LEAVE
        return ELIGIBLE

    def absent_throughout(self, first, last):
        """True if the person was not at work on any weekday in the window."""
        day = first
        while day <= last:
            if day.weekday() < 5 and self.employed_on(day) and not self.on_leave(day):
                return False
            day += timedelta(days=1)
        return True


class Roster:
    def __init__(self, people, tools, issues):
        self.people = people              # person_id -> Person
        self.tools = tools                # list of tool names
        self.issues = issues              # dict of counts
        self._by_email = {}
        self._by_name = {}
        for p in people.values():
            self._by_email.setdefault(normalise_identifier(p.email), []).append(p)
            self._by_name.setdefault(normalise_identifier(p.name), []).append(p)
        self._by_id = {normalise_identifier(pid): [p] for pid, p in people.items()}

    def __len__(self):
        return len(self.people)

    def lookup(self, raw, match_on):
        """Resolve a raw identifier from an export.

        Returns (person or None, outcome) where outcome is one of
        exact, repaired, unknown, ambiguous.
        """
        index = {"email": self._by_email, "name": self._by_name, "person_id": self._by_id}[match_on]
        hits = index.get(normalise_identifier(raw), [])
        if not hits:
            return None, "unknown"
        if len(hits) > 1:
            return None, "ambiguous"
        person = hits[0]
        canonical = {"email": person.email, "name": person.name, "person_id": person.person_id}[match_on]
        return person, ("exact" if raw == canonical else "repaired")


def _parse_leave(text):
    periods = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        first, _, last = chunk.partition("/")
        a, b = parse_iso(first), parse_iso(last or first)
        if b < a:
            raise ValueError("leave period ends before it starts: %s" % chunk)
        periods.append((a, b))
    return sorted(periods)


def _parse_flag(text):
    v = text.strip().casefold()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    raise ValueError("licence flag must be yes or no, got %r" % text)


def load_roster(path, tools):
    """Load a roster CSV.

    tools is a list of {"name": ..., "licence_column": ...}.
    A person may have several rows with different effective_from dates; that is
    how a change of practice, office or role is recorded. Rows that cannot be
    read are skipped and counted in issues, never silently.
    """
    required = ["person_id", "name", "email", "role", "practice", "office", "start_date"] + [
        t["licence_column"] for t in tools]
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise RosterError("roster %s is missing columns: %s" % (path, ", ".join(missing)))
        rows = list(reader)
    people = {}
    issues = {"rows_read": len(rows), "rows_skipped_invalid": 0, "duplicate_assignment_rows": 0,
              "invalid_examples": []}
    seen = set()
    for n, row in enumerate(rows, 2):
        try:
            pid = row["person_id"].strip()
            if not pid:
                raise ValueError("blank person_id")
            role = row["role"].strip().casefold()
            if role not in ROLES:
                raise ValueError("unknown role %r" % row["role"])
            eff_text = (row.get("effective_from") or "").strip()
            eff = parse_iso(eff_text) if eff_text else None
            start = parse_iso(row["start_date"])
            end_text = (row.get("end_date") or "").strip()
            end = parse_iso(end_text) if end_text else None
            leave = _parse_leave(row.get("leave_periods") or "")
            licences = {t["name"]: _parse_flag(row[t["licence_column"]]) for t in tools}
            practice, office = row["practice"].strip(), row["office"].strip()
            if not practice or not office:
                raise ValueError("blank practice or office")
        except ValueError as exc:
            issues["rows_skipped_invalid"] += 1
            if len(issues["invalid_examples"]) < 5:
                issues["invalid_examples"].append("line %d: %s" % (n, exc))
            continue
        if (pid, eff) in seen:
            issues["duplicate_assignment_rows"] += 1
            continue
        seen.add((pid, eff))
        if pid not in people:
            people[pid] = Person(pid, row["name"].strip(), row["email"].strip(), licences, start, end, leave)
        else:
            # Later rows for the same person carry the current licence and leave details.
            p = people[pid]
            p.licences, p.start_date, p.end_date, p.leave = licences, start, end, leave
        people[pid].assignments.append(Assignment(eff, role, practice, office))
    for p in people.values():
        p.assignments.sort(key=lambda a: (a.effective_from is not None, a.effective_from or date.min))
    issues["people"] = len(people)
    return Roster(people, [t["name"] for t in tools], issues)
