"""Experience finder: who has done this kind of work.

Evidence is matters and time records. A matter matches when every query
term is found in its type or practice, its description, or the titles of its
documents. Equivalent terms (kx/expand.py) count at a lower weight. Matter
text is matched directly against static alternatives; document titles go
through the same visibility-filtered engine as search. Only matters the asking user may see are read (the
same acl.VISIBLE_CTE as search), so a person gets no credit, hours or
"last active" date from a matter the asker is walled from, and that matter
is not listed.

Scoring, per person, is the sum over matching visible matters of
    basis weight x role weight x recency x hours factor
with every weight in config/ranking.json under "experience".
"""
from __future__ import annotations

import copy
import datetime as _dt
import math

from kx import acl
from kx.config import load_config
from kx import expand as expand_mod
from kx.index import FIELD_TITLE
from kx.search import (QueryError, _as_of, _Engine, _filter_sql, _prepare,
                       normalise_filters, parse_query)
from kx.text import tokenize

MATCHED_ON = {"matter": "matter type or practice", "description": "matter description",
              "documents": "document titles in the matter"}
MATTER_FILTERS = ("practice", "matter_type", "jurisdiction", "client_industry", "office")


def _empty(user_id, query, flt, access, message):
    return {"user": user_id, "query": query, "filters": flt, "access": access,
            "message": message, "confident": False, "relaxed": False, "not_found": [],
            "matters_matched": 0, "people_found": 0, "people": []}


def who(conn, user_id: str, query: str = "", filters: dict | None = None,
        config: dict | None = None, as_of=None, limit: int = 10, now=None,
        expand: bool | None = None) -> dict:
    config = config or load_config()
    cfg = config["experience"]
    xcfg = config["expansion"]
    expand = bool(xcfg["enabled"]) if expand is None else bool(expand) and bool(xcfg["enabled"])
    parsed = parse_query(query)
    merged = dict(parsed["filters"])
    merged.update(filters or {})
    flt = normalise_filters(merged)
    for key in flt:
        if key not in MATTER_FILTERS:
            raise QueryError(f"filter {key} applies to documents, not to the experience finder")

    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable as exc:
        return _empty(user_id, query, flt, "unavailable", f"Search is unavailable: {exc}.")
    if not acl.user_can_search(conn, user_id):
        return _empty(user_id, query, flt, "denied",
                      "This user is not an active person in the permission data.")
    groups = expand_mod.build_groups(parsed, config, expand)
    if not groups and not flt:
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

    matched = {}        # matter_id -> (basis, documents with a matching title, factor)
    not_found, relaxed = [], False
    if groups:
        weights = xcfg["weights"]
        static_groups = copy.deepcopy(groups)   # own words and thesaurus, before any index lookup
        engine = _Engine(conn, user_id, config, fields=(FIELD_TITLE,))
        if engine.n:
            _prepare(engine, groups, config, expand)
        doc_matter = dict(conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk, d.matter_id FROM docs d "
            "WHERE d.matter_id IN (SELECT matter_id FROM vis)", {"uid": user_id}))
        # Per group: matter -> (best weight, set of documents whose title satisfies the group)
        title_hits = []
        for g in groups:
            per_matter: dict = {}
            for alt in g.get("live", []):
                docs = None
                for unit in alt["units"]:
                    found = set(engine.unit_docs(unit))
                    docs = found if docs is None else docs & found
                for pk in docs or ():
                    mid = doc_matter.get(pk)
                    if mid in matters:
                        entry = per_matter.setdefault(mid, [0.0, set()])
                        entry[0] = max(entry[0], alt["weight"])
                        entry[1].add(pk)
            title_hits.append(per_matter)
        rows = {}
        for mid, m in matters.items():
            type_tokens = tokenize(f"{m['matter_type'] or ''} . {m['practice'] or ''}")
            text_tokens = type_tokens + ["."] + tokenize(m["description"] or "")
            per_group = []
            for g, hits in zip(static_groups, title_hits):
                w_type = expand_mod.match_tokens(g, type_tokens, expand, weights)
                w_text = max(w_type, expand_mod.match_tokens(g, text_tokens, expand, weights))
                w_title, docs = hits.get(mid, (0.0, set()))
                per_group.append((w_type, w_text, w_title, docs))
            rows[mid] = per_group
        live = [i for i in range(len(groups))
                if any(max(r[i][1], r[i][2]) > 0 for r in rows.values())]
        not_found = [groups[i]["label"] for i in range(len(groups)) if i not in live]

        def assess(per_group, minimum):
            got = [i for i in live if max(per_group[i][1], per_group[i][2]) > 0]
            if not live or len(got) / len(live) < minimum or not got:
                return None
            if all(per_group[i][0] > 0 for i in got):
                basis = "matter"
            elif all(per_group[i][1] > 0 for i in got):
                basis = "description"
            else:
                basis = "documents"
            factor = min(max(per_group[i][1], per_group[i][2]) for i in got) * len(got) / len(live)
            docs = None
            for i in got:
                docs = set(per_group[i][3]) if docs is None else docs & per_group[i][3]
            return basis, len(docs or ()), factor

        for mid, per_group in rows.items():
            verdict = assess(per_group, 1.0)
            if verdict:
                matched[mid] = verdict
        if not matched and len(live) > 1:
            for mid, per_group in rows.items():
                verdict = assess(per_group, float(cfg["relaxed_min_coverage"]))
                if verdict:
                    matched[mid] = verdict
            relaxed = bool(matched)
    else:
        matched = {mid: ("matter", 0, 1.0) for mid in matters}

    notes = []
    if not_found:
        notes.append("Nothing you can open mentions: " + ", ".join(not_found) + ".")
    if relaxed:
        notes.append("No matter matches every term. Showing matters that match most of them.")
    if not matched:
        out = _empty(user_id, query, flt, "ok",
                     " ".join(notes + ["No matching matters among those you can open."]))
        out["not_found"] = not_found
        return out

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
        basis, doc_count, factor = matched[mid]
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
        points = (cfg["basis_weights"][basis] * cfg["role_weights"][role] * recency
                  * hours_factor * factor)
        person = people.setdefault(pid, {"evidence": [], "score": 0.0})
        person["score"] += points
        person["evidence"].append({
            "matter_id": mid, "matter_name": m["name"], "practice": m["practice"],
            "matter_type": m["matter_type"], "jurisdiction": m["jurisdiction"],
            "role": role, "hours": round(hrs, 1), "last_activity": last_activity,
            "matched_on": MATCHED_ON[basis],
            "matching_documents": doc_count, "match_strength": round(factor, 3),
            "points": round(points, 4),
        })

    directory = {r[0]: r for r in conn.execute(
        "SELECT person_id, name, office, practice, title, status FROM people")}
    rows = []
    for pid, person in people.items():
        info = directory.get(pid)
        evidence = sorted(person["evidence"], key=lambda e: (-e["points"], e["matter_id"]))
        total_hours = round(sum(e["hours"] for e in evidence), 1)
        thin = []
        if len(evidence) <= int(cfg["thin_person_max_matters"]):
            thin.append("one matter only" if len(evidence) == 1 else "few matters")
        if total_hours < float(cfg["thin_person_max_hours"]):
            thin.append(f"under {cfg['thin_person_max_hours']} recorded hours")
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
            "evidence_level": "thin" if thin else "ok",
            "evidence_note": "; ".join(thin),
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
        # Too little to call a ranking. People are still put in order of
        # recorded involvement, because that is more use than the alphabet,
        # and the response says plainly how little the order rests on.
        rows.sort(key=lambda r: (-r["score"], r["person_id"]))
        for rank, r in enumerate(rows, start=1):
            r["rank"] = rank
        message = (f"Only {len(matched)} matching matter{'s' if len(matched) != 1 else ''} "
                   "you can open. That is too little to rank on: treat the people below "
                   "as leads to ask. They are in order of recorded involvement.")
    message = " ".join(notes + ([message] if message else []))
    return {"user": user_id, "query": query, "filters": flt, "access": "ok", "message": message,
            "confident": confident, "relaxed": relaxed, "not_found": not_found,
            "matters_matched": len(matched), "people_found": len(rows), "people": rows[:limit]}
