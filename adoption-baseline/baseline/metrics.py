"""Metric calculations. Written definitions are in METRICS.md.

Everything is computed from the roster (denominators) and the canonical day
table (numerators). Group tables go through small-group suppression before
they leave this module.
"""
from collections import defaultdict
from datetime import timedelta

from .roster import ELIGIBLE, LEFT, NOT_STARTED, ON_LEAVE, parse_iso
from .suppress import cell, hidden, suppress_cells

ANY = "any approved tool"
POPULATION_NOTE = ("All roles, on the roster at period end, with at least one interaction in the window. "
                   "Per-tool rows count licence holders for that tool only; the any-tool row counts everyone.")


def week_label(monday):
    y, w, _ = monday.isocalendar()
    return "%d-W%02d" % (y, w)


def complete_weeks(start, end):
    """Mondays of the ISO weeks that lie wholly inside [start, end]."""
    monday = start + timedelta(days=(7 - start.weekday()) % 7)
    weeks = []
    while monday + timedelta(days=6) <= end:
        weeks.append(monday)
        monday += timedelta(days=7)
    return weeks


def quantile(sorted_values, q):
    """Quantile by linear interpolation between closest ranks (the 'inclusive' method)."""
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def distribution(values, threshold):
    """Median and quartiles for a list of per-person values. Withheld for small groups."""
    values = sorted(values)
    if len(values) < threshold:
        return {"people": None if values else 0, "suppressed": "small_group" if values else None,
                "p25": None, "median": None, "p75": None, "p90": None, "mean": None,
                "top_decile_share": None}
    total = sum(values)
    top = values[-max(1, round(len(values) / 10)):]
    return {"people": len(values), "suppressed": None,
            "p25": quantile(values, 0.25), "median": quantile(values, 0.5),
            "p75": quantile(values, 0.75), "p90": quantile(values, 0.9),
            "mean": total / len(values),
            "top_decile_people": len(top),
            "top_decile_share": (sum(top) / total) if total else None}


class Usage:
    """Index over the canonical day table."""

    def __init__(self, day_table):
        self.counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))    # pid -> tool -> date -> n
        self.features = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))  # pid -> tool -> date -> {feature}
        for row in day_table:
            day = parse_iso(row["date"]) if isinstance(row["date"], str) else row["date"]
            n = int(row["interactions"])
            if n <= 0:
                continue
            self.counts[row["person_id"]][row["tool"]][day] += n
            self.features[row["person_id"]][row["tool"]][day].add(row["feature"])

    def _tools(self, pid, tool):
        per_tool = self.counts.get(pid, {})
        return [per_tool[tool]] if tool in per_tool else [] if tool not in (None, ANY) else list(per_tool.values())

    def interactions(self, pid, first, last, tool=None):
        return sum(n for days in self._tools(pid, tool) for d, n in days.items() if first <= d <= last)

    def active(self, pid, first, last, tool=None):
        return any(first <= d <= last for days in self._tools(pid, tool) for d in days)

    def features_used(self, pid, first, last, tool=None):
        out = set()
        for t, days in self.features.get(pid, {}).items():
            if tool in (None, ANY) or t == tool:
                for d, feats in days.items():
                    if first <= d <= last:
                        out |= {(t, f) for f in feats}
        return out

    def people(self):
        return set(self.counts)


class Analysis:
    """One period of analysis over a roster and a day table."""

    def __init__(self, roster, day_table, config, period_start, period_end):
        self.roster = roster
        self.usage = Usage(day_table)
        self.config = config
        self.start, self.end = period_start, period_end
        self.threshold = int(config.get("suppression_threshold", 5))
        self.lawyer_roles = set(config.get("lawyer_roles", ["partner", "counsel", "associate"]))
        self.weeks = complete_weeks(period_start, period_end)
        if not self.weeks:
            raise ValueError("the period contains no complete ISO week")
        reg = config.get("regular_use", {})
        self.window = int(reg.get("window_weeks", 4))
        self.min_active = int(reg.get("min_active_weeks", 3))
        self.last_weeks = self.weeks[-self.window:]
        self.records = self._person_weeks()
        # People on the roster at period end, with the assignment in effect then.
        self.in_scope = {pid: p.assignment_on(period_end) for pid, p in roster.people.items()
                         if p.employed_on(period_end)}

    # ---- building blocks -------------------------------------------------

    def _person_weeks(self):
        records = []
        for monday in self.weeks:
            sunday = monday + timedelta(days=6)
            for pid, p in self.roster.people.items():
                a = p.assignment_on(max(monday, min(p.start_date, sunday)))
                active = {t: self.usage.active(pid, monday, sunday, t) for t in self.roster.tools}
                records.append({"week": monday, "pid": pid, "status": p.week_status(monday),
                                "role": a.role, "practice": a.practice, "office": a.office,
                                "active": active, "any": any(active.values()),
                                "licensed": p.licences})
        return records

    def is_lawyer(self, role):
        return role in self.lawyer_roles

    def _select(self, weeks, population="lawyers", tool=None, where=None):
        weeks = set(weeks)
        for r in self.records:
            if r["week"] not in weeks or r["status"] != ELIGIBLE:
                continue
            if population == "lawyers" and not self.is_lawyer(r["role"]):
                continue
            if tool not in (None, ANY) and not r["licensed"].get(tool, False):
                continue
            if where and not where(r):
                continue
            yield r

    def weekly_active(self, weeks, population="lawyers", tool=None, where=None):
        """Eligible person-weeks with at least one interaction, over eligible person-weeks."""
        n = d = 0
        people = set()
        for r in self._select(weeks, population, tool, where):
            d += 1
            people.add(r["pid"])
            n += bool(r["any"] if tool in (None, ANY) else r["active"][tool])
        return cell(n, d, len(people))

    def regular_use(self, population="lawyers", tool=None, where=None):
        """People active in at least min_active of the last window weeks.

        Only people eligible in at least min_active of those weeks are counted,
        since nobody else could meet the test. Grouping uses the latest week.
        """
        if len(self.weeks) < self.window:
            return cell(0, 0, 0)
        per = defaultdict(lambda: [0, 0, None])
        for r in self._select(self.last_weeks, population, tool, None):
            entry = per[r["pid"]]
            entry[0] += 1
            entry[1] += bool(r["any"] if tool in (None, ANY) else r["active"][tool])
            entry[2] = r
        n = d = 0
        for elig, act, last in per.values():
            if elig < self.min_active or (where and not where(last)):
                continue
            d += 1
            n += act >= self.min_active
        return cell(n, d)

    def activated(self, population="lawyers", tool=None, where=None):
        """People on the roster at period end with any interaction in the period."""
        n = d = 0
        for pid, a in self.in_scope.items():
            if population == "lawyers" and not self.is_lawyer(a.role):
                continue
            if tool not in (None, ANY) and not self.roster.people[pid].licences.get(tool, False):
                continue
            if where and not where({"role": a.role, "practice": a.practice, "office": a.office}):
                continue
            d += 1
            n += self.usage.active(pid, self.start, self.end, tool)
        return cell(n, d)

    # ---- published sections ----------------------------------------------

    def weekly_trend(self, population="lawyers", tool=None):
        rows = []
        for monday in self.weeks:
            c = self.weekly_active([monday], population, tool)
            excluded = {NOT_STARTED: 0, ON_LEAVE: 0, LEFT: 0}
            for r in self.records:
                if r["week"] == monday and r["status"] != ELIGIBLE and (
                        population != "lawyers" or self.is_lawyer(r["role"])):
                    excluded[r["status"]] += 1
            rows.append({"week": week_label(monday), "week_start": monday.isoformat(),
                         "n": c["n"], "d": c["d"], "rate": c["rate"], "excluded": excluded})
        return rows

    def headline(self):
        latest = [self.weeks[-1]]
        return {
            "weekly_active_latest": self.weekly_active(latest),
            "weekly_active_last_4_weeks": self.weekly_active(self.last_weeks),
            "regular_use": self.regular_use(),
            "activated": self.activated(),
        }

    def tools_table(self):
        days = int(self.config.get("unused_licence_days", 30))
        first = self.end - timedelta(days=days - 1)
        rows = []
        for tool in self.roster.tools:
            licensed = [pid for pid in self.in_scope if self.roster.people[pid].licences.get(tool, False)]
            unused = [pid for pid in licensed if not self.usage.active(pid, first, self.end, tool)]
            absent = [pid for pid in unused if self.roster.people[pid].absent_throughout(first, self.end)]
            cells = {
                "activated": self.activated("all", tool),
                "weekly_active_last_4_weeks": self.weekly_active(self.last_weeks, "all", tool),
                "regular_use": self.regular_use("all", tool),
                "unused_licences": cell(len(unused), len(licensed)),
                "unused_licences_absent_throughout": cell(len(absent), len(unused)),
            }
            if len(licensed) < self.threshold:
                cells = {k: hidden("small_group") for k in cells}
            rows.append({"tool": tool, "licensed": len(licensed) if len(licensed) >= self.threshold else None,
                         "window_days": days, "cells": cells})
        return rows

    def breakdown(self, dim, population):
        """Group table for one dimension, with suppression applied column by column."""
        groups = sorted({getattr(a, dim) for a in self.in_scope.values()
                         if population == "all" or self.is_lawyer(a.role)}
                        | {r[dim] for r in self._select(self.weeks, population)})
        measures = {
            "weekly_active_latest": lambda w: self.weekly_active([self.weeks[-1]], population, None, w),
            "weekly_active_last_4_weeks": lambda w: self.weekly_active(self.last_weeks, population, None, w),
            "regular_use": lambda w: self.regular_use(population, None, w),
            "activated": lambda w: self.activated(population, None, w),
        }
        for tool in self.roster.tools:
            measures["weekly_active_last_4_weeks:" + tool] = (
                lambda w, tool=tool: self.weekly_active(self.last_weeks, population, tool, w))
        rows = [{"group": g, "cells": {}} for g in groups]
        total = {"group": "All", "cells": {}}
        for name, fn in measures.items():
            column = [fn(lambda r, g=g: r[dim] == g) for g in groups]
            for row, c in zip(rows, suppress_cells(column, self.threshold)):
                row["cells"][name] = c
            total["cells"][name] = fn(None)
        return {"dimension": dim, "population": population, "rows": rows, "total": total}

    def tool_population(self, tool):
        """People a per-person measure is computed over.

        Any approved tool: everyone on the roster at period end, all roles.
        A named tool: the same people, restricted to those who hold that
        tool's licence. Use without a licence therefore shows in the any-tool
        figures and under data quality, never in a per-tool figure.
        """
        if tool in (None, ANY):
            return list(self.in_scope)
        return [pid for pid in self.in_scope if self.roster.people[pid].licences.get(tool, False)]

    def intensity(self):
        """Interactions per person over the last window weeks, among people with any."""
        first, last = self.last_weeks[0], self.last_weeks[-1] + timedelta(days=6)
        out = {}
        for tool in [ANY] + self.roster.tools:
            values = [v for v in (self.usage.interactions(pid, first, last, tool)
                                  for pid in self.tool_population(tool)) if v > 0]
            out[tool] = distribution(values, self.threshold)
        return {"window_weeks": len(self.last_weeks), "unit": "interactions per active person",
                "population": POPULATION_NOTE, "by_tool": out}

    def breadth(self):
        """Distinct features used per person over the last window weeks, among people with any."""
        first, last = self.last_weeks[0], self.last_weeks[-1] + timedelta(days=6)
        out = {}
        feature_people = defaultdict(set)
        for tool in [ANY] + self.roster.tools:
            values = []
            for pid in self.tool_population(tool):
                feats = self.usage.features_used(pid, first, last, tool)
                if feats:
                    values.append(len(feats))
                    if tool != ANY:
                        for f in feats:
                            feature_people[f].add(pid)
            d = distribution(values, self.threshold)
            d.pop("top_decile_share", None)
            d.pop("top_decile_people", None)
            if d["people"]:
                d["two_or_more_features"] = cell(sum(1 for v in values if v >= 2), len(values))
            out[tool] = d
        features = []
        for (tool, feature), pids in sorted(feature_people.items()):
            n = len(pids)
            features.append({"tool": tool, "feature": feature,
                             "people": n if n >= self.threshold else None,
                             "suppressed": None if n >= self.threshold else "small_group"})
        return {"window_weeks": len(self.last_weeks), "unit": "features used per active person",
                "population": POPULATION_NOTE, "by_tool": out, "features": features}

    def roster_quality(self):
        people = self.roster.people
        used = self.usage.people()
        leave_weeks = sum(1 for r in self.records if r["status"] == ON_LEAVE and r["any"])
        excluded = {NOT_STARTED: 0, ON_LEAVE: 0, LEFT: 0}
        for r in self.records:
            if r["status"] != ELIGIBLE:
                excluded[r["status"]] += 1
        never_eligible = {r["pid"] for r in self.records} - {r["pid"] for r in self.records if r["status"] == ELIGIBLE}
        return {
            "people_on_roster": len(people),
            "people_on_roster_at_period_end": len(self.in_scope),
            "people_with_no_usage_counted_as_zero": sum(
                1 for pid in people if not self.usage.active(pid, self.start, self.end)),
            "people_who_changed_practice": sum(1 for p in people.values() if p.changed_practice()),
            "people_never_eligible_in_period": len(never_eligible),
            "person_weeks_total": len(self.records),
            "person_weeks_excluded": excluded,
            "person_weeks_with_usage_during_full_leave": leave_weeks,
            "roster_file": {k: v for k, v in self.roster.issues.items()},
            "usage_people_not_on_roster_note": "see unknown_user rows per source",
            "people_with_usage": len(used & set(people)),
        }

    def individual_rows(self):
        """Per-person rows. Off by default; only written when explicitly requested."""
        first, last = self.last_weeks[0], self.last_weeks[-1] + timedelta(days=6)
        rows = []
        for pid, a in sorted(self.in_scope.items()):
            weeks_active = sum(1 for r in self.records if r["pid"] == pid and r["status"] == ELIGIBLE and r["any"])
            rows.append({"person_id": pid, "role": a.role, "practice": a.practice, "office": a.office,
                         "weeks_active": weeks_active,
                         "interactions_period": self.usage.interactions(pid, self.start, self.end),
                         "interactions_last_window": self.usage.interactions(pid, first, last)})
        return rows

    def person_totals(self):
        """Interactions per person over the period. For tests and individual output only."""
        return {pid: self.usage.interactions(pid, self.start, self.end) for pid in self.roster.people}
