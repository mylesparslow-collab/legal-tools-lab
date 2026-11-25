"""Small hand-built datasets for unit tests."""

from datetime import date
from decimal import Decimal

from feemodel.cost import TaskCodeMap
from feemodel.loader import Dataset, Invoice, Matter, TimeEntry

D = Decimal
RATES = {"partner": D("600"), "associate": D("400"), "paralegal": D("200")}
COSTS = {"partner": D("200"), "associate": D("100"), "paralegal": D("50")}
CODE_MAP = TaskCodeMap(prefixes={"AS": "assessment", "DR": "drafting", "DX": "discovery", "HR": "hearing", "CL": "closing"})


def d(text):
    return date.fromisoformat(text)


def mk_matter(mid, mtype="widget_dispute", open_="2021-01-01", close="2021-06-30", status="closed",
              reason="completed", **kw):
    return Matter(matter_id=mid, matter_type=mtype, status=status, open_date=d(open_),
                  close_date=d(close) if close else None, close_reason=reason, **kw)


def mk_entry(eid, mid, day, hours, rate="300", level="associate", code="DR10", billed=None, tk="TK-1"):
    hours = D(str(hours))
    return TimeEntry(entry_id=eid, matter_id=mid, timekeeper_id=tk, work_date=d(day), hours_worked=hours,
                     rate=D(rate), hours_billed=hours if billed is None else D(str(billed)), level=level,
                     task_code=code)


def mk_invoice(iid, mid, day, billed, collected, written_off="0"):
    return Invoice(iid, mid, d(day), D(billed), D(collected), D(written_off))


def mk_dataset(matters, entries=(), invoices=()):
    ds = Dataset()
    for m in matters:
        ds.matters[m.matter_id] = m
    ds.entries = list(entries)
    ds.invoices = list(invoices)
    return ds


def simple_history(values, mtype="widget_dispute", start_year=2015):
    """One closed matter per value, each opening after the previous one closed. Value = hours x 400."""
    matters, entries = [], []
    for i, hours in enumerate(values):
        y = start_year + i
        mid = "H-%02d" % i
        matters.append(mk_matter(mid, mtype, "%d-01-10" % y, "%d-06-30" % y))
        entries.append(mk_entry("E-%02d" % i, mid, "%d-02-01" % y, hours))
    return mk_dataset(matters, entries)
