"""CPRA records desk: response clocks, legacy-cite mapping, exemption proposals and a privilege log.
Proposals are suggestions. Nothing is treated as withheld until a named reviewer approves it."""
import csv
import re
from datetime import date, datetime, timedelta

from .rules import cpra, finding, load


def _d(s):
    return date.fromisoformat(s) if s else None


def roll_forward(d: date, holidays: set) -> date:
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d += timedelta(days=1)
    return d


def deadlines(req: dict, today: date | None = None) -> dict:
    """req keys: id, received, extension_notice_date, extension_reason, extension_to, determination_sent."""
    R = cpra()
    hol = set(load("holidays")["dates"]) if R["roll_forward"]["enabled"] else None
    roll = (lambda d: roll_forward(d, hol)) if hol is not None else (lambda d: d)
    recv = _d(req["received"])
    raw_due = recv + timedelta(days=R["determination"]["days"])
    due = roll(raw_due)
    ext_max = roll(raw_due + timedelta(days=R["extension"]["max_days"]))
    findings = []
    effective = due
    note_d, reason, ext_to = _d(req.get("extension_notice_date")), (req.get("extension_reason") or "").strip(), _d(req.get("extension_to"))
    if note_d or reason or ext_to:
        ok = True
        if not re.fullmatch(r"c\d", reason) or reason not in R["unusual_circumstances"]:
            ok = False
            findings.append(finding("fail", "ext_reason", f"Extension reason '{reason}' is not one of the listed unusual circumstances.", R["unusual_circumstances"]))
        if note_d is None:
            ok = False
            findings.append(finding("fail", "ext_notice", "Extension claimed but no written notice date recorded.", R["extension"]))
        elif note_d > due:
            ok = False
            findings.append(finding("fail", "ext_late", f"Extension notice dated {note_d} is after the determination deadline of {due}.", R["extension"]))
        target = ext_to or ext_max
        if target > ext_max:
            ok = False
            findings.append(finding("fail", "ext_too_long", f"Extension to {target} is more than 14 days past the original deadline. Latest allowed is {ext_max}.", R["extension"]))
        if ext_to is None and note_d:
            findings.append(finding("review", "ext_no_date", "Extension notice must state the date a determination is expected.", R["extension"]))
        if ok:
            effective = target
            findings.append(finding("pass", "ext_ok", f"Extension to {target} for: {R['unusual_circumstances'][reason]}.", R["extension"]))
    if raw_due != due:
        findings.append(finding("info", "rolled", f"Day 10 is {raw_due:%A %Y-%m-%d}; moved to {due}.", R["roll_forward"]))
    sent = _d(req.get("determination_sent"))
    today = today or date.today()
    if sent:
        status = "sent on time" if sent <= effective else f"sent {(sent - effective).days} day(s) late"
        findings.append(finding("pass" if sent <= effective else "fail", "determination", f"Determination {status}.", R["determination"]))
    else:
        left = (effective - today).days
        status = f"due in {left} day(s)" if left > 0 else ("due today" if left == 0 else f"overdue by {-left} day(s)")
        findings.append(finding("fail" if left < 0 else ("review" if left <= 2 else "info"), "determination", f"Determination {status} ({effective}).", R["determination"]))
    return {"id": req.get("id"), "received": recv.isoformat(), "determination_due": due.isoformat(), "extension_latest": ext_max.isoformat(),
            "effective_due": effective.isoformat(), "status": status, "findings": findings}


def read_requests(path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def to_ics(rows: list, agency: str = "") -> str:
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//brown-act-cpra-desk//demo//EN"]
    for r in rows:
        for key, label in (("determination_due", "CPRA determination due"), ("extension_latest", "CPRA latest extended date (only if extension noticed)")):
            d = r[key].replace("-", "")
            end = (date.fromisoformat(r[key]) + timedelta(days=1)).strftime("%Y%m%d")
            out += ["BEGIN:VEVENT", f"UID:{r['id']}-{key}@desk.demo", f"DTSTAMP:{datetime(2026, 1, 1):%Y%m%dT%H%M%SZ}",
                    f"DTSTART;VALUE=DATE:{d}", f"DTEND;VALUE=DATE:{end}", f"SUMMARY:{label}: {r['id']}",
                    "DESCRIPTION:Demo output with fictional data. Check the date against Gov. Code § 7922.535.", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


# ---------- legacy citations ----------

LEGACY = re.compile(r"(?:§+\s*|[Ss]ections?\s+|[Ss]ec\.\s*)(62\d\d(?:\.\d+)?)((?:\([a-z]{1,2}\))?)")


def map_legacy(text: str) -> list:
    table = load("legacy_map")
    m = {e["old"]: e for e in table["map"]}
    out = []
    for hit in LEGACY.finditer(text):
        base, sub = hit.group(1), hit.group(2)
        if not (6250 <= float(base) < 6277):
            continue
        e = m.get(base + sub) or (m.get(base) if not sub else None)
        out.append({"start": hit.start(), "end": hit.end(), "found": hit.group(0), "old": base + sub,
                    "new": "§ " + e["new"] if e else None, "topic": e["topic"] if e else None,
                    "status": ("new text verified; old-to-new pairing " + table["meta"]["pairing_status"]) if e else "no mapping in table; look it up",
                    "message": (f"Former § {base + sub} is now § {e['new']} ({e['topic']})." if e
                                else f"Former § {base + sub} was repealed and recodified in § 7920.000 et seq. This table has no entry for it.")})
    return out


# ---------- exemption proposals ----------

PATTERNS = [
    ("personal_privacy", "Social Security number pattern", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("employee_contact", "Phone number labeled home or personal", re.compile(r"(?i)(?:home|cell|personal|mobile)[^\n\d(]{0,20}(\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4})")),
    ("employee_contact", "Home address", re.compile(r"(?i)home address[^\n:]*:\s*([^\n]+)")),
    ("employee_contact", "Birthdate", re.compile(r"(?i)(?:date of birth|birthdate|DOB)[^\n\d]{0,10}(\d{1,2}/\d{1,2}/\d{2,4})")),
    ("personal_privacy", "Medical detail", re.compile(r"(?i)(?:diagnos\w+|medical leave for|treatment for)[^\n.,]*")),
    ("attorney_client", "Marked attorney-client privileged", re.compile(r"(?i)attorney[- ]client privileged[^\n]*")),
    ("draft", "Marked draft", re.compile(r"(?im)^\s*(?:DRAFT|PRELIMINARY DRAFT)\b[^\n]*")),
    ("security", "Credential or network detail", re.compile(r"(?i)(?:password|admin login|firewall rule|VPN (?:key|config))[^\n]*")),
]


def propose(doc_id: str, text: str, counsel: tuple = ()) -> list:
    cats = load("exemptions")["categories"]
    out = []
    for cat, why, rx in PATTERNS:
        for hit in rx.finditer(text):
            g = 1 if hit.groups() else 0
            out.append({"doc": doc_id, "start": hit.start(g), "end": hit.end(g), "text": hit.group(g).strip(), "category": cat,
                        "label": cats[cat]["label"], "cite": cats[cat]["cite"], "basis": why, "caution": cats[cat].get("note", ""),
                        "scope": "span", "status": "proposed", "reviewer": ""})
    frm = re.search(r"(?im)^From:\s*(.+)$", text)
    to = re.search(r"(?im)^To:\s*(.+)$", text)
    people = " ".join(x.group(1) for x in (frm, to) if x)
    if counsel and any(c.lower() in people.lower() for c in counsel) and re.search(r"(?i)legal advice|advise|privileged|counsel", text):
        out.append({"doc": doc_id, "start": 0, "end": len(text), "text": "(whole message)", "category": "attorney_client",
                    "label": cats["attorney_client"]["label"], "cite": cats["attorney_client"]["cite"],
                    "basis": "Sent to or from agency counsel and refers to legal advice", "caution": "Privilege depends on purpose and confidentiality, not the address line.",
                    "scope": "document", "status": "proposed", "reviewer": ""})
    out.sort(key=lambda p: (p["start"], p["end"]))
    for i, p in enumerate(out, 1):
        p["id"] = f"{doc_id}-{i:02d}"
    return out


def apply_decisions(proposals: list, decisions: dict) -> list:
    """decisions: {proposal_id: {"decision": "approve"|"reject", "reviewer": "Name, Title"}}. Unlisted stay proposed."""
    out = []
    for p in proposals:
        p = dict(p)
        d = decisions.get(p["id"])
        if d:
            if d["decision"] == "approve" and not d.get("reviewer"):
                raise ValueError(f"{p['id']}: an approval needs a named reviewer (Gov. Code § 7922.540(b)).")
            p["status"] = {"approve": "approved", "reject": "rejected"}[d["decision"]]
            p["reviewer"] = d.get("reviewer", "")
        out.append(p)
    return out


def propagate_decisions(proposals: list) -> list:
    """An approved span applies to the same text wherever it appears in the set. Mark those copies."""
    approved = {p["text"].lower(): p for p in proposals if p["status"] == "approved" and p["scope"] == "span"}
    out = []
    for p in proposals:
        p = dict(p)
        src = approved.get(p["text"].lower())
        if src and p["status"] == "proposed" and p["scope"] == "span":
            p["status"], p["reviewer"] = "approved", src["reviewer"]
            p["basis"] += f" (same text approved in {src['id']})"
        out.append(p)
    return out


def privilege_log(proposals: list, meta: dict) -> list:
    """Rows for approved entries only. meta: {doc_id: {date, from, to, subject}}."""
    rows = []
    for p in proposals:
        if p["status"] != "approved":
            continue
        m = meta.get(p["doc"], {})
        rows.append({"entry": p["id"], "document": p["doc"], "date": m.get("date", ""), "from": m.get("from", ""), "to": m.get("to", ""),
                     "subject": m.get("subject", ""), "treatment": "Withheld in full" if p["scope"] == "document" else "Redacted in part",
                     "exemption": p["cite"], "description": p["label"], "responsible_person": p["reviewer"]})
    return rows


def write_csv(rows: list, path) -> None:
    if not rows:
        open(path, "w").close()
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
