"""Comparable-matter selection. The rules are data, are printed with every result, and can be changed."""

from dataclasses import dataclass, field as dc_field
from datetime import date
from typing import Optional

DEFAULT_MIN_COMPS = 8
DEFAULT_BAND_ORDER = ["A", "B", "C", "D"]


class InsufficientComps(Exception):
    """Raised instead of producing a number from too few comparable matters."""

    def __init__(self, message, selection):
        super().__init__(message)
        self.selection = selection


@dataclass
class SelectionRules:
    forum: str = "any"                      # "any" or "same"
    num_parties_tolerance: Optional[int] = None   # None = ignore; else comps within +/- this many parties
    amount_band: str = "any"                # "any", "same" or "adjacent"
    num_units_range: Optional[list] = None  # None = ignore; else [min, max] inclusive
    hearing: str = "any"                    # "any" or "same"
    closed_within_years: Optional[int] = None     # None = all history; else only comps closed this recently
    include_abnormal: bool = False          # include matters settled early, transferred, etc.
    min_comps: int = DEFAULT_MIN_COMPS
    band_order: list = dc_field(default_factory=lambda: list(DEFAULT_BAND_ORDER))

    @classmethod
    def from_dict(cls, raw):
        raw = dict(raw or {})
        known = set(cls.__dataclass_fields__)
        unknown = set(raw) - known
        if unknown:
            raise ValueError("unknown selection rule(s): %s" % ", ".join(sorted(unknown)))
        rules = cls(**raw)
        if rules.forum not in ("any", "same"):
            raise ValueError("forum rule must be 'any' or 'same'")
        if rules.amount_band not in ("any", "same", "adjacent"):
            raise ValueError("amount_band rule must be 'any', 'same' or 'adjacent'")
        if rules.hearing not in ("any", "same"):
            raise ValueError("hearing rule must be 'any' or 'same'")
        if rules.min_comps < 1:
            raise ValueError("min_comps must be at least 1")
        return rules

    def describe(self, matter_type, attrs, as_of):
        """The rules in plain sentences, in the order they are applied."""
        lines = [
            "Matter type is %s." % matter_type,
            "Closed before %s (open matters are never comps)." % as_of.isoformat(),
        ]
        if self.include_abnormal:
            lines.append("Matters that closed abnormally (settled early, transferred, other) are included and flagged.")
        else:
            lines.append("Matters that closed abnormally (settled early, transferred, other) are excluded.")
        if self.closed_within_years is not None:
            lines.append("Closed within the %d years before %s." % (self.closed_within_years, as_of.isoformat()))
        if self.forum == "same":
            lines.append("Same forum as proposed (%s)." % attrs.get("forum"))
        if self.num_parties_tolerance is not None:
            lines.append("Number of parties within %d of proposed (%s)."
                         % (self.num_parties_tolerance, attrs.get("num_parties")))
        if self.amount_band == "same":
            lines.append("Same amount band as proposed (%s)." % attrs.get("amount_band"))
        elif self.amount_band == "adjacent":
            lines.append("Amount band the same as or next to proposed (%s; order %s)."
                         % (attrs.get("amount_band"), " < ".join(self.band_order)))
        if self.num_units_range is not None:
            lines.append("Number of units between %d and %d." % tuple(self.num_units_range))
        if self.hearing == "same":
            lines.append("Hearing occurred: %s, as expected for the proposed matter."
                         % ("yes" if attrs.get("hearing_expected") else "no"))
        lines.append("At least %d comps are required before any figure is shown." % self.min_comps)
        return lines


@dataclass
class CompSelection:
    matter_type: str
    attrs: dict
    as_of: date
    rules: SelectionRules
    included: list = dc_field(default_factory=list)   # Matter objects
    flags: dict = dc_field(default_factory=dict)      # matter_id -> list of flag strings
    excluded: list = dc_field(default_factory=list)   # (Matter, [reasons])
    relax_hints: dict = dc_field(default_factory=dict)  # rule name -> matters gained if that rule alone were dropped
    type_total: int = 0

    @property
    def n(self):
        return len(self.included)

    def rule_lines(self):
        return self.rules.describe(self.matter_type, self.attrs, self.as_of)

    def exclusion_counts(self):
        counts = {}
        for _m, reasons in self.excluded:
            for r in reasons:
                counts[r] = counts.get(r, 0) + 1
        return counts

    def shortfall_message(self):
        need = self.rules.min_comps - self.n
        parts = ["Not modeled: %d comparable closed matters of type %s found, %d required."
                 % (self.n, self.matter_type, self.rules.min_comps),
                 "%d more are needed." % need]
        if self.relax_hints:
            hints = ["%s (+%d)" % (rule, gain) for rule, gain in sorted(self.relax_hints.items(), key=lambda kv: -kv[1])]
            parts.append("Relaxing one rule on its own would add: %s." % ", ".join(hints))
        else:
            parts.append("No single rule change would add comps; this matter type needs more closed history.")
        return " ".join(parts)


def _years_before(day, years):
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def _attribute_failures(m, attrs, rules, as_of):
    """Names of the adjustable rules this matter fails."""
    failed = []
    if m.is_abnormal_close and not rules.include_abnormal:
        failed.append("abnormal close excluded")
    if rules.closed_within_years is not None and m.close_date < _years_before(as_of, rules.closed_within_years):
        failed.append("closed too long ago")
    if rules.forum == "same" and m.forum != attrs.get("forum"):
        failed.append("different forum")
    if rules.num_parties_tolerance is not None:
        want = attrs.get("num_parties")
        if want is None or m.num_parties is None or abs(m.num_parties - int(want)) > rules.num_parties_tolerance:
            failed.append("number of parties out of range")
    if rules.amount_band != "any":
        want = attrs.get("amount_band")
        ok = False
        if want is not None and m.amount_band is not None:
            if rules.amount_band == "same":
                ok = m.amount_band == want
            elif want in rules.band_order and m.amount_band in rules.band_order:
                ok = abs(rules.band_order.index(want) - rules.band_order.index(m.amount_band)) <= 1
        if not ok:
            failed.append("amount band out of range")
    if rules.num_units_range is not None:
        lo, hi = rules.num_units_range
        if m.num_units is None or not (lo <= m.num_units <= hi):
            failed.append("number of units out of range")
    if rules.hearing == "same":
        if m.hearing_occurred is None or bool(m.hearing_occurred) != bool(attrs.get("hearing_expected")):
            failed.append("hearing does not match")
    return failed


def select_comps(dataset, matter_type, attrs, rules, as_of, exclude_ids=()):
    """Pick comps for a proposed matter. Returns a CompSelection; does not enforce the minimum."""
    sel = CompSelection(matter_type=matter_type, attrs=dict(attrs or {}), as_of=as_of, rules=rules)
    gains = {}
    for m in sorted(dataset.matters.values(), key=lambda x: (x.close_date or date.max, x.matter_id)):
        if m.matter_type != matter_type or m.matter_id in exclude_ids:
            continue
        sel.type_total += 1
        # Hard rules: never adjustable.
        if m.status != "closed":
            sel.excluded.append((m, ["open matter"]))
            continue
        if m.close_date is None:
            sel.excluded.append((m, ["closed without a close date"]))
            continue
        if not (m.close_date < as_of):
            sel.excluded.append((m, ["closed on or after the as-of date"]))
            continue
        failed = _attribute_failures(m, sel.attrs, rules, as_of)
        if failed:
            sel.excluded.append((m, failed))
            if len(failed) == 1:
                gains[failed[0]] = gains.get(failed[0], 0) + 1
            continue
        flags = []
        if m.is_abnormal_close:
            flags.append("closed abnormally: %s" % m.close_reason)
        if m.close_reason is None:
            flags.append("close reason missing")
        sel.included.append(m)
        sel.flags[m.matter_id] = flags
    sel.relax_hints = gains
    return sel


def require_min(selection):
    """Raise InsufficientComps when the selection is below the configured minimum."""
    if selection.n < selection.rules.min_comps:
        raise InsufficientComps(selection.shortfall_message(), selection)
    return selection
