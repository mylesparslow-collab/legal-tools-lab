"""Build everything for one RFP: draft sections, compliance matrix, disqualifiers, go/no-go."""
import math
import re

from drafting import llm_hook

from . import facts as F
from .experience import check_min_quals, match_experience, select_references, select_team
from .library import fill_placeholders, provenance, rank_answers
from .rfp import DEADLINE_LABELS, PERSON_QTYPES, page_limit, parse_rfp, submission_deadline
from .util import business_days_between, fmt_date, norm_ws, parse_iso, shift_business_days, tokens

ANSWERED, PARTIAL, NO_CONTENT, PERSON, FAILED, DONE = "answered", "partial", "no_content", "person", "failed", "done"
STATUS_LABELS = {ANSWERED: "Answered from library", PARTIAL: "Partially answered", NO_CONTENT: "No content found",
                 PERSON: "Needs a person", FAILED: "Check failed", DONE: "Marked done"}
LIBRARY_QTYPES = ["firm_overview", "approach", "team", "experience", "references", "diversity_local", "transition"]
HOLIDAY_NOTE = ("Due dates count back from the submission deadline in business days. Weekends are skipped. "
                "Holidays are not skipped unless a holiday file is supplied.")


def detect_terms(rfp_text, meta):
    """Governing body and chief executive as this RFP names them, or ''."""
    def most_used(terms):
        counts = [(len(re.findall(r"(?<![A-Za-z])" + re.escape(t) + r"(?![a-z])", rfp_text)), -i, t)
                  for i, t in enumerate(terms)]
        n, _, term = max(counts)
        return term if n else ""
    body = most_used([t for t in F.BODY_TERMS if t not in ("Planning Commission", "Mayor")])
    if not body and re.search(r"(?:the|'s|’s)\s+Board\b", rfp_text):
        body = "Board"
    chief = most_used([t for t in F.EXEC_TERMS if t != "City Attorney"])
    return body, chief


def _owner(workplan, key):
    return workplan.get("owners", {}).get(key, "Proposal lead")


class _Schedule:
    def __init__(self, deadline, as_of, holidays, workplan):
        self.deadline = parse_iso(deadline["date"]) if deadline else None
        self.as_of, self.holidays = as_of, holidays
        self.lead = workplan.get("lead_days", {})

    def due(self, key):
        """(iso date or '', late flag)."""
        if not self.deadline:
            return "", False
        n = self.lead.get(key, self.lead.get("content", 6))
        d = shift_business_days(self.deadline, -n, self.holidays)
        return d.isoformat(), d < self.as_of


def _words(text):
    return len(re.findall(r"\S+", text or ""))


def _passage_part(cand, ctx, req):
    a = cand["answer"]
    filled = fill_placeholders(a["answer_text"], ctx)
    text, rewritten = filled, False
    if llm_hook.ENABLED:
        text = llm_hook.rewrite(filled, req["text"], {"agency": ctx["agency"], "agency_type": ctx["agency_type"],
                                                      "question_type": req["qtype"], "answer_id": a["id"]})
        rewritten = text != filled
    flags = F.check_passage(text, ctx)   # always after any rewrite
    if rewritten:
        flags.append(F.flag(F.WARNING, "rewritten",
                            "this text was rewritten by the optional model hook. It is not approved text. "
                            "Compare it with source answer %s." % a["id"]))
    return {"type": "passage", "text": text, "provenance": provenance(a), "flags": flags,
            "rewritten": rewritten, "score": cand["score"], "reasons": cand["reasons"]}


def _choose(cands, ctx, req, limit=8):
    """Pick the passage to insert. Stale answers are never inserted.

    The best-ranked fresh answer is used unless it has blocking flags and a
    clean fresh answer ranks at 60% of its score or better.
    """
    fresh = [c for c in cands if not c["stale"]][:limit]
    stale = [c for c in cands if c["stale"]]
    parts = [(c, _passage_part(c, ctx, req)) for c in fresh]
    chosen, skipped = None, []
    if parts:
        top_score = parts[0][0]["score"]
        for c, p in parts:
            if not F.has_blocking(p["flags"]) and c["score"] >= 0.6 * top_score and c["bm25"] > 0:
                chosen = p
                break
            skipped.append((c, p))
        if chosen is None:
            first = next(((c, p) for c, p in parts if c["bm25"] > 0), None)
            chosen, skipped = (first[1] if first else None), []
    alternatives = []
    for c, p in parts:
        if p is chosen:
            continue
        alternatives.append({"answer_id": c["answer"]["id"], "proposal_id": c["answer"]["proposal_id"],
                             "score": c["score"], "stale": False, "reasons": c["reasons"],
                             "blocking": [f["message"] for f in p["flags"] if f["level"] == F.BLOCKING]})
    for c in stale[:3]:
        alternatives.append({"answer_id": c["answer"]["id"], "proposal_id": c["answer"]["proposal_id"],
                             "score": c["score"], "stale": True, "reasons": c["reasons"], "blocking": []})
    skipped_ids = ["%s (%s)" % (c["answer"]["id"], next(
        (f["message"] for f in p["flags"] if f["level"] == F.BLOCKING), "ranked too low"))
        for c, p in skipped] if chosen is not None else []
    return chosen, alternatives[:5], skipped_ids, stale


def _team_part(team):
    lines = []
    for m in team["members"]:
        b = m["bio"]
        admitted = "Admitted %d." % b["admit_year"] if b.get("admit_year") else "Admission year not on file."
        lines.append({"name": b["name"], "role": m["role"], "bio_id": b["id"], "reasons": m["reasons"],
                      "text": "%s, %s. %s. %s %s office. %s" % (b["name"], b["title"], m["role"], admitted,
                                                                b.get("office", ""), b.get("bio_text", ""))})
    return {"type": "team", "items": lines, "text": "\n".join(x["text"] for x in lines)}


def _experience_part(exp):
    items = [{"record_id": s["record"]["id"], "mode": s["display"]["mode"], "text": s["display"]["text"],
              "reasons": s["reasons"], "score": s["score"]} for s in exp["selected"]]
    return {"type": "experience", "items": items, "text": "\n".join(x["text"] for x in items),
            "omitted": [{"record_id": s["record"]["id"], "score": s["score"], "reasons": s["reasons"]}
                        for s in exp["omitted"]]}


def _references_part(refs):
    items = []
    for s in refs["selected"]:
        r = s["record"]
        items.append({"record_id": r["id"], "stale": s["stale"], "last_confirmed": r.get("last_confirmed"),
                      "text": "%s, %s, %s. Telephone %s. Email %s." % (r["contact_name"], r["contact_title"],
                                                                     r["client_name"], r["phone"], r["email"])})
    return {"type": "references", "items": items, "text": "\n".join(x["text"] for x in items),
            "needed": refs["needed"], "withheld_count": refs["withheld_count"]}


def build(rfp_text, data, as_of, holidays=frozenset(), status=None):
    """Return the full result for one RFP as a plain dict."""
    as_of = parse_iso(as_of)
    status = status or {}
    wp = data.workplan
    rfp = parse_rfp(rfp_text)
    meta = rfp["meta"]
    flat = norm_ws(rfp_text)          # line wraps must not hide terms such as "Board of Directors"
    body, chief = detect_terms(flat, meta)
    ctx = F.make_context(meta, data, flat)
    ctx.update({"governing_body": body, "chief_exec": chief})
    deadline = submission_deadline(rfp)
    sched = _Schedule(deadline, as_of, holidays, wp)

    team = select_team(meta, data.bios, as_of)
    exp = match_experience(meta, data.experience, as_of)
    mq = check_min_quals(rfp["min_quals"], team, data.facts, as_of)
    query_extra = " " + " ".join(meta.get("subjects", []))
    n_parties = len(rfp["parties"])

    sections = []
    for req in rfp["requirements"]:
        qtype = req["qtype"]
        sec = {"id": req["id"], "label": req["label"], "title": req["title"], "rfp_text": req["text"],
               "qtype": qtype, "mandatory": req["mandatory"], "parts": [], "notes": [], "alternatives": [],
               "owner": _owner(wp, qtype), "confidence": req["confidence"], "source_line": req["source"]["line"]}
        due_key = qtype if qtype in sched.lead else "content"
        sec["due"], sec["late"] = sched.due(due_key)
        if qtype == "conflicts":
            sec["status"] = PERSON
            sec["parts"].append({"type": "person", "text":
                                 "The conflicts section is never written by the tool. %d parties named in the RFP "
                                 "are listed in conflicts_parties.csv for the conflicts team. Past conflicts "
                                 "statements in the library are not inserted." % n_parties})
        elif qtype == "cover_letter":
            sec["status"] = PERSON
            sec["parts"].append({"type": "person", "text":
                                 "A signed letter is required. The tool does not draft or sign it."})
        elif qtype == "rates":
            sec["status"] = PERSON
            current = [r for r in data.rate_schedules
                       if r["effective"] <= as_of.isoformat() <= r["expires"] and r.get("approved_by")]
            ref = ("Approved rate schedule on file for reference only: %s (%s), approved by %s."
                   % (current[0]["id"], current[0]["name"], current[0]["approved_by"])) if current else \
                "No approved rate schedule is in force on %s." % as_of.isoformat()
            sec["parts"].append({"type": "person", "text": "Pricing is set by a person. Nothing is inserted. " + ref})
        elif qtype == "disclosure":
            sec["status"] = PERSON
            sec["parts"].append({"type": "person", "text":
                                 "Disclosures and exceptions are written by a person. Nothing is inserted."})
        elif qtype not in LIBRARY_QTYPES:
            sec["status"] = NO_CONTENT
            sec["parts"].append({"type": "gap", "text":
                                 "Question type not recognised. A person must read the question and decide how to answer."})
        else:
            cands = rank_answers(data.answers, qtype, req["text"] + query_extra, meta, as_of)
            chosen, alts, skipped, stale = _choose(cands, ctx, req)
            sec["alternatives"] = alts
            downgrade = []
            if chosen is None:
                sec["status"] = NO_CONTENT
                msg = "No current approved content found for this question."
                if stale:
                    msg += " Stale answers exist and were not inserted: %s." % ", ".join(
                        c["answer"]["id"] for c in stale[:3])
                sec["parts"].append({"type": "gap", "text": msg})
            else:
                sec["parts"].append(chosen)
                p = chosen["provenance"]
                src = next(a for a in data.answers if a["id"] == p["answer_id"])
                if F.has_blocking(chosen["flags"]):
                    downgrade.append("blocking fact flags on the inserted passage")
                if not p["approved"]:
                    downgrade.append("source answer is not approved by the practice lead")
                if src["practice"] != meta["practice"]:
                    downgrade.append("source answer is from a different practice (%s)" % src["practice"].replace("_", " "))
                if chosen["rewritten"]:
                    downgrade.append("passage was rewritten by the model hook")
                if skipped:
                    sec["notes"].append("Higher-ranked answers were passed over because of blocking flags: %s"
                                        % " ".join(skipped))
            if qtype == "firm_overview" and (chosen is None or F.has_blocking(chosen["flags"])):
                # no clean passage: give the current facts so the writer does not reach for old numbers
                sec["parts"].append({"type": "facts", "as_of": data.facts["as_of"],
                                     "text": F.facts_block(data.facts)})
            if qtype == "team":
                sec["parts"].append(_team_part(team))
                if not team["lead"]:
                    downgrade.append("no lead attorney could be proposed from the bios")
                bad = [q for q in mq if q["status"] == "not_met"]
                if bad:
                    downgrade.append("%d minimum qualification(s) not met" % len(bad))
            if qtype == "experience":
                part = _experience_part(exp)
                sec["parts"].append(part)
                if len(part["items"]) < 3:
                    downgrade.append("fewer than three printable experience records")
                if part["omitted"]:
                    sec["notes"].append("%d relevant record(s) left out for lack of consent to name the client and of an approved "
                                        "anonymized description: %s" % (len(part["omitted"]), ", ".join(
                                            o["record_id"] for o in part["omitted"])))
            if qtype == "references":
                needed = req.get("references_required") or 3
                refs = select_references(meta, data.references, data.experience, as_of, needed,
                                         wp.get("reference_reconfirm_days", 365))
                part = _references_part(refs)
                sec["parts"].append(part)
                if len(part["items"]) < needed:
                    downgrade.append("%d reference(s) with both consents on file; the RFP asks for %d"
                                     % (len(part["items"]), needed))
                old = [x["record_id"] for x in part["items"] if x["stale"]]
                if old:
                    downgrade.append("reference(s) not confirmed in the last %d days: %s"
                                     % (wp.get("reference_reconfirm_days", 365), ", ".join(old)))
                if part["withheld_count"]:
                    sec["notes"].append("%d matching reference record(s) were not listed: %d without the contact's "
                                        "consent to be listed, %d without the client's consent to be named"
                                        % (part["withheld_count"], refs["withheld_contact"], refs["withheld_client"]))
            if chosen is not None:
                sec["status"] = PARTIAL if downgrade else ANSWERED
            sec["notes"] = downgrade + sec["notes"]
        sections.append(sec)

    # ---------------------------------------------------------------- page estimate
    wpp = wp.get("words_per_page", 450)
    limit = page_limit(rfp)
    exclusions = " ".join(str(m["value"]) for m in rfp["mechanics"] if m["kind"] == "page_exclusions").lower()
    excluded_q = set()
    if re.search(r"transmittal|cover letter", exclusions):
        excluded_q.add("cover_letter")
    if "cost proposal" in exclusions or "fee proposal" in exclusions:
        excluded_q.add("rates")
    counted = [s for s in sections if s["qtype"] not in excluded_q]
    words = sum(_words(p.get("text")) for s in counted for p in s["parts"]
                if p["type"] in ("passage", "facts", "team", "experience", "references"))
    empty = [s["label"] or s["title"] for s in counted if s["status"] in (NO_CONTENT, PERSON)]
    est_pages = max(1, math.ceil(words / wpp)) if words else 0
    page = {"limit": limit["value"] if limit else None, "words": words, "words_per_page": wpp,
            "estimated_pages": est_pages, "empty_sections": empty,
            "exclusions": exclusions, "changed_by": limit.get("changed_by") if limit else None,
            "original_limit": limit.get("original_value") if limit else None}

    # ---------------------------------------------------------------- consent check on the whole draft
    all_text = "\n".join(p.get("text") or "" for s in sections for p in s["parts"])
    consent_flags = F.check_consent(all_text, data, meta["agency"])

    # ---------------------------------------------------------------- matrix
    rows = []

    def add_row(rid, category, section, requirement, mandatory, where, st, detail, owner_key, due_key, line=None):
        due, late = sched.due(due_key)
        rows.append({"id": rid, "category": category, "section": section, "requirement": requirement,
                     "mandatory": bool(mandatory), "where": where, "status": st, "detail": detail,
                     "owner": _owner(wp, owner_key), "due": due, "late": late, "source_line": line})

    if deadline:
        t = (" at %s" % deadline["time"]) if deadline["time"] else ""
        det = "Submit by %s%s." % (fmt_date(deadline["date"]), t)
        if deadline.get("changed_by"):
            det += " Changed by %s; was %s." % (deadline["changed_by"], fmt_date(deadline["original_date"]))
        rows.append({"id": "DEADLINE", "category": "deadline", "section": "", "requirement": deadline["source"]["text"],
                     "mandatory": True, "where": "Delivery", "status": PERSON, "detail": det,
                     "owner": _owner(wp, "submission"), "due": deadline["date"],
                     "late": parse_iso(deadline["date"]) < as_of, "source_line": deadline["source"]["line"]})
    else:
        rows.append({"id": "DEADLINE", "category": "deadline", "section": "", "requirement": "Submission deadline",
                     "mandatory": True, "where": "Delivery", "status": FAILED,
                     "detail": "No submission deadline was found in the RFP. Read the RFP and set it by hand.",
                     "owner": _owner(wp, "submission"), "due": "", "late": False, "source_line": None})

    for s in sections:
        detail = "; ".join(s["notes"])
        prov = next((p["provenance"] for p in s["parts"] if p["type"] == "passage"), None)
        if prov:
            detail = ("Passage from %s (%s, %s)%s" % (prov["answer_id"], prov["proposal_id"], prov["outcome"],
                                                     ". " + detail if detail else "."))
        elif not detail:
            detail = s["parts"][0]["text"] if s["parts"] else ""
        rows.append({"id": s["id"], "category": "content", "section": s["label"], "requirement": s["rfp_text"],
                     "mandatory": s["mandatory"], "where": "Draft section %s %s" % (s["label"], s["title"]),
                     "status": s["status"], "detail": detail, "owner": s["owner"], "due": s["due"],
                     "late": s["late"], "source_line": s["source_line"]})

    team_sec = next((s for s in sections if s["qtype"] == "team"), None)
    for q in mq:
        st = {"met": ANSWERED, "not_met": FAILED, "not_checkable": PERSON}[q["status"]]
        add_row(q["id"], "min_qual", q["label"], q["text"], True,
                ("Draft section %s %s" % (team_sec["label"], team_sec["title"])) if team_sec else "Team section",
                st, q["detail"], "min_qual", "min_qual")

    for f in rfp["forms"]:
        std = match_standard_form(f["name"], data.forms)
        needs = [x for x, on in (("signature", f["signature"] or (std and std["requires_signature"])),
                                 ("notary", f["notarized"])) if on]
        if f["confidence"] == "check" and not f["mandatory"]:
            st, det = PERSON, "Referred to in the RFP text. Check whether it must be submitted."
        elif std:
            st, det = PERSON, "Firm's standard answers on file: %s (%s, last reviewed %s). Complete the agency's form." % (
                std["id"], std["name"], std.get("last_reviewed") or "unknown")
        else:
            st, det = NO_CONTENT, "No standard answers on file for this form. Complete the agency's form from the RFP package."
        if needs:
            det += " Needs: %s." % ", ".join(needs)
        if f.get("added_by"):
            det += " Added by %s." % f["added_by"]
        add_row(f["id"], "form", f["ref"], f["name"], f["mandatory"], "Forms packet", st, det, "form", "form",
                f["source"]["line"])

    for x in rfp["insurance"]:
        amounts = ", ".join(x["amounts"]) or "no amount stated"
        add_row(x["id"], "insurance", "", x["text"], True, "Insurance statement or certificate", PERSON,
                "Risk manager confirms current coverage against the RFP text (%s)." % amounts,
                "insurance", "insurance", x["source"]["line"])

    for m in rfp["mechanics"]:
        kind = m["kind"]
        if kind == "page_exclusions":
            continue
        if kind == "page_limit":
            lim = m["value"]
            note = "Estimate: %d words, about %d page(s) at %d words a page, against a limit of %d." % (
                words, est_pages, wpp, lim)
            if m.get("changed_by"):
                note += " Limit changed by %s; was %s." % (m["changed_by"], m.get("original_value"))
            if exclusions:
                note += " Excluded by the RFP: %s." % exclusions
            if empty:
                note += " %d section(s) are still empty, so the final length will be higher." % len(empty)
            note += " This is an estimate from word count. Check the final layout."
            if est_pages > lim:
                st = FAILED
            elif empty or est_pages > 0.8 * lim:
                st = PARTIAL
            else:
                st = ANSWERED
            add_row(m["id"], "submission", "", m["source"]["text"], True, "Whole draft", st, note,
                    "submission", "submission", m["source"]["line"])
        elif kind in ("font", "margins"):
            val = "%s point" % m["value"] if kind == "font" else "%s inch" % m["value"]
            add_row(m["id"], "submission", "", m["source"]["text"], True, "draft.html print style", PARTIAL,
                    "draft.html prints at %s. If the final document is laid out elsewhere, check it there." % val,
                    "submission", "submission", m["source"]["line"])
        else:
            add_row(m["id"], "submission", "", m["source"]["text"], True, "Delivery", PERSON,
                    "%s: %s" % (kind.replace("_", " "), m["value"]), "submission", "submission", m["source"]["line"])

    for a in rfp["addenda"]:
        for note in a["notes"]:
            add_row(note["id"], "addendum", "Addendum %s" % a["number"], note["text"], True, "Read and act", PERSON,
                    "Addendum item not applied automatically. Read it and act on it.", "addendum", "addendum",
                    note["source"]["line"])

    if consent_flags:
        add_row("CONSENT", "content", "", "Client names may be printed only with client consent.", True,
                "Whole draft", FAILED, " ".join(f["message"] for f in consent_flags), "experience", "content")

    for r in rows:
        r["auto_status"] = r["status"]
        mark = status.get(r["id"])
        if mark and mark.get("done"):
            r["status"] = DONE
            r["detail"] = "Marked done by %s%s. Tool status was: %s. %s" % (
                mark.get("by", "a person"), (" (" + mark["note"] + ")") if mark.get("note") else "",
                STATUS_LABELS[r["auto_status"]].lower(), r["detail"])
        r["status_label"] = STATUS_LABELS[r["status"]]
    unknown_marks = sorted(set(status) - {r["id"] for r in rows})

    disqualifiers = [r for r in rows if r["mandatory"] and r["status"] not in (ANSWERED, DONE)]
    disqualifiers.sort(key=lambda r: (r["due"] or "9999", r["id"]))

    # ---------------------------------------------------------------- go / no-go
    content = [s for s in sections]
    count = {k: sum(1 for s in content if s["status"] == k) for k in (ANSWERED, PARTIAL, NO_CONTENT, PERSON)}
    answerable = [s for s in content if s["qtype"] not in PERSON_QTYPES]
    full = sum(1 for s in answerable if s["status"] == ANSWERED)
    blocking = [{"section": s["label"], "answer_id": p["provenance"]["answer_id"], "message": f["message"]}
                for s in sections for p in s["parts"] if p["type"] == "passage"
                for f in p["flags"] if f["level"] == F.BLOCKING]
    facts_age = (as_of - parse_iso(data.facts["as_of"])).days
    gng = {
        "agency": meta["agency"], "title": meta["title"], "rfp_number": meta["rfp_number"],
        "as_of": as_of.isoformat(),
        "deadline": None if not deadline else {
            "date": deadline["date"], "time": deadline["time"], "changed_by": deadline.get("changed_by"),
            "original_date": deadline.get("original_date"), "original_time": deadline.get("original_time"),
            "business_days_left": business_days_between(as_of, parse_iso(deadline["date"]), holidays),
            "passed": parse_iso(deadline["date"]) < as_of},
        "min_quals": {"met": sum(1 for q in mq if q["status"] == "met"),
                      "not_met": sum(1 for q in mq if q["status"] == "not_met"),
                      "not_checkable": sum(1 for q in mq if q["status"] == "not_checkable"), "items": mq},
        "coverage": {"requirements": len(content), "answered": count[ANSWERED], "partial": count[PARTIAL],
                     "no_content": count[NO_CONTENT], "person": count[PERSON],
                     "library_answerable": len(answerable), "answered_of_answerable": full,
                     "pct": round(100 * full / len(answerable)) if answerable else 0},
        "open_disqualifiers": len(disqualifiers),
        "blocking_flags": blocking,
        "consent_flags": [f["message"] for f in consent_flags],
        "page": page,
        "facts_as_of": data.facts["as_of"], "facts_age_days": facts_age,
        "facts_old": facts_age > wp.get("firm_facts_max_age_days", 180),
        "parser_checks": len(rfp["checks"]),
        "late_items": sum(1 for r in rows if r["late"] and r["status"] not in (ANSWERED, DONE)),
        "holidays_supplied": bool(holidays), "holiday_note": HOLIDAY_NOTE,
        "unknown_status_marks": unknown_marks,
        "data_errors": len(data.errors),
    }
    return {"rfp": rfp, "terms": {"governing_body": body, "chief_exec": chief}, "sections": sections,
            "matrix": rows, "disqualifiers": disqualifiers, "go_no_go": gng, "team": team,
            "experience": exp, "min_quals": mq, "parties": rfp["parties"], "page": page,
            "deadline_labels": DEADLINE_LABELS, "status_labels": STATUS_LABELS}


def match_standard_form(name, forms):
    """Match an RFP form name to a firm standard form by word overlap. Returns the form or None."""
    want = set(tokens(re.sub(r"\bsigned\b", "", name, flags=re.I)))
    if not want:
        return None
    best, best_score = None, 0.0
    for f in forms:
        for cand in [f["name"]] + list(f.get("aliases", [])):
            have = set(tokens(cand))
            if not have:
                continue
            j = len(want & have) / len(want | have)
            if have <= want:
                j = max(j, 0.75)
            if j > best_score:
                best, best_score = f, j
    return best if best_score >= 0.6 else None
