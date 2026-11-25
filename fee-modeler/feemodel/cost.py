"""Per-matter cost: hours by phase and level, worked vs billed vs collected, raw vs normalized.

Three money views of the same matter, kept apart on purpose:

- raw worked value: hours worked x the rate in force when the work was done
- normalized value: hours worked x today's rate card for each level (what the same work
  would be valued at now, at standard rates, before any write-down)
- internal cost: hours worked x a cost rate per level that the user supplies
"""

from dataclasses import dataclass, field as dc_field
from decimal import Decimal

from .money import ZERO, ONE, D
from .schema import PHASES

# Date-window fallback, used only when an entry has no usable task code.
# Position of the work date in the matter's life, as a percentage of open-to-close.
FALLBACK_WINDOWS = [(15, "assessment"), (45, "drafting"), (80, "discovery"), (101, "closing")]
HEARING_WINDOW_DAYS = 21
LOW_CONFIDENCE_SHARE = Decimal("0.20")  # more than this share of hours by fallback = low confidence


class TaskCodeMap:
    """Task code -> phase. Exact codes win, then the longest matching prefix."""

    def __init__(self, exact=None, prefixes=None):
        self.exact = dict(exact or {})
        self.prefixes = dict(prefixes or {})
        for phase in list(self.exact.values()) + list(self.prefixes.values()):
            if phase not in PHASES:
                raise ValueError("task code map names unknown phase %r; phases are %s" % (phase, ", ".join(PHASES)))

    @classmethod
    def from_dict(cls, raw):
        return cls(exact=raw.get("exact", {}), prefixes=raw.get("prefixes", {}))

    def phase_for(self, code):
        if not code:
            return None
        if code in self.exact:
            return self.exact[code]
        for prefix in sorted(self.prefixes, key=len, reverse=True):
            if code.startswith(prefix):
                return self.prefixes[prefix]
        return None


def fallback_phase(work_date, matter, end_date=None):
    """Phase from date windows. Lower confidence than a task code; see FALLBACK_WINDOWS."""
    if matter.hearing_date is not None:
        gap = (matter.hearing_date - work_date).days
        if 0 <= gap <= HEARING_WINDOW_DAYS:
            return "hearing"
    end = matter.close_date or end_date or work_date
    total = (end - matter.open_date).days
    if total <= 0:
        return "assessment"
    elapsed = (work_date - matter.open_date).days
    elapsed = max(0, min(elapsed, total))
    for limit, phase in FALLBACK_WINDOWS:
        if elapsed * 100 < limit * total:
            return phase
    return "closing"


def assign_phase(entry, matter, code_map):
    """Return (phase, source) where source is 'task_code' or 'date_window'."""
    phase = code_map.phase_for(entry.task_code) if code_map else None
    if phase is not None:
        return phase, "task_code"
    return fallback_phase(entry.work_date, matter), "date_window"


@dataclass
class MatterCost:
    matter: object
    hours: dict = dc_field(default_factory=dict)        # (phase, level) -> hours worked
    hours_billed: Decimal = ZERO
    raw_worked: Decimal = ZERO
    raw_billed: Decimal = ZERO
    invoiced: Decimal = ZERO
    collected: Decimal = ZERO
    written_off: Decimal = ZERO
    write_off_known: bool = True
    fallback_hours: Decimal = ZERO
    billed_assumed: bool = False
    n_entries: int = 0
    last_entry_date: object = None

    @property
    def matter_id(self):
        return self.matter.matter_id

    @property
    def total_hours(self):
        return sum(self.hours.values(), ZERO)

    def hours_by_phase(self, reductions=None):
        out = {p: ZERO for p in PHASES}
        for (phase, _level), h in self.hours.items():
            out[phase] += h * _keep(reductions, phase)
        return out

    def hours_by_level(self, reductions=None):
        out = {}
        for (phase, level), h in self.hours.items():
            out[level] = out.get(level, ZERO) + h * _keep(reductions, phase)
        return out

    def value_by_phase(self, rates, reductions=None):
        """Hours x a per-level rate table (rate card or cost rates), by phase."""
        out = {p: ZERO for p in PHASES}
        for (phase, level), h in self.hours.items():
            if level not in rates:
                raise KeyError("no rate for level %r (matter %s); add it to the rate file"
                               % (level, self.matter_id))
            out[phase] += h * _keep(reductions, phase) * rates[level]
        return out

    def value_total(self, rates, reductions=None):
        return sum(self.value_by_phase(rates, reductions).values(), ZERO)

    def phases_occurred(self):
        return {p for p, h in self.hours_by_phase().items() if h > 0}

    @property
    def write_down(self):
        """Worked value that was never billed."""
        return self.raw_worked - self.raw_billed

    @property
    def uncollected(self):
        """Billed on invoices but not collected (written off or still outstanding)."""
        return self.invoiced - self.collected

    @property
    def fallback_share(self):
        total = self.total_hours
        return (self.fallback_hours / total) if total > 0 else ZERO

    @property
    def phase_confidence(self):
        return "date_window" if self.fallback_share > LOW_CONFIDENCE_SHARE else "task_code"


def _keep(reductions, phase):
    if not reductions:
        return ONE
    return ONE - reductions.get(phase, ZERO)


def parse_reductions(raw):
    """User-typed hours reductions by phase, as percentages (0-100). Returns fractions."""
    out = {}
    for phase, pct in (raw or {}).items():
        if phase not in PHASES:
            raise ValueError("unknown phase %r in hours-reduction assumptions" % phase)
        value = D(pct)      # strings or whole numbers only; floats are refused
        if value < 0 or value > 100:
            raise ValueError("hours reduction for %s must be between 0 and 100 percent" % phase)
        if value != 0:
            out[phase] = value / Decimal("100")
    return out


def build_cost(matter, entries, invoices, code_map, as_of=None):
    """Cost for one matter. With as_of, anything dated after that day is ignored."""
    mc = MatterCost(matter=matter)
    for e in entries:
        if as_of is not None and e.work_date > as_of:
            continue
        phase, source = assign_phase(e, matter, code_map)
        key = (phase, e.level)
        mc.hours[key] = mc.hours.get(key, ZERO) + e.hours_worked
        mc.hours_billed += e.hours_billed
        mc.raw_worked += e.amount_worked
        mc.raw_billed += e.amount_billed
        if source == "date_window":
            mc.fallback_hours += e.hours_worked
        if e.billed_assumed:
            mc.billed_assumed = True
        mc.n_entries += 1
        if mc.last_entry_date is None or e.work_date > mc.last_entry_date:
            mc.last_entry_date = e.work_date
    for inv in invoices:
        if as_of is not None and inv.invoice_date > as_of:
            continue
        mc.invoiced += inv.amount_billed
        mc.collected += inv.amount_collected
        if inv.amount_written_off is None:
            mc.write_off_known = False
        else:
            mc.written_off += inv.amount_written_off
    return mc


class CostBook:
    """Costs for every matter, with an as-of view for the back-test.

    cost(matter_id) uses everything on file. cost_as_of(matter_id, day) ignores entries and
    invoices dated after `day`, so a back-test cannot see time posted later.
    """

    def __init__(self, dataset, code_map):
        self.dataset = dataset
        self.code_map = code_map
        self._entries = dataset.entries_by_matter()
        self._invoices = dataset.invoices_by_matter()
        self._full = {}
        self._asof = {}

    def cost(self, matter_id):
        if matter_id not in self._full:
            self._full[matter_id] = build_cost(self.dataset.matters[matter_id],
                                               self._entries.get(matter_id, []),
                                               self._invoices.get(matter_id, []), self.code_map)
        return self._full[matter_id]

    def cost_as_of(self, matter_id, day):
        full = self.cost(matter_id)
        last_inv = max((i.invoice_date for i in self._invoices.get(matter_id, [])), default=None)
        if (full.last_entry_date is None or full.last_entry_date <= day) and (last_inv is None or last_inv <= day):
            return full
        key = (matter_id, day)
        if key not in self._asof:
            self._asof[key] = build_cost(self.dataset.matters[matter_id], self._entries.get(matter_id, []),
                                         self._invoices.get(matter_id, []), self.code_map, as_of=day)
        return self._asof[key]

    def all_costs(self):
        return {mid: self.cost(mid) for mid in self.dataset.matters}
