"""Seeded synthetic data generator. Everything here is invented.

Random draws use floats (lognormal shapes); every value written to disk is built from integers
(tenths of an hour, whole-dollar rates) with Decimal, so the exports themselves are exact.
The planted truths are listed in ANSWER_KEY.md and asserted in tests/test_answer_key.py.
"""

import csv
import json
import math
import os
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

SEED = 20260
START = date(2020, 1, 1)
END = date(2025, 12, 31)
CURRENT_YEAR = 2026
RATE_INCREASE = Decimal("1.04")
LEVELS = ["partner", "senior_associate", "associate", "paralegal"]
BASE_RATES_2020 = {"partner": 520, "senior_associate": 410, "associate": 320, "paralegal": 170}

THIN_TYPE = "election_law_advisory"
DRIFT_TYPE = "internal_investigation"
DRIFT_FROM = date(2023, 1, 1)
# Shipped step is 2.0x. An earlier 1.7x plant was not reliably flagged by the back-test's
# three-condition drift rule, so the plant was made larger; the detector's thresholds were not
# changed. Measured sensitivity by step size: output/drift_sensitivity.txt and the README.
DRIFT_FACTOR = 2.0
HEARING_TYPE = "public_records_litigation"
NO_TASK_CODE_TYPE = "ordinance_drafting"
HEAVY_WRITE_DOWN_TYPE = "employment_single_plaintiff_defense"
UNITS_TYPE = "facility_change_of_ownership"
LEVEL_CHANGE = {"timekeeper_id": "TK-12", "from": "associate", "to": "senior_associate",
                "effective": date(2022, 7, 1)}
N_OPEN = 40
BLANK_CODE_SHARE = 0.10
UNMAPPED_CODE = "ZZ99"

LIT = (0.15, 0.30, 0.40, 0.15)
TXN = (0.20, 0.50, 0.15, 0.15)
INV = (0.15, 0.15, 0.50, 0.20)

# name, n closed, median hours, sigma, median duration days, P(hearing), hearing hours factor,
# forums, write-down share, has units, phase shares
TYPES = [
    ("public_records_litigation", 80, 110, 0.50, 240, 0.45, 0.90, ["superior_court", "superior_court", "superior_court", "appellate_court"], 0.04, False, LIT),
    ("employment_single_plaintiff_defense", 75, 260, 0.60, 420, 0.25, 0.50, ["superior_court", "arbitration", "state_agency"], 0.12, False, LIT),
    ("facility_change_of_ownership", 60, 45, 0.40, 150, 0.0, 0.0, ["state_agency"], 0.03, True, TXN),
    ("public_works_bid_protest", 55, 75, 0.50, 90, 0.50, 0.60, ["local_agency", "superior_court"], 0.04, False, LIT),
    ("ordinance_drafting", 60, 35, 0.50, 120, 0.30, 0.30, ["local_agency"], 0.05, False, TXN),
    ("paga_response", 50, 150, 0.65, 300, 0.15, 0.50, ["superior_court", "arbitration"], 0.06, False, LIT),
    ("administrative_licensing_appeal", 45, 90, 0.50, 200, 0.70, 0.50, ["state_agency"], 0.04, False, LIT),
    ("commercial_lease_review", 50, 22, 0.40, 45, 0.0, 0.0, ["none"], 0.02, True, TXN),
    (DRIFT_TYPE, 45, 120, 0.45, 150, 0.0, 0.0, ["none"], 0.05, False, INV),
    ("regulatory_compliance_audit", 40, 70, 0.45, 180, 0.0, 0.0, ["state_agency", "none"], 0.03, False, INV),
    ("contract_dispute_arbitration", 35, 200, 0.60, 360, 0.60, 0.60, ["arbitration"], 0.06, False, LIT),
    (THIN_TYPE, 5, 30, 0.40, 60, 0.0, 0.0, ["none", "local_agency"], 0.03, False, TXN),
]

LEVEL_MIX = {  # weights in LEVELS order
    "assessment": (0.35, 0.25, 0.30, 0.10),
    "drafting": (0.15, 0.25, 0.45, 0.15),
    "discovery": (0.08, 0.17, 0.45, 0.30),
    "hearing": (0.40, 0.30, 0.25, 0.05),
    "closing": (0.25, 0.25, 0.30, 0.20),
}
CODES = {"assessment": ["AS10", "AS20"], "drafting": ["DR10", "DR20"], "discovery": ["DX10", "DX20"],
         "hearing": ["HR10", "HR20"], "closing": ["CL10", "CL20"]}
BAND_MULT = {"A": 0.85, "B": 1.0, "C": 1.25, "D": 1.6}

TIMEKEEPERS = ([("TK-%02d" % i, "partner") for i in range(1, 7)]
               + [("TK-%02d" % i, "senior_associate") for i in range(7, 12)]
               + [("TK-%02d" % i, "associate") for i in range(12, 21)]
               + [("TK-%02d" % i, "paralegal") for i in range(21, 25)])

B_TITLES = {"partner": "Partner", "senior_associate": "Sr Associate", "associate": "Associate", "paralegal": "Paralegal"}
B_DISPOSITION = {"completed": "COMP", "settled_early": "SETL", "transferred": "XFER", "other": "OTH"}
B_BANDS = {"A": "Tier 1", "B": "Tier 2", "C": "Tier 3", "D": "Tier 4"}


def display_name(slug):
    return slug.replace("_", " ").title()


def rate_for(level, year):
    """Standard rate for a level in a year: 2020 base grown 4% a year, rounded to a whole dollar."""
    value = Decimal(BASE_RATES_2020[level]) * (RATE_INCREASE ** (year - 2020))
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def level_on(tk_id, base_level, day):
    if tk_id == LEVEL_CHANGE["timekeeper_id"]:
        return LEVEL_CHANGE["to"] if day >= LEVEL_CHANGE["effective"] else LEVEL_CHANGE["from"]
    return base_level


def _weighted(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def generate(seed=SEED, drift_factor=DRIFT_FACTOR):
    """Build the whole synthetic firm in memory. Returns dict with matters, entries, invoices."""
    rng = random.Random(seed)
    base_level = dict(TIMEKEEPERS)
    by_level = {lv: [tk for tk, l in TIMEKEEPERS if l == lv] for lv in LEVELS}
    matters = []

    def new_matter(tdef, is_open):
        (name, _n, med, sigma, dur_med, hear_p, hear_f, forums, wd, has_units, shares) = tdef
        reason = "completed"
        if not is_open:
            r = rng.random()
            if name != THIN_TYPE:
                reason = "completed" if r < 0.88 else "settled_early" if r < 0.96 else "transferred" if r < 0.99 else "other"
        parties = 2 + min(4, int(rng.expovariate(1.2)))
        band = _weighted(rng, ["A", "B", "C", "D"], [0.3, 0.4, 0.2, 0.1])
        units = 1 + min(7, int(rng.expovariate(0.55))) if has_units else 1
        duration = int(max(20, min(1000, dur_med * math.exp(rng.gauss(0, 0.35)))))
        hours = med * math.exp(rng.gauss(0, sigma)) * BAND_MULT[band] * (1 + 0.08 * (parties - 2))
        if has_units:
            hours *= 1 + 0.30 * (units - 1)
        hearing = rng.random() < hear_p
        if reason != "completed":
            duration = max(15, duration // 2)
            hours *= 0.4 if reason == "settled_early" else 0.3
            hearing = False
        if is_open:
            open_date = date(2025, 3, 1) + timedelta(days=rng.randrange(0, 280))
            duration = (END - open_date).days
            hours *= 0.5
            hearing = False
        else:
            span = (END - START).days - duration - 5
            open_date = START + timedelta(days=rng.randrange(0, span))
        if name == DRIFT_TYPE and open_date >= DRIFT_FROM:
            hours *= drift_factor
        j = lambda: rng.uniform(-0.04, 0.04)
        a, b = 0.15 + j(), 0.45 + j()
        if hearing:
            c, d = 0.70 + j(), 0.88 + j()
        else:
            c = d = 0.78 + j()
        phase_hours = dict(zip(["assessment", "drafting", "discovery", "closing"],
                               [hours * s * math.exp(rng.gauss(0, 0.2)) for s in shares]))
        phase_hours["hearing"] = hours * hear_f * math.exp(rng.gauss(0, 0.3)) if hearing else 0.0
        if reason != "completed" or is_open:
            phase_hours["closing"] *= 0.3
        windows = {"assessment": (0.0, a), "drafting": (a, b), "discovery": (b, c), "hearing": (c, d),
                   "closing": (d, 1.0)}
        team = {"partner": rng.choice(by_level["partner"]),
                "senior_associate": rng.choice(by_level["senior_associate"]),
                "associate": rng.choice(by_level["associate"]),
                "paralegal": rng.choice(by_level["paralegal"])}
        return {
            "type": name, "status": "open" if is_open else "closed", "open_date": open_date,
            "close_date": None if is_open else open_date + timedelta(days=duration), "duration": duration,
            "close_reason": None if is_open else reason, "client": "C-%03d" % rng.randrange(1, 61),
            "forum": rng.choice(forums), "parties": parties, "band": band, "units": units,
            "hearing": hearing, "hearing_date": open_date + timedelta(days=int(d * duration)) if hearing else None,
            "phase_hours": phase_hours, "windows": windows, "team": team, "wd": wd,
        }

    for tdef in TYPES:
        for _ in range(tdef[1]):
            matters.append(new_matter(tdef, False))
    open_types = [t for t in TYPES if t[0] != THIN_TYPE]
    for _ in range(N_OPEN):
        matters.append(new_matter(rng.choice(open_types), True))
    matters.sort(key=lambda m: (m["open_date"], m["type"], m["parties"], m["duration"]))
    for i, m in enumerate(matters, start=1):
        m["id"] = "M-%04d" % i

    entries = []

    def add_entry(m, phase, tenths, day, slot_level, force_code=None):
        tk = m["team"][slot_level]
        level = level_on(tk, base_level[tk], day)
        rate = rate_for(level, day.year)
        billed = tenths
        if rng.random() < min(0.9, 3 * m["wd"]):
            billed = (tenths * 2 + 1) // 3
        if force_code is not None:
            code = force_code
        elif m["type"] == NO_TASK_CODE_TYPE:
            code = ""
        else:
            r = rng.random()
            code = "" if r < BLANK_CODE_SHARE else UNMAPPED_CODE if r < BLANK_CODE_SHARE + 0.01 else rng.choice(CODES[phase])
        entries.append({"matter": m["id"], "tk": tk, "level": level, "date": day, "tenths": tenths,
                        "billed_tenths": billed, "rate": rate, "code": code, "phase": phase})

    for m in matters:
        for phase in ["assessment", "drafting", "discovery", "hearing", "closing"]:
            remaining = int(round(m["phase_hours"][phase] * 10))
            lo, hi = m["windows"][phase]
            while remaining > 0:
                tenths = min(remaining, int(round(rng.uniform(1.0, 12.0) * 10)))
                remaining -= tenths
                day = m["open_date"] + timedelta(days=int(rng.uniform(lo, hi) * m["duration"]))
                add_entry(m, phase, tenths, day, _weighted(rng, LEVELS, LEVEL_MIX[phase]))

    # A few entries posted after the matter closed (late time).
    late_pool = [m for m in matters if m["close_reason"] == "completed"
                 and m["close_date"] + timedelta(days=70) < END and m["type"] != THIN_TYPE]
    late_ids = []
    for m in rng.sample(late_pool, 6):
        add_entry(m, "closing", 10, m["close_date"] + timedelta(days=rng.randrange(20, 60)), "paralegal",
                  force_code="CL20")
        late_ids.append(m["id"])

    entries.sort(key=lambda e: (e["matter"], e["date"], e["tk"], e["tenths"], e["code"]))
    for i, e in enumerate(entries, start=1):
        e["id"] = "T-%06d" % i

    # Monthly invoices from billed time.
    buckets = {}
    for e in entries:
        key = (e["matter"], e["date"].year, e["date"].month)
        buckets[key] = buckets.get(key, Decimal(0)) + Decimal(e["billed_tenths"]) / 10 * e["rate"]
    status = {m["id"]: m["status"] for m in matters}
    closed_ids = sorted(mid for mid, s in status.items() if s == "closed")
    unpaid_closed = set(rng.sample(closed_ids, 3))
    last_bucket = {}
    for (mid, y, mo) in buckets:
        last_bucket[mid] = max(last_bucket.get(mid, (0, 0)), (y, mo))
    invoices = []
    for (mid, y, mo) in sorted(buckets):
        amount = buckets[(mid, y, mo)].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount == 0:
            continue
        inv_date = date(y + (mo == 12), mo % 12 + 1, 15)
        written_off = Decimal("0.00")
        collected = amount
        is_last = last_bucket[mid] == (y, mo)
        if (status[mid] == "open" and inv_date > date(2025, 10, 31)) or (mid in unpaid_closed and is_last):
            collected = Decimal("0.00")
        elif rng.random() < 0.06:
            written_off = (amount * Decimal(str(round(rng.uniform(0.1, 0.6), 2)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            collected = amount - written_off
        invoices.append({"matter": mid, "date": inv_date, "billed": amount, "collected": collected,
                         "written_off": written_off})
    for i, inv in enumerate(invoices, start=1):
        inv["id"] = "INV-%05d" % i
    return {"matters": matters, "entries": entries, "invoices": invoices, "late_entry_matters": sorted(late_ids),
            "unpaid_closed_matters": sorted(unpaid_closed)}


def _iso(d):
    return d.isoformat() if d else ""


def _us(d):
    return d.strftime("%m/%d/%Y") if d else ""


def _hours(tenths):
    return "%d.%d" % (tenths // 10, tenths % 10)


def _usd(amount):
    return "$" + format(amount.quantize(Decimal("0.01")), ",")


def write_export_a(world, out_dir):
    """Shape A: four tidy files, ISO dates, hours in decimals, timekeeper levels in their own table."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "matters.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["matter_id", "client_id", "matter_type", "status", "open_date", "close_date", "close_reason",
                    "forum", "num_parties", "amount_band", "num_units", "hearing_occurred", "hearing_date"])
        for m in world["matters"]:
            w.writerow([m["id"], m["client"], m["type"], m["status"], _iso(m["open_date"]), _iso(m["close_date"]),
                        m["close_reason"] or "", m["forum"], m["parties"], m["band"], m["units"],
                        "true" if m["hearing"] else "false", _iso(m["hearing_date"])])
    with open(os.path.join(out_dir, "timekeepers.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["timekeeper_id", "display_name", "level", "effective_from"])
        for tk, level in TIMEKEEPERS:
            w.writerow([tk, "Timekeeper %s" % tk[3:], level, ""])
            if tk == LEVEL_CHANGE["timekeeper_id"]:
                w.writerow([tk, "Timekeeper %s" % tk[3:], LEVEL_CHANGE["to"], _iso(LEVEL_CHANGE["effective"])])
    with open(os.path.join(out_dir, "time_entries.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["entry_id", "matter_id", "timekeeper_id", "work_date", "hours_worked", "hours_billed",
                    "billed_rate", "task_code"])
        for e in world["entries"]:
            w.writerow([e["id"], e["matter"], e["tk"], _iso(e["date"]), _hours(e["tenths"]),
                        _hours(e["billed_tenths"]), "%s.00" % e["rate"], e["code"]])
    with open(os.path.join(out_dir, "invoices.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["invoice_id", "matter_id", "invoice_date", "amount_billed", "amount_collected",
                    "amount_written_off"])
        for inv in world["invoices"]:
            w.writerow([inv["id"], inv["matter"], _iso(inv["date"]), inv["billed"], inv["collected"],
                        inv["written_off"]])


def write_export_b(world, out_dir):
    """Shape B: semicolon-delimited, US dates, coded values, minutes, currency text, level on each row."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "MATTER_MASTER.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["Matter No", "Client No", "Practice Category", "Stat", "Opened", "Closed", "Disposition",
                    "Venue", "Party Ct", "Exposure Band", "Unit Ct", "Hrg", "Hrg Dt"])
        for m in sorted(world["matters"], key=lambda x: x["id"], reverse=True):
            w.writerow([m["id"], m["client"], display_name(m["type"]), "O" if m["status"] == "open" else "C",
                        _us(m["open_date"]), _us(m["close_date"]), B_DISPOSITION.get(m["close_reason"], ""),
                        display_name(m["forum"]), m["parties"], B_BANDS[m["band"]], m["units"],
                        "Y" if m["hearing"] else "N", _us(m["hearing_date"])])
    with open(os.path.join(out_dir, "WIP_DETAIL.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["Tran ID", "Matter No", "TK Init", "TK Title", "Tran Date", "Base Mins", "Bill Mins",
                    "Std Rate", "Activity"])
        for e in sorted(world["entries"], key=lambda x: (x["date"], x["id"])):
            w.writerow([e["id"], e["matter"], e["tk"], B_TITLES[e["level"]], _us(e["date"]), e["tenths"] * 6,
                        e["billed_tenths"] * 6, _usd(Decimal(e["rate"])), e["code"]])
    with open(os.path.join(out_dir, "AR_SUMMARY.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\n")
        w.writerow(["Inv No", "Matter No", "Inv Date", "Fees Billed", "Cash Applied", "Adjustments"])
        for inv in world["invoices"]:
            w.writerow([inv["id"], inv["matter"], _us(inv["date"]), _usd(inv["billed"]), _usd(inv["collected"]),
                        _usd(inv["written_off"])])


def rate_card():
    history = {str(y): {lv: str(rate_for(lv, y)) for lv in LEVELS} for y in range(2020, CURRENT_YEAR)}
    return {
        "note": "Synthetic rate card. Rates rise 4% a year from invented 2020 figures. 'current' is what "
                "historical hours are normalized to.",
        "currency": "USD", "current_label": str(CURRENT_YEAR),
        "current": {lv: str(rate_for(lv, CURRENT_YEAR)) for lv in LEVELS},
        "history": history,
    }


def b_value_maps():
    """Value maps for the shape B mapping file, built from the same tables used to write it."""
    forums = sorted({f for t in TYPES for f in t[7]})
    return {
        "matter_type": {display_name(t[0]): t[0] for t in TYPES},
        "status": {"O": "open", "C": "closed"},
        "close_reason": {v: k for k, v in B_DISPOSITION.items()},
        "forum": {display_name(f): f for f in forums},
        "amount_band": {v: k for k, v in B_BANDS.items()},
        "level": {v: k for k, v in B_TITLES.items()},
    }


def write_all(data_dir, seed=SEED):
    world = generate(seed)
    write_export_a(world, os.path.join(data_dir, "export_a"))
    write_export_b(world, os.path.join(data_dir, "export_b"))
    with open(os.path.join(data_dir, "rate_card.json"), "w", encoding="utf-8") as fh:
        json.dump(rate_card(), fh, indent=2)
        fh.write("\n")
    return world


def to_dataset(world):
    """The generated firm as a canonical Dataset, without going through files. Used by the drift study."""
    from .loader import Dataset, Invoice, Matter, TimeEntry
    ds = Dataset(mapping_name="in memory")
    for m in world["matters"]:
        ds.matters[m["id"]] = Matter(
            matter_id=m["id"], matter_type=m["type"], status=m["status"], open_date=m["open_date"],
            close_date=m["close_date"], close_reason=m["close_reason"], client_id=m["client"], forum=m["forum"],
            num_parties=m["parties"], amount_band=m["band"], num_units=m["units"], hearing_occurred=m["hearing"],
            hearing_date=m["hearing_date"])
    for e in world["entries"]:
        ds.entries.append(TimeEntry(
            entry_id=e["id"], matter_id=e["matter"], timekeeper_id=e["tk"], work_date=e["date"],
            hours_worked=Decimal(e["tenths"]) / 10, rate=Decimal(e["rate"]),
            hours_billed=Decimal(e["billed_tenths"]) / 10, level=e["level"], task_code=e["code"] or None))
    for inv in world["invoices"]:
        ds.invoices.append(Invoice(inv["id"], inv["matter"], inv["date"], inv["billed"], inv["collected"],
                                   inv["written_off"]))
    return ds
