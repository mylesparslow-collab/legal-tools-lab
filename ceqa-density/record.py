"""CEQA record-of-proceedings compiler: Pub. Resources Code 21167.6 as amended by SB 131 (Stats. 2025, ch. 24).

What it does, with no language model anywhere in the path:
  1. Computes the record clock (service of the request, 60-day certification, extensions).
  2. Decides which subparagraph of 21167.6(e)(10) governs the project: (A) if it includes a distribution
     center or oil and gas infrastructure, (B) for everything else.
  3. Gives each candidate document a disposition and the reason for it.
  4. Removes exact duplicates by SHA-256.
  5. Orders the record per Cal. Rules of Court, rule 3.2205(a)(1), numbers the pages, and writes
     bookmarked, text-searchable PDF volumes, a hyperlinked index, and logs of what was left out.

Document labels (category, internal, presented to the decision-making body, privilege) are inputs. In the
research report those labels come from a bounded classifier with human review; here they are columns in a CSV.

Fictional sample data only. Not legal advice; built by a non-attorney as a portfolio demo.

Run: python3 record.py sample_data/record_case.json sample_data/documents.csv -o output/record
"""
from __future__ import annotations
import argparse, csv, hashlib, html, json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGAL = json.loads((ROOT / "legal_data.json").read_text())
CR = LEGAL["ceqa_record"]
v = lambda node: node["value"]

E_CATEGORIES = {
    1: "Project application materials", 2: "Staff reports and related documents on compliance and the action",
    3: "Staff reports, testimony and documents relevant to findings", 4: "Transcripts or minutes of proceedings",
    5: "Notices issued to comply with CEQA or other law", 6: "Written comments on environmental documents",
    7: "Written evidence or correspondence submitted to or sent by the agency", 8: "Proposed decisions or findings",
    9: "Documentation of the final decision, incl. final EIR and documents relied on",
    10: "Other written materials, incl. internal agency communications", 11: "Record before an inferior body on appeal"}
GROUPS = {g[0]: g for g in v(CR["order_of_documents"])}
YES = lambda s: str(s).strip().upper() in ("Y", "YES", "TRUE", "1")


# ---------------------------------------------------------------- clock
def _holidays():
    return {date.fromisoformat(d) for d in v(CR["court_holidays"])}


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _holidays()


def add_business_days(d: date, n: int) -> date:
    while n:
        d += timedelta(days=1)
        n -= is_business_day(d)
    return d


def next_court_day(d: date) -> date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def record_clock(case: dict) -> dict:
    filed = date.fromisoformat(case["filed"])
    served = date.fromisoformat(case["request_served"])
    serve_by = add_business_days(filed, v(CR["request_service_business_days"]))
    due = served + timedelta(days=v(CR["certify_days"]))
    rows = [("Petition and request to prepare the record filed", filed, CR["request_service_business_days"]["cite"]),
            ("Last day to personally serve the request on the agency (10 business days)", serve_by, CR["request_service_business_days"]["cite"]),
            ("Request served on the agency", served, ""),
            ("Case management conference to be held by (30 days from filing)", filed + timedelta(days=v(CR["cmc_days"])), CR["cmc_days"]["cite"]),
            ("Record certified and lodged by (60 days from service of the request)", due, CR["certify_days"]["cite"])]
    flags = []
    if served > serve_by:
        flags.append(f"Request was served {served}, after the 10-business-day date of {serve_by}.")
    cur = due
    for i, ext in enumerate(case.get("extensions", []), 1):
        days = int(ext["days"])
        if days > v(CR["max_single_extension_days"]) and not ext.get("public_interest_finding"):
            flags.append(f"Extension {i} is {days} days; a single extension over 60 days needs a court finding that it is in the public interest.")
        if ext["type"] not in ("stipulation", "court_order"):
            flags.append(f"Extension {i}: time can be extended only by stipulation of all served parties or court order.")
        cur += timedelta(days=days)
        rows.append((f"Extension {i} ({ext['type'].replace('_', ' ')}, {days} days): record now due", cur, CR["max_single_extension_days"]["cite"]))
    rolled = next_court_day(cur)
    if rolled != cur:
        flags.append(f"The due date {cur} is a weekend or listed court holiday. If Code Civ. Proc. 12a applies it moves to {rolled}. "
                     "That rule and the holiday list are unverified; attorney to confirm.")
    as_of = date.fromisoformat(case["as_of"]) if case.get("as_of") else None
    return {"rows": rows, "due": cur, "due_if_rolled": rolled, "flags": flags,
            "days_remaining": (cur - as_of).days if as_of else None, "as_of": as_of}


# ---------------------------------------------------------------- scope branch
def scope_branch(case: dict) -> tuple[str, str]:
    """'A' = 21167.6(e)(10)(A) (internal communications incl. staff notes all come in);
    'B' = (e)(10)(B) (emails and other electronic internal communications not presented to the
    final decision-making body are outside the required record, with an executive-review exception)."""
    p = case["project"]
    min_sf = v(CR["distribution_center_min_sqft"])
    dc = bool(p.get("includes_warehouse_distribution_center")) and p.get("distribution_center_sqft", 0) >= min_sf
    og = bool(p.get("includes_oil_gas_infrastructure"))
    if dc or og:
        why = " and ".join(x for x in (f"a warehouse distribution center of {p.get('distribution_center_sqft', 0):,} sq ft (threshold {min_sf:,})" if dc else "",
                                       "oil and gas infrastructure" if og else "") if x)
        return "A", f"Project includes {why}: Pub. Resources Code 21167.6(e)(10)(A), 21060.4, 21064.8."
    return "B", "Project includes no distribution center (50,000 sq ft or larger) and no oil and gas infrastructure: Pub. Resources Code 21167.6(e)(10)(B)."


# ---------------------------------------------------------------- dispositions
INCLUDE, DUP, LOGISTICAL, OPTIONAL, PRIV, REVIEW = ("INCLUDE", "EXCLUDE_DUPLICATE", "EXCLUDE_LOGISTICAL", "NOT_REQUIRED",
                                                    "WITHHOLD_PENDING_PRIVILEGE_REVIEW", "ATTORNEY_REVIEW")
EXEC = {"lead_agency_executive": "the lead agency executive", "local_agency_executive": "a local agency executive (Gov. Code 3511.1(d))",
        "supervisory_official": "an administrative official in a supervisory role reviewing the project"}


def disposition(doc: dict, branch: str) -> tuple[str, str]:
    """One document -> (disposition, reason). Rules are applied in this order; the first that fits wins."""
    cat = int(doc["e_category"])
    if cat not in E_CATEGORIES:
        return REVIEW, f"Category {cat} is not one of 21167.6(e)(1)-(11)."
    priv = doc.get("privilege_flag", "none").strip().lower() or "none"
    if priv != "none":
        return PRIV, (f"Flagged {priv.replace('_', ' ')}. Material subject to Evidence Code privileges or Public Records Act exemptions "
                      "is not included (21167.6(e)(10)). A person decides; this goes on the privilege log candidates list.")
    internal = YES(doc.get("internal_agency_comm"))
    if internal and YES(doc.get("logistical")):
        return LOGISTICAL, "Internal communication of a logistical nature (meeting invitation, scheduling): excluded by 21167.6(e)(10)."
    if YES(doc.get("draft_env_doc")) and not YES(doc.get("released_for_public_review")):
        return REVIEW, ("Draft environmental document not released for public review. (e)(10) lists drafts 'released for public review'; "
                        "whether this draft comes in another way is an attorney call.")
    if not internal or cat != 10:
        return INCLUDE, f"21167.6(e)({cat}): {E_CATEGORIES[cat]}."
    if branch == "A":
        return INCLUDE, "Internal agency communication on a distribution center / oil and gas project: included under 21167.6(e)(10)(A)(i), staff notes included."
    presented = YES(doc.get("presented_to_decisionmaking_body"))
    reviewer = doc.get("reviewed_by", "none").strip().lower() or "none"
    if YES(doc.get("electronic")) and not presented:
        if reviewer in EXEC:
            return INCLUDE, f"Electronic internal communication not presented to the decision-making body, but consulted or reviewed by {EXEC[reviewer]}: included under the exception in 21167.6(e)(10)(B)(iii)."
        return OPTIONAL, ("Electronic internal communication not presented to the final decision-making body and not reviewed by an executive or "
                          "supervising official: outside 'internal agency communications' under 21167.6(e)(10)(B)(iii). The agency may still choose to include it.")
    if YES(doc.get("staff_notes")) and not presented:
        return REVIEW, "Staff notes on a subparagraph (B) project. (B)(i) says 'memoranda' and drops the words 'staff notes' that appear in (A)(i); attorney to decide."
    return INCLUDE, "Internal agency communication (memorandum, or presented to the decision-making body): included under 21167.6(e)(10)(B)(i)."


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(case: dict, docs: list[dict], doc_dir: Path, include_optional: bool = False) -> dict:
    branch, branch_reason = scope_branch(case)
    docs = sorted(docs, key=lambda d: (d["date"], d["doc_id"]))
    seen = {}
    for d in docs:
        d["sha256"] = sha256_file(doc_dir / d["file"])
        if d["sha256"] in seen:
            d["disposition"], d["reason"] = DUP, f"Byte-identical to {seen[d['sha256']]} (same SHA-256); the earlier copy is kept."
            continue
        seen[d["sha256"]] = d["doc_id"]
        d["disposition"], d["reason"] = disposition(d, branch)
        if d["disposition"] == OPTIONAL and include_optional:
            d["disposition"], d["reason"] = INCLUDE, "Included by agency choice. " + d["reason"]
    return {"branch": branch, "branch_reason": branch_reason, "docs": docs, "clock": record_clock(case)}


# ---------------------------------------------------------------- compile
def _paginate(text: str, per_page: int = 46, width: int = 92) -> list[list[str]]:
    import textwrap
    lines = []
    for para in text.splitlines():
        lines += textwrap.wrap(para, width) or [""]
    return [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[""]]


def compile_record(result: dict, case: dict, doc_dir: Path, out: Path, pages_per_volume: int | None = None, prefix: str = "AR") -> dict:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    out.mkdir(parents=True, exist_ok=True)
    cap = pages_per_volume or v(CR["paper_bound_volume_max_pages"])
    inc = [d for d in result["docs"] if d["disposition"] == INCLUDE]
    inc.sort(key=lambda d: (d["rule_group"], d["date"], d["doc_id"]))
    for d in inc:
        d["_pages"] = _paginate((doc_dir / d["file"]).read_text())
    page, vol, used, c, vols = 1, 0, cap, None, []

    def new_volume():
        nonlocal vol, used, c
        if c:
            c.save()
        vol += 1; used = 0
        name = f"{prefix}_Vol_{vol:02d}.pdf"
        c = canvas.Canvas(str(out / name), pagesize=letter, invariant=1)
        c.setTitle(f"ADMINISTRATIVE RECORD Volume {vol} - {case['case_name']}")
        vols.append({"file": name, "first": page, "last": page - 1})

    for d in inc:
        n = len(d["_pages"])
        if used + n > cap and used > 0 or c is None:   # keep a document in one volume where it fits
            new_volume()
        d["volume"], d["vol_file"], d["first_page"], d["last_page"], d["vol_page"] = vol, vols[-1]["file"], page, page + n - 1, used + 1
        for i, lines in enumerate(d["_pages"]):
            if used >= cap:
                new_volume()
            if i == 0:
                key = f"doc_{d['doc_id']}"
                c.bookmarkPage(key); c.addOutlineEntry(f"{prefix}{page:06d} {d['title']}"[:110], key, level=0)
            c.setFont("Helvetica-Bold", 9); c.drawString(54, 756, f"{d['doc_id']}  |  {d['date']}  |  {d['title']}"[:118])
            c.setFont("Courier", 9)
            y = 736
            for ln in lines:
                c.drawString(54, y, ln); y -= 14.5
            c.setFont("Helvetica-Bold", 10); c.drawRightString(558, 36, f"{prefix}{page:06d}")
            c.setFont("Helvetica", 7); c.drawString(54, 36, "FICTIONAL SAMPLE DATA - portfolio demo")
            c.showPage(); page += 1; used += 1; vols[-1]["last"] = page - 1
    if c:
        c.save()

    # index (rule 3.2205(b)); hyperlinks are allowed, not required (rule 3.2207(a))
    clock = result["clock"]
    counts = {}
    for d in result["docs"]:
        counts[d["disposition"]] = counts.get(d["disposition"], 0) + 1
    h = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Index to Administrative Record</title><style>",
         "body{font:14px/1.45 Georgia,serif;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#1b1b1b}table{border-collapse:collapse;width:100%;margin:1rem 0}",
         "th,td{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}th{background:#eee}h2{margin-top:2rem}.note{color:#555;font-size:13px}",
         "</style></head><body>",
         f"<h1>Index to Administrative Record</h1><p><b>{html.escape(case['case_name'])}</b><br>{html.escape(case['court'])}, Case No. {html.escape(case['case_number'])}</p>",
         "<p class='note'>Fictional sample data generated for a portfolio demo. Not a real case, agency or project. Not legal advice.</p>",
         f"<p><b>Scope:</b> {html.escape(result['branch_reason'])}</p>",
         f"<p><b>Record due:</b> {clock['due']} (60 days from service of the request on {case['request_served']}"
         + (", plus extensions" if case.get("extensions") else "") + ").</p>",
         "<p><b>Volumes:</b> " + "; ".join(f"<a href='{x['file']}'>{x['file']}</a> ({prefix}{x['first']:06d}-{prefix}{x['last']:06d})" for x in vols) + "</p>"]
    cur = None
    for d in inc:
        if d["rule_group"] != cur:
            if cur:
                h.append("</table>")
            cur = d["rule_group"]
            h.append(f"<h2>{html.escape(GROUPS[cur])}</h2><table><tr><th>Pages</th><th>Date</th><th>Document</th><th>Author</th><th>21167.6(e)</th><th>Vol.</th></tr>")
        h.append(f"<tr><td><a href='{d['vol_file']}#page={d['vol_page']}'>{prefix}{d['first_page']:06d}-{prefix}{d['last_page']:06d}</a></td><td>{d['date']}</td>"
                 f"<td>{html.escape(d['title'])}</td><td>{html.escape(d['author'])}</td><td>({d['e_category']})</td><td>{d['volume']}</td></tr>")
    h.append("</table><h2>Documents not in the record</h2><table><tr><th>ID</th><th>Date</th><th>Document</th><th>Disposition</th><th>Reason</th></tr>")
    for d in result["docs"]:
        if d["disposition"] != INCLUDE:
            h.append(f"<tr><td>{d['doc_id']}</td><td>{d['date']}</td><td>{html.escape(d['title'])}</td><td>{d['disposition']}</td><td>{html.escape(d['reason'])}</td></tr>")
    h.append("</table></body></html>")
    (out / "index.html").write_text("\n".join(h))

    fields = ["doc_id", "date", "title", "author", "doc_type", "e_category", "rule_group", "disposition", "reason", "volume", "first_page", "last_page", "sha256"]
    with open(out / "disposition_log.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader()
        for d in result["docs"]:
            row = dict(d)
            for k in ("first_page", "last_page"):
                if d.get(k):
                    row[k] = f"{prefix}{d[k]:06d}"
            w.writerow(row)
    with open(out / "privilege_log_candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["doc_id", "date", "title", "author", "recipient", "privilege_flag", "reason"], extrasaction="ignore"); w.writeheader()
        w.writerows(d for d in result["docs"] if d["disposition"] == PRIV)

    # calendar
    ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ceqa-density demo//EN"]
    for i, (label, dt, cite) in enumerate(clock["rows"]):
        ics += ["BEGIN:VEVENT", f"UID:ceqa-record-{i}@demo.invalid", f"DTSTAMP:{case['filed'].replace('-', '')}T000000Z",
                f"DTSTART;VALUE=DATE:{dt:%Y%m%d}", f"SUMMARY:{label} (fictional demo)", f"DESCRIPTION:{cite}", "END:VEVENT"]
    (out / "record_clock.ics").write_text("\r\n".join(ics + ["END:VCALENDAR"]) + "\r\n")

    summary = {"case": case["case_name"], "branch": result["branch"], "branch_reason": result["branch_reason"],
               "clock": [{"event": a, "date": str(b), "cite": c_} for a, b, c_ in clock["rows"]], "record_due": str(clock["due"]),
               "days_remaining": clock["days_remaining"], "flags": clock["flags"], "counts": counts,
               "pages": page - 1, "volumes": vols}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def load_docs(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("case"); ap.add_argument("documents")
    ap.add_argument("-o", "--out", default="output/record")
    ap.add_argument("--include-optional", action="store_true", help="include documents the agency may but need not include under (e)(10)(B)")
    ap.add_argument("--pages-per-volume", type=int)
    a = ap.parse_args(argv)
    case = json.loads(Path(a.case).read_text())
    doc_dir = Path(a.documents).parent
    result = process(case, load_docs(Path(a.documents)), doc_dir, a.include_optional)
    s = compile_record(result, case, doc_dir, Path(a.out), a.pages_per_volume)
    print(json.dumps({k: s[k] for k in ("branch", "record_due", "days_remaining", "flags", "counts", "pages")}, indent=1))
    print("volumes:", ", ".join(x["file"] for x in s["volumes"])); print("wrote", a.out)
    return s


if __name__ == "__main__":
    main()
