"""Experience matcher, team selection, minimum qualification checks, references.

Client consent rule: a client is named only if the record has
client_consent true. Without consent the approved anonymized description is
printed instead. With neither, the record is left out and listed for the
proposal lead so consent can be sought.
"""
from .util import parse_iso

ROLE_FOR_PRACTICE = {"general_counsel": ["general counsel", "city attorney"], "labor": ["chief negotiator"],
                     "capital_projects": ["special counsel"]}
LEAD_TITLES = ("Partner", "Of Counsel")


def _years_text(rec):
    if rec.get("end_year"):
        return "%s to %s" % (rec["start_year"], rec["end_year"])
    return "%s to present" % rec["start_year"]


def display_experience(rec):
    """How a record may be printed. Returns {mode, name, text}.

    mode: 'named' | 'anonymized' | 'omitted'. The free-text summary is printed
    only when the client may be named, because summaries can identify a client.
    """
    role = rec.get("role") or "counsel"
    if rec.get("client_consent") is True:
        text = "%s (%s, %s)." % (rec["client_name"], role, _years_text(rec))
        if rec.get("summary"):
            text += " " + rec["summary"]
        return {"mode": "named", "name": rec["client_name"], "text": text}
    anon = (rec.get("anonymized_description") or "").strip()
    if anon:
        label = anon[0].upper() + anon[1:]
        subjects = ", ".join(rec.get("subjects", []))
        text = "%s (%s, %s)." % (label, role, _years_text(rec))
        if subjects:
            text += " Subjects: %s." % subjects
        return {"mode": "anonymized", "name": label, "text": text}
    return {"mode": "omitted", "name": None, "text": None}


def score_experience(rec, rfp_meta, as_of):
    score, reasons = 0, []
    if rec["agency_type"] == rfp_meta["agency_type"]:
        score += 3
        reasons.append("same agency type (%s)" % rec["agency_type"].replace("_", " "))
    if rec["practice"] == rfp_meta["practice"]:
        score += 3
        reasons.append("same practice (%s)" % rec["practice"].replace("_", " "))
    shared = sorted(set(rec.get("subjects", [])) & set(rfp_meta.get("subjects", [])))
    if shared:
        score += min(3, len(shared))
        reasons.append("shared subjects: %s" % ", ".join(shared))
    end = rec.get("end_year")
    if end is None:
        score += 2
        reasons.append("ongoing")
    elif end >= as_of.year - 3:
        score += 2
        reasons.append("ended %d (within three years)" % end)
    elif end >= as_of.year - 6:
        score += 1
        reasons.append("ended %d (within six years)" % end)
    else:
        reasons.append("ended %d (older)" % end)
    if rec.get("role") in ROLE_FOR_PRACTICE.get(rfp_meta["practice"], []):
        score += 2
        reasons.append("same role (%s)" % rec["role"])
    return score, reasons


def match_experience(rfp_meta, experience, as_of, top_n=5):
    """Return {'selected': [...], 'omitted': [...]}.

    selected: printable records, best first, each with score, reasons, display.
    omitted: records that would have ranked in the top but cannot be printed.
    """
    as_of = parse_iso(as_of)
    scored = []
    for rec in experience:
        score, reasons = score_experience(rec, rfp_meta, as_of)
        scored.append({"record": rec, "score": score, "reasons": reasons, "display": display_experience(rec)})
    scored.sort(key=lambda x: (-x["score"], x["record"]["id"]))
    selected = [s for s in scored if s["display"]["mode"] != "omitted"][:top_n]
    cutoff = selected[-1]["score"] if selected else 0
    omitted = [s for s in scored if s["display"]["mode"] == "omitted" and s["score"] >= cutoff and s["score"] > 0]
    for s in omitted:
        s["reasons"] = s["reasons"] + ["not printed: no client consent and no approved anonymized description"]
    return {"selected": selected, "omitted": omitted[:top_n]}


def score_bio(bio, rfp_meta, as_of):
    score, reasons = 0, []
    if rfp_meta["practice"] in bio.get("practices", []):
        score += 4
        reasons.append("practice: %s" % rfp_meta["practice"].replace("_", " "))
    if rfp_meta["agency_type"] in bio.get("agency_types", []):
        score += 3
        reasons.append("works for this agency type")
    shared = sorted(set(bio.get("subjects", [])) & set(rfp_meta.get("subjects", [])))
    if shared:
        score += min(3, len(shared))
        reasons.append("subjects: %s" % ", ".join(shared))
    roles = set(bio.get("roles", [])) & set(ROLE_FOR_PRACTICE.get(rfp_meta["practice"], []))
    if roles:
        score += 2
        reasons.append("has served as %s" % ", ".join(sorted(roles)))
    if bio.get("admit_year"):
        reasons.append("admitted %d (%d years)" % (bio["admit_year"], as_of.year - bio["admit_year"]))
    return score, reasons


def select_team(rfp_meta, bios, as_of, size=4):
    """Lead (a partner or of counsel), a backup, and associates. Departed attorneys are never proposed."""
    as_of = parse_iso(as_of)
    active = [b for b in bios if b.get("status", "active") == "active"]
    excluded = [b["name"] for b in bios if b.get("status", "active") != "active"]
    scored = []
    for b in active:
        score, reasons = score_bio(b, rfp_meta, as_of)
        if score > 0 and rfp_meta["practice"] in b.get("practices", []):
            scored.append({"bio": b, "score": score, "reasons": reasons})
    scored.sort(key=lambda x: (-x["score"], x["bio"].get("admit_year") or 9999, x["bio"]["id"]))
    seniors = [s for s in scored if s["bio"]["title"] in LEAD_TITLES]
    others = [s for s in scored if s["bio"]["title"] not in LEAD_TITLES]
    members = []
    if seniors:
        members.append(dict(seniors[0], role="Lead attorney"))
    if len(seniors) > 1:
        members.append(dict(seniors[1], role="Backup attorney"))
    for s in others[:max(0, size - len(members))]:
        members.append(dict(s, role="Team member"))
    return {"lead": members[0] if members and members[0]["role"] == "Lead attorney" else None,
            "members": members, "excluded_departed": excluded}


def check_min_quals(min_quals, team, facts, as_of):
    """Check each minimum qualification that bio or firm data can check.

    status: met | not_met | not_checkable. 'not_checkable' means a person must confirm it.
    """
    as_of = parse_iso(as_of)
    lead = team["lead"]["bio"] if team.get("lead") else None
    out = []
    for q in min_quals:
        kind, val = q["check_kind"], q["value"]
        status, detail = "not_checkable", "cannot be checked from bio or firm data; a person must confirm it"
        if kind == "years_admitted":
            if lead is None:
                status, detail = "not_met", "no lead attorney could be proposed from the bios"
            elif not lead.get("admit_year"):
                detail = "%s has no admission year on file" % lead["name"]
            else:
                years = as_of.year - lead["admit_year"]
                status = "met" if years >= val else "not_met"
                detail = "%s was admitted in %d: %d years against %d required. Bio data holds the year only, " \
                         "so confirm the date and the jurisdiction." % (lead["name"], lead["admit_year"], years, val)
        elif kind == "office_location":
            places = set()
            for o in facts.get("offices", []):
                places |= {o.get("city", "").casefold(), o.get("county", "").casefold()}
            hit = val.casefold() in places
            status = "met" if hit else "not_met"
            detail = ("firm_facts.json lists an office in %s" % val) if hit else \
                     ("firm_facts.json lists no office in %s" % val)
        elif kind == "attorney_count":
            n = facts.get("attorney_count", 0)
            status = "met" if n >= val else "not_met"
            detail = "firm has %d attorneys against %d required; confirm they are available for this client" % (n, val)
        out.append({"id": q["id"], "label": q.get("label", ""), "text": q["text"], "check_kind": kind,
                    "status": status, "detail": detail})
    return out


def select_references(rfp_meta, references, as_of, needed=3, reconfirm_days=365):
    """References that may be listed. Only records with consent are returned as usable."""
    as_of = parse_iso(as_of)
    usable, withheld = [], []
    for r in references:
        score = 0
        if r.get("practice") == rfp_meta["practice"]:
            score += 3
        if r.get("agency_type") == rfp_meta["agency_type"]:
            score += 3
        if score == 0:
            continue
        item = {"record": r, "score": score, "stale": False}
        if r.get("last_confirmed"):
            item["stale"] = (as_of - parse_iso(r["last_confirmed"])).days > reconfirm_days
        else:
            item["stale"] = True
        (usable if r.get("client_consent") is True else withheld).append(item)
    usable.sort(key=lambda x: (-x["score"], x["stale"], x["record"]["id"]))
    withheld.sort(key=lambda x: (-x["score"], x["record"]["id"]))
    return {"selected": usable[:needed], "needed": needed, "withheld_count": len(withheld),
            "withheld_ids": [w["record"]["id"] for w in withheld[:10]]}
