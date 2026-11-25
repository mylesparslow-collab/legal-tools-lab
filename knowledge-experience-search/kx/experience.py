"""Experience finder: who has done this kind of work.

Evidence is matters and time records. A matter matches when every query
term is in its type or practice, or in its description, or in the title of
at least one of its documents. Only matters the asking user may see are read (the
same acl.VISIBLE_CTE as search), so a person gets no credit, hours or
"last active" date from a matter the asker is walled from, and that matter
is not listed.

Scoring, per person, is the sum over matching visible matters of
    basis weight x role weight x recency x hours factor
with every weight in config/ranking.json under "experience".
"""
from __future__ import annotations

import datetime as _dt
import math

from kx import acl
from kx.config import load_config
from kx.search import (QueryError, _as_of, _filter_sql, matching_matters,
                       normalise_filters, parse_query)
from kx.text import tokenize

MATCHED_ON = {"matter": "matter type or practice", "description": "matter description",
              "documents": "document titles in the matter"}
MATTER_FILTERS = ("practice", "matter_type", "jurisdiction", "client_industry", "office")


def _empty(user_id, query, flt, access, message):
    return {"user": user_id, "query": query, "filters": flt, "access": access,
            "message": message, "confident": False, "matters_matched": 0, "people": []}


def who(conn, user_id: str, query: str = "", filters: dict | None = None,
        config: dict | None = None, as_of=None, limit: int = 10, now=None) -> dict:
    config = config or load_config()
    cfg = config["experience"]
    parsed = parse_query(query)
    merged = dict(parsed["filters"])
    merged.update(filters or {})
    flt = normalise_filters(merged)
    for key in flt:
        if key not in MATTER_FILTERS:
            raise QueryError(f"filter {key} applies to documents, not to the experience finder")
    terms = list(parsed["terms"])
    for phrase in parsed["phrases"]:
        for tok in phrase:
            if tok not in terms:
                terms.append(tok)

    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable as exc:
        return _empty(user_id, query, flt, "unavailable", f"Search is unavailable: {exc}.")
    if not acl.user_can_search(conn, user_id):
        return _empty(user_id, query, flt, "denied",
                      "This user is not an active person in the permission data.")
    if not terms and not flt:
        return _empty(user_id, query, flt, "ok", "Describe the work or choose a filter.")

    params = {"uid": user_id}
    filter_sql = _filter_sql(flt, params)  # matter filters only reference alias m
    matters = {}
    for row in conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT m.matter_id, m.name, m.practice, m.matter_type, "
            "m.jurisdiction, m.client_industry, m.office, m.opened, m.closed, m.description "
            f"FROM matters m WHERE m.matter_id IN (SELECT matter_id FROM vis){filter_sql}", params):
        matters[row[0]] = {"matter_id": row[0], "name": row[1], "practice": row[2],
                           "matter_type": row[3], "jurisdiction": row[4],
                           "client_industry": row[5], "office": row[6], "opened": row[7],
                           "closed": row[8], "description": row[9]}

    matched = {}  # matter_id -> (basis, matching document count)
    if terms:
        doc_counts = matching_matters(conn, user_id, terms, config)
        for mid, m in matters.items():
            # All terms must fall within one kind of evidence. Mixing fields
            # (one word from the court name, one from the description)
            # produced matches that meant nothing.
            type_tokens = set(tokenize(f"{m['matter_type'] or ''} {m['practice'] or ''}"))
            desc_tokens = set(tokenize(m["description"] or ""))
            if all(t in type_tokens for t in terms):
                matched[mid] = ("matter", doc_counts.get(mid, 0))
            elif all(t in desc_tokens for t in terms):
                matched[mid] = ("description", doc_counts.get(mid, 0))
            elif doc_counts.get(mid):
                matched[mid] = ("documents", doc_counts[mid])
    else:
        matched = {mid: ("matter", 0) for mid in matters}

    if not matched:
        return _empty(user_id, query, flt, "ok",
                      "No matching matters among those you can open.")

    roles = {}
    for mid, pid, role in conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT t.matter_id, t.person_id, t.role FROM matter_team t "
            "WHERE t.matter_id IN (SELECT matter_id FROM vis)", {"uid": user_id}):
        if mid in matched:
            roles[(mid, pid)] = role if role in ("lead", "support") else "support"
    hours = {}
    for mid, pid, total, last in conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT e.matter_id, e.person_id, SUM(e.hours), "
            "MAX(e.work_date) FROM time_entries e "
            "WHERE e.matter_id IN (SELECT matter_id FROM vis) "
            "GROUP BY e.matter_id, e.person_id", {"uid": user_id}):
        if mid in matched:
            hours[(mid, pid)] = (float(total or 0.0), last or "")

    when = _as_of(config, as_of)
    half_life = float(cfg["recency_half_life_years"])
    people: dict = {}
    for key in sorted(set(roles) | set(hours)):
        mid, pid = key
        m = matters[mid]
        basis, doc_count = matched[mid]
        role = roles.get(key, "timekeeper")
        hrs, last = hours.get(key, (0.0, ""))
        last_activity = last or m["closed"] or m["opened"] or ""
        try:
            years = max(0.0, (when - _dt.date.fromisoformat(last_activity[:10])).days / 365.25)
            recency = 0.5 ** (years / half_life)
        except ValueError:
            recency = 0.0
        hours_factor = max(float(cfg["hours_floor"]),
                           min(1.0, math.log1p(hrs) / math.log1p(float(cfg["hours_cap"]))))
        points = (cfg["basis_weights"][basis] * cfg["role_weights"][role] * recency * hours_factor)
        person = people.setdefault(pid, {"evidence": [], "score": 0.0})
        person["score"] += points
        person["evidence"].append({
            "matter_id": mid, "matter_name": m["name"], "practice": m["practice"],
            "matter_type": m["matter_type"], "jurisdiction": m["jurisdiction"],
            "role": role, "hours": round(hrs, 1), "last_activity": last_activity,
            "matched_on": MATCHED_ON[basis],
            "matching_documents": doc_count, "points": round(points, 4),
        })

    directory = {r[0]: r for r in conn.execute(
        "SELECT person_id, name, office, practice, title, status FROM people")}
    rows = []
    for pid, person in people.items():
        info = directory.get(pid)
        evidence = sorted(person["evidence"], key=lambda e: (-e["points"], e["matter_id"]))
        total_hours = round(sum(e["hours"] for e in evidence), 1)
        notes = []
        if len(evidence) <= int(cfg["thin_person_max_matters"]):
            notes.append("one matter only" if len(evidence) == 1 else "few matters")
        if total_hours < float(cfg["thin_person_max_hours"]):
            notes.append(f"under {cfg['thin_person_max_hours']} recorded hours")
        status = info[5] if info else "unknown"
        rows.append({
            "person_id": pid, "name": info[1] if info else pid,
            "office": info[2] if info else "", "practice": info[3] if info else "",
            "title": info[4] if info else "",
            "departed": status == "departed",
            "status_note": ("Has left the firm. Listed so the work can still be found."
                            if status == "departed" else
                            ("Not in the people directory." if info is None else "")),
            "score": round(person["score"], 4), "matters": len(evidence),
            "lead_matters": sum(1 for e in evidence if e["role"] == "lead"),
            "hours": total_hours,
            "last_activity": max((e["last_activity"] for e in evidence), default=""),
            "evidence_level": "thin" if notes else "ok",
            "evidence_note": "; ".join(notes),
            "evidence": evidence,
        })

    confident = (len(matched) >= int(cfg["confident_min_matters"])
                 and any(r["evidence_level"] == "ok" for r in rows))
    if confident:
        rows.sort(key=lambda r: (r["evidence_level"] != "ok", -r["score"], r["person_id"]))
        rank = 0
        for r in rows:
            if r["evidence_level"] == "ok":
                rank += 1
                r["rank"] = rank
            else:
                r["rank"] = None
        message = ""
    else:
        rows.sort(key=lambda r: (r["name"], r["person_id"]))
        for r in rows:
            r["rank"] = None
        message = (f"Only {len(matched)} matching matter{'s' if len(matched) != 1 else ''} "
                   "you can open. Too little to rank: the people below are listed by name "
                   "as leads to ask, not as a ranking.")
    return {"user": user_id, "query": query, "filters": flt, "access": "ok", "message": message,
            "confident": confident, "matters_matched": len(matched),
            "people_found": len(rows), "people": rows[:limit]}
