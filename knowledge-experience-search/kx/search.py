"""Permission-scoped search.

Every SQL statement in this module that reads documents, postings or
near-duplicate edges includes acl.VISIBLE_CTE and restricts to it. Rows the
asking user may not see are never fetched. In particular:

* candidates, snippets, facets, totals and collapse lists come only from
  fetched (visible) rows;
* the BM25 statistics (document count, document frequencies, average field
  lengths) are computed over the visible set at query time, so a term that
  exists only behind a wall has no effect on any score the user sees;
* near-duplicate and version collapse run over visible results only.

The design test (tests/test_noninterference.py) is: a user's output must be
identical to what they would get from an index that never contained the
documents they cannot see.
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from collections import Counter

from kx import acl
from kx.config import load_config
from kx.index import FIELD_BODY, FIELD_META, FIELD_NAMES, FIELD_TITLE
from kx.text import STOP_WORDS, raw_tokens, stem, tokenize

FILTER_ALIASES = {
    "type": "doc_type", "doctype": "doc_type", "doc_type": "doc_type",
    "practice": "practice",
    "mtype": "matter_type", "matter_type": "matter_type", "mattertype": "matter_type",
    "jurisdiction": "jurisdiction", "court": "jurisdiction", "forum": "jurisdiction",
    "industry": "client_industry", "client_industry": "client_industry",
    "office": "office", "author": "author",
    "after": "after", "before": "before", "year": "year",
    "filed": "was_filed", "was_filed": "was_filed",
    "model": "model_form", "model_form": "model_form",
    "final": "is_final", "is_final": "is_final",
}
BOOLEAN_FILTERS = ("was_filed", "model_form", "is_final")
FACET_FIELDS = ("doc_type", "practice", "matter_type", "jurisdiction", "client_industry", "year")

_FILTER_RE = re.compile(r'(\w+):(?:"([^"]*)"|(\S+))')
_PHRASE_RE = re.compile(r'"([^"]+)"')
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


class QueryError(ValueError):
    """The query or a filter could not be understood."""


def parse_query(text: str) -> dict:
    """Split a query string into loose terms, phrases and field filters."""
    text = text or ""
    filters = {}

    def take_filter(match):
        key = FILTER_ALIASES.get(match.group(1).lower())
        if key is None:
            return match.group(0)  # not a filter; leave it as text
        value = match.group(2) if match.group(2) is not None else match.group(3)
        filters[key] = value
        return " "

    rest = _FILTER_RE.sub(take_filter, text)
    phrases = []
    for m in _PHRASE_RE.finditer(rest):
        toks = tokenize(m.group(1))
        if toks and toks not in phrases:
            phrases.append(toks)
    rest = _PHRASE_RE.sub(" ", rest).replace('"', " ")
    terms = []
    for t in raw_tokens(rest):
        if t in STOP_WORDS:
            continue
        s = stem(t)
        if s not in terms:
            terms.append(s)
    return {"terms": terms, "phrases": phrases, "filters": filters}


def _as_bool(key: str, value) -> int:
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y"):
        return 1
    if text in ("0", "false", "no", "n"):
        return 0
    raise QueryError(f"filter {key} needs yes or no, not {value!r}")


def normalise_filters(filters: dict | None) -> dict:
    out = {}
    for key, value in (filters or {}).items():
        if value in (None, ""):
            continue
        canonical = FILTER_ALIASES.get(str(key).lower())
        if canonical is None:
            raise QueryError(f"unknown filter {key!r}")
        out[canonical] = _as_bool(canonical, value) if canonical in BOOLEAN_FILTERS else str(value).strip()
    return out


def _filter_sql(filters: dict, params: dict) -> str:
    """SQL conditions over aliases d (docs) and m (matters). Values go in as parameters."""
    clauses = []
    simple = {"doc_type": "d.doc_type", "practice": "m.practice", "matter_type": "m.matter_type",
              "jurisdiction": "m.jurisdiction", "client_industry": "m.client_industry",
              "office": "m.office"}
    for key, value in filters.items():
        name = f"f_{key}"
        if key in simple:
            clauses.append(f"LOWER({simple[key]}) = :{name}")
            params[name] = str(value).lower()
        elif key in BOOLEAN_FILTERS:
            clauses.append(f"d.{key} = :{name}")
            params[name] = int(value)
        elif key == "after":
            clauses.append(f"d.doc_date >= :{name}")
            params[name] = value
        elif key == "before":
            clauses.append(f"d.doc_date <= :{name}")
            params[name] = value
        elif key == "year":
            clauses.append(f"substr(d.doc_date, 1, 4) = :{name}")
            params[name] = str(value)
        elif key == "author":
            clauses.append(f"(d.author_id = :{name} OR d.author_id IN "
                           f"(SELECT person_id FROM people WHERE LOWER(name) LIKE :{name}_like))")
            params[name] = value
            params[f"{name}_like"] = f"%{str(value).lower()}%"
    return "".join(f" AND {c}" for c in clauses)


def _in_list(prefix: str, values, params: dict) -> str:
    names = []
    for i, v in enumerate(values):
        params[f"{prefix}{i}"] = v
        names.append(f":{prefix}{i}")
    return ",".join(names) or "NULL"


def _has_phrase(positions_by_term: dict, phrase: list) -> bool:
    """positions_by_term: term -> list of positions, for one document field."""
    lists = []
    for tok in phrase:
        p = positions_by_term.get(tok)
        if not p:
            return False
        lists.append(p)
    later = [set(p) for p in lists[1:]]
    return any(all((start + i + 1) in s for i, s in enumerate(later)) for start in lists[0])


def _empty(user_id, query, parsed_filters, access, message=""):
    return {"user": user_id, "query": query, "filters": parsed_filters, "access": access,
            "message": message, "relaxed": False, "total": 0, "offset": 0, "results": [],
            "facets": {f: [] for f in FACET_FIELDS}}


def _as_of(config, as_of):
    value = as_of or config.get("as_of")
    if isinstance(value, _dt.date):
        return value
    if value:
        return _dt.date.fromisoformat(str(value)[:10])
    return _dt.date.today()


def _recency(doc_date: str, as_of: _dt.date, half_life: float) -> float:
    try:
        d = _dt.date.fromisoformat((doc_date or "")[:10])
    except ValueError:
        return 0.0
    years = max(0.0, (as_of - d).days / 365.25)
    return 0.5 ** (years / half_life)


def _snippet(body: str, wanted: set, words: int) -> dict:
    """A window of the document's own body with the most distinct query terms."""
    spans = [(m.start(), m.end(), stem(m.group(0).lower())) for m in _WORD_RE.finditer(body or "")]
    if not spans:
        return {"text": "", "highlights": []}
    best_start, best_score = 0, -1
    if wanted:
        hits = [i for i, s in enumerate(spans) if s[2] in wanted]
        for i in hits:
            start = max(0, i - 4)
            window = spans[start:start + words]
            score = len({s[2] for s in window if s[2] in wanted})
            if score > best_score:
                best_start, best_score = start, score
    window = spans[best_start:best_start + words]
    lo, hi = window[0][0], window[-1][1]
    prefix = "… " if best_start > 0 else ""
    suffix = " …" if best_start + words < len(spans) else ""
    text = prefix + body[lo:hi] + suffix
    shift = len(prefix) - lo
    highlights = [[s + shift, e + shift] for s, e, t in window if t in wanted]
    return {"text": text, "highlights": highlights}


def _retrieve(conn, user_id: str, terms: list, phrases: list, filters: dict, config: dict,
              require_all: bool, fields: tuple | None = None):
    """Fetch and text-score visible candidates. Returns (candidates, stats).

    candidates: doc_pk -> dict with lengths, per-term per-field tf and bm25.
    Everything read here is restricted to the user's visible matters in SQL.
    """
    params = {"uid": user_id}
    n_docs, sum_t, sum_b, sum_m = conn.execute(
        f"WITH {acl.VISIBLE_CTE} SELECT COUNT(*), COALESCE(SUM(d.len_title),0), "
        "COALESCE(SUM(d.len_body),0), COALESCE(SUM(d.len_meta),0) FROM docs d "
        "WHERE d.matter_id IN (SELECT matter_id FROM vis)", params).fetchone()
    stats = {"n_visible": n_docs, "df": {}}
    if n_docs == 0:
        return {}, stats
    avg_len = {FIELD_TITLE: (sum_t / n_docs) or 1.0, FIELD_BODY: (sum_b / n_docs) or 1.0,
               FIELD_META: (sum_m / n_docs) or 1.0}

    all_terms = list(terms)
    for ph in phrases:
        for t in ph:
            if t not in all_terms:
                all_terms.append(t)

    filter_params = dict(params)
    filter_sql = _filter_sql(filters, filter_params)

    if not all_terms:
        rows = conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk FROM docs d "
            "JOIN matters m ON m.matter_id = d.matter_id "
            f"WHERE d.matter_id IN (SELECT matter_id FROM vis){filter_sql}", filter_params)
        return {r[0]: {"bm25": 0.0, "terms": {}} for r in rows}, stats

    id_params: dict = {}
    marks = _in_list("t", all_terms, id_params)
    term_ids = dict(conn.execute(f"SELECT term, term_id FROM terms WHERE term IN ({marks})",
                                 id_params))
    id_to_term = {v: k for k, v in term_ids.items()}
    if not term_ids:
        return {}, stats

    df_params = dict(params)
    id_marks = _in_list("i", list(term_ids.values()), df_params)
    for term_id, count in conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT p.term_id, COUNT(DISTINCT p.doc_pk) FROM postings p "
            "JOIN docs d ON d.doc_pk = p.doc_pk "
            f"WHERE p.term_id IN ({id_marks}) AND d.matter_id IN (SELECT matter_id FROM vis) "
            "GROUP BY p.term_id", df_params):
        stats["df"][id_to_term[term_id]] = count

    post_params = dict(filter_params)
    field_sql = ""
    if fields:
        field_sql = f" AND p.field IN ({','.join(str(int(f)) for f in fields)})"
    id_marks = _in_list("i", list(term_ids.values()), post_params)
    docs: dict = {}
    for doc_pk, term_id, field, tf, positions, lt, lb, lm in conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT p.doc_pk, p.term_id, p.field, p.tf, p.positions, "
            "d.len_title, d.len_body, d.len_meta FROM postings p "
            "JOIN docs d ON d.doc_pk = p.doc_pk JOIN matters m ON m.matter_id = d.matter_id "
            f"WHERE p.term_id IN ({id_marks}) AND d.matter_id IN (SELECT matter_id FROM vis)"
            f"{field_sql}{filter_sql}", post_params):
        entry = docs.setdefault(doc_pk, {"len": {FIELD_TITLE: lt, FIELD_BODY: lb, FIELD_META: lm},
                                         "tf": {}, "pos": {}})
        term = id_to_term[term_id]
        entry["tf"].setdefault(term, {})[field] = tf
        if phrases:
            entry["pos"].setdefault(field, {})[term] = [int(x) for x in positions.split(",")]

    bm = config["bm25"]
    k1, b = bm["k1"], bm["b"]
    weights = {FIELD_TITLE: bm["field_weights"]["title"], FIELD_BODY: bm["field_weights"]["body"],
               FIELD_META: bm["field_weights"]["metadata"]}
    idf = {t: math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5)) for t, df in stats["df"].items()}

    candidates = {}
    for doc_pk, entry in docs.items():
        if phrases and not all(
                any(_has_phrase(entry["pos"].get(f, {}), ph) for f in (FIELD_TITLE, FIELD_BODY))
                for ph in phrases):
            continue
        if terms:
            present = [t for t in terms if t in entry["tf"]]
            if require_all and len(present) != len(terms):
                continue
            if not require_all and not present and not phrases:
                continue
        total = 0.0
        per_term = {}
        for t in all_terms:
            fields = entry["tf"].get(t)
            if not fields:
                continue
            wtf = 0.0
            for f, tf in sorted(fields.items()):
                norm = 1.0 - b + b * (entry["len"][f] / avg_len[f])
                wtf += weights[f] * tf / norm
            score = idf[t] * wtf / (k1 + wtf)
            total += score
            per_term[t] = {"idf": idf[t], "fields": dict(fields), "score": score}
        candidates[doc_pk] = {"bm25": total, "terms": per_term}
    return candidates, stats


def _load_docs(conn, user_id: str, doc_pks: list) -> dict:
    """Metadata and body for candidate documents, again restricted to the visible set."""
    out = {}
    pks = sorted(doc_pks)
    for start in range(0, len(pks), 400):
        params = {"uid": user_id}
        marks = _in_list("k", pks[start:start + 400], params)
        for row in conn.execute(
                f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk, d.doc_id, d.matter_id, d.title, d.body, "
                "d.doc_type, d.author_id, d.doc_date, d.family_id, d.version_no, d.is_final, "
                "d.was_filed, d.model_form, d.reuse_count, m.name, m.practice, m.matter_type, "
                "m.jurisdiction, m.client_industry, m.office, a.name, a.status "
                "FROM docs d JOIN matters m ON m.matter_id = d.matter_id "
                "LEFT JOIN people a ON a.person_id = d.author_id "
                f"WHERE d.doc_pk IN ({marks}) AND d.matter_id IN (SELECT matter_id FROM vis)",
                params):
            out[row[0]] = {
                "doc_id": row[1], "matter_id": row[2], "title": row[3], "body": row[4] or "",
                "doc_type": row[5], "author_id": row[6], "date": row[7], "family_id": row[8],
                "version_no": row[9], "is_final": bool(row[10]), "was_filed": bool(row[11]),
                "model_form": bool(row[12]), "reuse_count": row[13] or 0, "matter_name": row[14],
                "practice": row[15], "matter_type": row[16], "jurisdiction": row[17],
                "client_industry": row[18], "office": row[19], "author_name": row[20] or "",
                "author_status": row[21] or "unknown",
            }
    return out


def _visible_edges(conn, user_id: str) -> list:
    """Near-duplicate pairs where both documents are visible to the user."""
    return conn.execute(
        f"WITH {acl.VISIBLE_CTE} SELECT a.doc_pk, b.doc_pk FROM near_dups n "
        "JOIN docs a ON a.doc_pk = n.doc_a JOIN docs b ON b.doc_pk = n.doc_b "
        "WHERE a.matter_id IN (SELECT matter_id FROM vis) "
        "AND b.matter_id IN (SELECT matter_id FROM vis)", {"uid": user_id}).fetchall()


def search(conn, user_id: str, query: str = "", filters: dict | None = None,
           config: dict | None = None, limit: int = 10, offset: int = 0, explain: bool = False,
           as_of=None, reranker=None, now=None) -> dict:
    """Run one query as one user. Returns a plain dict ready for JSON."""
    config = config or load_config()
    parsed = parse_query(query)
    merged = dict(parsed["filters"])
    merged.update(filters or {})
    flt = normalise_filters(merged)
    terms, phrases = parsed["terms"], parsed["phrases"]

    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable as exc:
        return _empty(user_id, query, flt, "unavailable",
                      f"Search is unavailable: {exc}.")
    if not acl.user_can_search(conn, user_id):
        return _empty(user_id, query, flt, "denied",
                      "This user is not an active person in the permission data.")
    if not terms and not phrases and not flt:
        out = _empty(user_id, query, flt, "ok", "Enter a search term or choose a filter.")
        return out

    require_all = config.get("match_mode", "all") == "all"
    candidates, stats = _retrieve(conn, user_id, terms, phrases, flt, config, require_all)
    relaxed = False
    if not candidates and require_all and len(terms) > 1 and config.get("relax_to_any_when_empty"):
        candidates, stats = _retrieve(conn, user_id, terms, phrases, flt, config, False)
        relaxed = bool(candidates)

    docs = _load_docs(conn, user_id, list(candidates))
    blend = config["blend"]
    when = _as_of(config, as_of)
    max_bm25 = max((c["bm25"] for pk, c in candidates.items() if pk in docs), default=0.0)
    reuse_cap = max(1, int(config.get("reuse_cap", 20)))
    scored = []
    for pk, cand in candidates.items():
        doc = docs.get(pk)
        if doc is None:
            continue
        text_value = (cand["bm25"] / max_bm25) if max_bm25 > 0 else 0.0
        signals = [
            ("model_form", 1.0 if doc["model_form"] else 0.0),
            ("is_final", 1.0 if doc["is_final"] else 0.0),
            ("was_filed", 1.0 if doc["was_filed"] else 0.0),
            ("reuse", min(1.0, math.log1p(doc["reuse_count"]) / math.log1p(reuse_cap))),
            ("recency", _recency(doc["date"], when, float(config["recency_half_life_years"]))),
        ]
        score = blend["text"] * text_value + sum(blend[name] * value for name, value in signals)
        scored.append({"pk": pk, "doc": doc, "cand": cand, "text_value": text_value,
                       "signals": signals, "score": score})
    scored.sort(key=lambda r: (-round(r["score"], 9), r["doc"]["doc_id"]))

    # Version families: keep one document per family among the matches,
    # preferring the final, then the highest version number.
    families: dict = {}
    for r in scored:
        fam = r["doc"]["family_id"]
        if fam:
            families.setdefault(fam, []).append(r)
    dropped = set()
    for fam, members in families.items():
        if len(members) < 2:
            continue
        keep = max(members, key=lambda r: (r["doc"]["is_final"], r["doc"]["version_no"],
                                           r["doc"]["doc_id"]))
        keep["other_versions"] = sorted(
            ({"doc_id": r["doc"]["doc_id"], "version_no": r["doc"]["version_no"],
              "is_final": r["doc"]["is_final"]} for r in members if r is not keep),
            key=lambda v: (v["version_no"], v["doc_id"]))
        dropped.update(r["pk"] for r in members if r is not keep)
    reps = [r for r in scored if r["pk"] not in dropped]

    # Near-duplicates: walk the ranked list; fold a document into the first
    # higher-ranked kept document it is a near-duplicate of.
    rep_pks = {r["pk"] for r in reps}
    neighbours: dict = {}
    for a, b in _visible_edges(conn, user_id):
        if a in rep_pks and b in rep_pks:
            neighbours.setdefault(a, set()).add(b)
            neighbours.setdefault(b, set()).add(a)
    kept, kept_by_pk = [], {}
    for r in reps:
        target = None
        for other in kept:
            if other["pk"] in neighbours.get(r["pk"], ()):
                target = other
                break
        if target is None:
            kept.append(r)
            kept_by_pk[r["pk"]] = r
        else:
            target.setdefault("near_duplicates", []).append(
                {"doc_id": r["doc"]["doc_id"], "matter_id": r["doc"]["matter_id"],
                 "title": r["doc"]["title"]})

    reranked = False
    if reranker is not None and kept:
        top_k = int(config.get("rerank_top_k", 20))
        head = kept[:top_k]
        new_scores = list(reranker.rerank(query, [
            {"doc_id": r["doc"]["doc_id"], "title": r["doc"]["title"], "body": r["doc"]["body"]}
            for r in head]))
        if len(new_scores) != len(head):
            raise ValueError("reranker must return one score per document")
        for r, s in zip(head, new_scores):
            r["rerank_score"] = float(s)
        head.sort(key=lambda r: (-r["rerank_score"], r["doc"]["doc_id"]))
        kept = head + kept[top_k:]
        reranked = True

    facets = {}
    shown = int(config.get("facet_values_shown", 12))
    for field in FACET_FIELDS:
        counter = Counter()
        for r in kept:
            value = (r["doc"]["date"] or "")[:4] if field == "year" else r["doc"][field]
            if value:
                counter[value] += 1
        facets[field] = [{"value": v, "count": c}
                         for v, c in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:shown]]

    wanted = set(terms)
    for ph in phrases:
        wanted.update(ph)
    results = []
    page = kept[offset:offset + limit]
    for rank, r in enumerate(page, start=offset + 1):
        doc = r["doc"]
        item = {
            "rank": rank, "doc_id": doc["doc_id"], "title": doc["title"],
            "doc_type": doc["doc_type"], "date": doc["date"],
            "matter_id": doc["matter_id"], "matter_name": doc["matter_name"],
            "practice": doc["practice"], "matter_type": doc["matter_type"],
            "jurisdiction": doc["jurisdiction"], "client_industry": doc["client_industry"],
            "office": doc["office"],
            "author": {"person_id": doc["author_id"], "name": doc["author_name"],
                       "departed": doc["author_status"] == "departed"},
            "version_no": doc["version_no"], "is_final": doc["is_final"],
            "was_filed": doc["was_filed"], "model_form": doc["model_form"],
            "reuse_count": doc["reuse_count"], "score": round(r["score"], 6),
            "snippet": _snippet(doc["body"], wanted, int(config.get("snippet_words", 30))),
            "other_versions": r.get("other_versions", []),
            "near_duplicates": r.get("near_duplicates", []),
        }
        if explain:
            item["explain"] = _explain(r, stats, blend, max_bm25, reranked)
        results.append(item)

    message = ""
    if relaxed:
        message = "No document has every term. Showing documents that match some of them."
    elif not kept:
        message = "Nothing found among the documents you can open."
    return {"user": user_id, "query": query, "filters": flt, "access": "ok", "message": message,
            "relaxed": relaxed, "reranked": reranked, "total": len(kept), "offset": offset,
            "results": results, "facets": facets}


def _explain(r: dict, stats: dict, blend: dict, max_bm25: float, reranked: bool) -> dict:
    terms = []
    for term, info in r["cand"]["terms"].items():
        terms.append({
            "term": term,
            "matched_in": {FIELD_NAMES[f]: tf for f, tf in sorted(info["fields"].items())},
            "documents_you_can_see_with_term": stats["df"].get(term, 0),
            "idf": round(info["idf"], 4),
            "bm25": round(info["score"], 4),
        })
    signals = [{"signal": name, "value": round(value, 4), "weight": blend[name],
                "contribution": round(blend[name] * value, 4)} for name, value in r["signals"]]
    out = {
        "text": {"bm25": round(r["cand"]["bm25"], 4),
                 "best_bm25_in_your_results": round(max_bm25, 4),
                 "value": round(r["text_value"], 4), "weight": blend["text"],
                 "contribution": round(blend["text"] * r["text_value"], 4), "terms": terms},
        "signals": signals,
        "total": round(r["score"], 6),
        "statistics_scope": f"{stats['n_visible']} documents you can open",
    }
    if reranked and "rerank_score" in r:
        out["rerank_score"] = r["rerank_score"]
    return out


def matching_matters(conn, user_id: str, terms: list, config: dict | None = None) -> dict:
    """matter_id -> number of visible documents whose title has every term. For kx/experience.py."""
    config = config or load_config()
    if not terms:
        return {}
    candidates, _ = _retrieve(conn, user_id, terms, [], {}, config, True, fields=(FIELD_TITLE,))
    docs = _load_docs(conn, user_id, list(candidates))
    counts = Counter(d["matter_id"] for d in docs.values())
    return dict(counts)


def suggest(conn, user_id: str, prefix: str, limit: int = 8, config: dict | None = None,
            now=None) -> list:
    """Complete the last word of ``prefix`` from titles and metadata of visible documents only."""
    tokens = raw_tokens(prefix or "")
    if not tokens or len(tokens[-1]) < 2 or not (prefix or "")[-1:].isalnum():
        return []
    config = config or load_config()
    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable:
        return []
    stub = tokens[-1]
    rows = conn.execute(
        f"WITH {acl.VISIBLE_CTE} SELECT t.term, COUNT(DISTINCT p.doc_pk) AS n FROM terms t "
        "JOIN postings p ON p.term_id = t.term_id JOIN docs d ON d.doc_pk = p.doc_pk "
        "WHERE t.term >= :lo AND t.term < :hi AND p.field IN (:f_title, :f_meta) "
        "AND d.matter_id IN (SELECT matter_id FROM vis) "
        "GROUP BY t.term ORDER BY n DESC, t.term LIMIT :limit",
        {"uid": user_id, "lo": stub, "hi": stub + "￿", "f_title": FIELD_TITLE,
         "f_meta": FIELD_META, "limit": int(limit)})
    return [r[0] for r in rows if r[0] not in STOP_WORDS]
