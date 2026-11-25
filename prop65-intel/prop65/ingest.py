"""Parse Attorney General 60-day notice CSV exports into notices and resolution events.

The OAG export ("Search Results w/ Segments") has one row per notice per attached segment:
a complaint, a settlement report, a judgment or a withdrawal. A notice with nothing attached
has one row with empty segment columns.
"""
from __future__ import annotations
import csv, gzip, io, json, re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path

from .rules import load_product_classes, RULES_DIR

EXPECTED_HEADER = ["AG Number", "Date", "Noticing Party", "Plaintiff Attorney", "Alleged Violator(s)",
                   "Chemicals", "Source", "Comments", "Case ID", "Case Name", "Court Docket Number",
                   "Civil Penalty", "Attorney Fees", "Other Payments", "Type of Claim", "Relief Sought",
                   "Injunctive Relief"]

_SUFFIX = re.compile(r"\b(a professional corporation|professional corporation|a law corporation|law corporation|"
                     r"law firm|law group|law offices of|law office of|attorneys at law|apc|aplc|pc|plc|llp|llc|inc|"
                     r"corp|corporation|the)\b")


def firm_key(name: str) -> str:
    """Stable key for a plaintiff firm or noticing party: case, punctuation and entity suffixes removed."""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _SUFFIX.sub(" ", s)
    s = re.sub(r"\b[a-z]\b", " ", s)          # middle initials: "Evan J. Smith" and "Evan Smith" are one firm
    return re.sub(r"\s+", " ", s).strip()


def chemical_key(name: str) -> str:
    """Group spelling variants of the most common chemicals. Unknown names pass through lowercased."""
    s = name.strip().lower()
    table = [
        (r"\blead\b", "Lead"), (r"\bcadmium\b", "Cadmium"), (r"dehp|di\(2-ethylhexyl\)", "DEHP"),
        (r"dinp|diisononyl", "DINP"), (r"\bdbp\b|di-n-butyl", "DBP"), (r"\bbbp\b|butyl benzyl", "BBP"),
        (r"didp|di-isodecyl|diisodecyl", "DIDP"), (r"dnhp|di-n-hexyl", "DnHP"),
        (r"bisphenol a|\bbpa\b", "BPA"), (r"bisphenol s|\bbps\b", "BPS"), (r"acrylamide", "Acrylamide"),
        (r"arsenic", "Arsenic"), (r"mercury", "Mercury"), (r"pfoa|perfluorooctanoic", "PFOA"),
        (r"pfos|perfluorooctane sulf", "PFOS"), (r"pfna|perfluorononanoic", "PFNA"),
        (r"formaldehyde", "Formaldehyde"), (r"benzene", "Benzene"), (r"diethanolamine", "Diethanolamine"),
        (r"chromium", "Chromium (hexavalent)"), (r"tobacco smoke", "Tobacco smoke"),
        (r"carbon monoxide", "Carbon monoxide"), (r"titanium dioxide", "Titanium dioxide"),
        (r"1,4-dioxane", "1,4-Dioxane"), (r"tdcpp|tris\(1,3-dichloro", "TDCPP"), (r"styrene", "Styrene"),
        (r"exhaust", "Engine exhaust"), (r"wood dust", "Wood dust"), (r"alcohol", "Alcohol"),
        (r"marijuana|cannabis|thc|tetrahydrocannabinol", "Cannabis smoke / THC"),
    ]
    for pat, label in table:
        if re.search(pat, s):
            return label
    return name.strip()


def split_chemicals(field_value: str) -> list[str]:
    """The export joins chemicals with ', ' but some names contain commas (1,4-Dioxane). Split conservatively."""
    out, seen = [], set()
    for part in re.split(r",\s+(?![0-9]-)", field_value or ""):
        k = chemical_key(part) if part.strip() else ""
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out


def product_class(source: str) -> str:
    s = (source or "").lower()
    for c in load_product_classes():
        if any(re.search(r"\b" + re.escape(k), s) for k in c["keywords"]):
            return c["id"]
    return "other"


def product_class_labels() -> dict[str, str]:
    d = {c["id"]: c["label"] for c in load_product_classes()}
    d["other"] = json.loads((RULES_DIR / "product_classes.json").read_text())["fallback"]["label"]
    return d


def _money(s: str):
    s = (s or "").replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class Event:
    kind: str            # settlement | judgment | complaint | withdrawal
    seg_id: int | None
    case_name: str
    docket: str
    civil_penalty: float | None = None
    attorney_fees: float | None = None
    other_payments: float | None = None
    injunctive_relief: str = ""
    court_entered: bool = False          # a judgment with the same docket and amounts exists
    ag_numbers: list = field(default_factory=list)

    @property
    def total(self) -> float:
        return (self.civil_penalty or 0) + (self.attorney_fees or 0) + (self.other_payments or 0)


@dataclass
class Notice:
    ag_number: str
    date: date
    noticing_party: str
    plaintiff_attorney: str
    violators: str
    chemicals: list
    source: str
    comments: str
    product_class: str
    events: list = field(default_factory=list)

    @property
    def firm(self) -> str:
        return firm_key(self.plaintiff_attorney) or firm_key(self.noticing_party)

    def has(self, kind: str) -> bool:
        return any(e.kind == kind for e in self.events)

    @property
    def is_followup(self) -> bool:
        return bool(re.search(r"amend|supplement|renotice|re-notice|relates to", self.comments, re.I))


def _open(path: Path):
    if str(path).endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig", newline="")
    return open(path, newline="", encoding="utf-8-sig")


def read_rows(paths) -> list[dict]:
    rows = []
    for p in paths:
        with _open(Path(p)) as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                continue
            if [h.strip() for h in header] != EXPECTED_HEADER:
                raise ValueError(f"{p}: unexpected header {header!r}. The OAG export format may have changed.")
            for rec in reader:
                if len(rec) != len(EXPECTED_HEADER):
                    continue
                if rec[0] == "AG Number":      # header repeated in a concatenated file
                    continue
                rows.append(dict(zip(EXPECTED_HEADER, rec)))
    return rows


def build_notices(rows: list[dict]) -> dict[str, Notice]:
    notices: dict[str, Notice] = {}
    seen_seg = set()
    for r in rows:
        ag = r["AG Number"].strip()
        if not re.fullmatch(r"\d{4}-\d{5}", ag):
            continue
        n = notices.get(ag)
        if n is None:
            n = notices[ag] = Notice(
                ag_number=ag, date=datetime.strptime(r["Date"].strip(), "%m/%d/%Y").date(),
                noticing_party=r["Noticing Party"].strip(), plaintiff_attorney=r["Plaintiff Attorney"].strip(),
                violators=r["Alleged Violator(s)"].strip(), chemicals=split_chemicals(r["Chemicals"]),
                source=r["Source"].strip(), comments=r["Comments"].strip(), product_class=product_class(r["Source"]))
        m = re.fullmatch(r"(Settlement|Judgment|Complaint|Withdrawal)\s+(\d+)", r["Case ID"].strip())
        if not m:
            continue
        key = (ag, m.group(1), m.group(2))
        if key in seen_seg:               # overlapping date windows can repeat a row
            continue
        seen_seg.add(key)
        n.events.append(Event(kind=m.group(1).lower(), seg_id=int(m.group(2)), case_name=r["Case Name"].strip(),
                              docket=r["Court Docket Number"].strip(), civil_penalty=_money(r["Civil Penalty"]),
                              attorney_fees=_money(r["Attorney Fees"]), other_payments=_money(r["Other Payments"]),
                              injunctive_relief=r["Injunctive Relief"].strip(), ag_numbers=[ag]))
    return notices


def _docket_key(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", s.lower())
    return "" if s in {"na", "notapplicable", "litigationwasnotfiled", "none", "notfiled", "nofiling"} else s


def resolutions(notices: dict[str, Notice], id_window: int = 3, large_dup_usd: float = 250000) -> list[dict]:
    """Collapse settlement and judgment segments into distinct payment events.

    Two heuristics, both stated in the README because they change the counts:
      1. A judgment on the same notice with the same docket and the same three amounts as a settlement
         is the court entering that settlement. It is counted once and marked court_entered.
      2. The same settlement is often reported once per notice it resolves (original and amended
         notices). Segments from the same noticing party with identical amounts, the same docket text
         and report IDs within `id_window` of each other are merged into one event.
      3. A large global settlement in a multi-defendant case is reported under many notices, sometimes
         as both settlement and judgment. Events from the same noticing party with the same docket
         number and the same total of `large_dup_usd` or more are merged into one.
    """
    raw = []
    for n in notices.values():
        setts = [e for e in n.events if e.kind == "settlement"]
        judgs = [e for e in n.events if e.kind == "judgment"]
        used = set()
        for s in setts:
            for j in judgs:
                if id(j) in used:
                    continue
                if (_docket_key(j.docket) == _docket_key(s.docket) and _docket_key(s.docket)
                        and (j.civil_penalty, j.attorney_fees, j.other_payments) ==
                        (s.civil_penalty, s.attorney_fees, s.other_payments)):
                    s.court_entered = True; used.add(id(j)); break
            raw.append((n, s))
        for j in judgs:
            if id(j) not in used:
                raw.append((n, j))
    groups = defaultdict(list)
    for n, e in raw:
        groups[(firm_key(n.noticing_party), e.kind, e.civil_penalty, e.attorney_fees, e.other_payments,
                _docket_key(e.docket))].append((n, e))
    out = []
    for items in groups.values():
        items.sort(key=lambda t: t[1].seg_id or 0)
        cluster = [items[0]]
        for it in items[1:]:
            same_notice = it[0].ag_number in {c[0].ag_number for c in cluster}
            if not same_notice and (it[1].seg_id - cluster[-1][1].seg_id) <= id_window:
                cluster.append(it)
            else:
                out.append(_merge(cluster)); cluster = [it]
        out.append(_merge(cluster))
    big, final = {}, []
    for r in out:
        if r["total"] >= large_dup_usd and r["litigated"]:
            k = (firm_key(r["noticing_party"]), _docket_key(r["docket"]), r["total"])
            if k in big:
                b = big[k]
                b["ag_numbers"] = sorted(set(b["ag_numbers"]) | set(r["ag_numbers"]))
                b["seg_ids"] += r["seg_ids"]
                b["court_entered"] = b["court_entered"] or r["court_entered"]
                b["notice_date"] = min(b["notice_date"], r["notice_date"])
                continue
            big[k] = r
        final.append(r)
    return final


def _merge(cluster) -> dict:
    n, e = cluster[0]
    ags = sorted({c[0].ag_number for c in cluster})
    chems, seen = [], set()
    for c in cluster:
        for ch in c[0].chemicals:
            if ch not in seen:
                seen.add(ch); chems.append(ch)
    return {
        "kind": e.kind, "seg_ids": [c[1].seg_id for c in cluster], "ag_numbers": ags,
        "notice_date": min(c[0].date for c in cluster), "noticing_party": n.noticing_party,
        "plaintiff_attorney": n.plaintiff_attorney, "firm": n.firm, "chemicals": chems,
        "product_class": n.product_class, "source": n.source, "violators": n.violators,
        "case_name": e.case_name, "docket": e.docket, "litigated": bool(_docket_key(e.docket)),
        "court_entered": e.court_entered or e.kind == "judgment",
        "civil_penalty": e.civil_penalty or 0.0, "attorney_fees": e.attorney_fees or 0.0,
        "other_payments": e.other_payments or 0.0, "total": e.total, "injunctive_relief": e.injunctive_relief,
    }


def load(paths) -> tuple[dict[str, Notice], list[dict]]:
    notices = build_notices(read_rows(paths))
    return notices, resolutions(notices)
