"""Permission-scoped search.

Every SQL statement in this module that reads documents, postings or
near-duplicate edges includes acl.VISIBLE_CTE and restricts to it. Rows the
asking user may not see are never fetched. In particular:

* candidates, snippets, facets, totals and collapse lists come only from
  fetched (visible) rows;
* the BM25 statistics (document count, document frequencies, average field
  lengths) are computed over the visible set at query time, so a term that
  exists only behind a wall has no effect on any score the user sees;
* near-duplicate and version collapse run over visible results only;
* vocabulary bridging (kx/expand.py) proposes alternatives from static data,
  and an alternative is kept, counted and shown only if it occurs in the
  visible set. "Related" terms are taken from the user's own top results.

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
from kx import expand as expand_mod
from kx.text import (QUERY_FILLER, STOP_WORDS, edit_distance, raw_tokens, root, stem,
                     tokenize)

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
    terms, sequence = [], []
    for t in raw_tokens(rest):
        s = stem(t)
        sequence.append((s, t))
        if t in STOP_WORDS or t in QUERY_FILLER:
            continue
        if s not in terms:
            terms.append(s)
    return {"terms": terms, "phrases": phrases, "filters": filters, "sequence": sequence}


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


def _empty(user_id, query, parsed_filters, access, message=""):
    return {"user": user_id, "query": query, "filters": parsed_filters, "access": access,
            "message": message, "relaxed": False, "reranked": False, "total": 0, "offset": 0,
            "results": [], "facets": {f: [] for f in FACET_FIELDS},
            "expansion": {"on": False, "used": [], "not_found": [], "corrected": [],
                          "related_terms": []}}


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


class _Engine:
    """Reads and scores postings for one user. Every read is restricted to the
    user's visible matters, and every statistic is a visible-set statistic."""

    def __init__(self, conn, user_id: str, config: dict, fields: tuple | None = None):
        self.conn, self.uid, self.config = conn, user_id, config
        self.field_sql = ""
        if fields:
            self.field_sql = f" AND p.field IN ({','.join(str(int(f)) for f in fields)})"
        n, st, sb, sm = conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT COUNT(*), COALESCE(SUM(d.len_title),0), "
            "COALESCE(SUM(d.len_body),0), COALESCE(SUM(d.len_meta),0) FROM docs d "
            "WHERE d.matter_id IN (SELECT matter_id FROM vis)", {"uid": user_id}).fetchone()
        self.n = n
        self.avg = {FIELD_TITLE: (st / n) or 1.0, FIELD_BODY: (sb / n) or 1.0,
                    FIELD_META: (sm / n) or 1.0} if n else {}
        bm = config["bm25"]
        self.k1, self.b = bm["k1"], bm["b"]
        self.w = {FIELD_TITLE: bm["field_weights"]["title"], FIELD_BODY: bm["field_weights"]["body"],
                  FIELD_META: bm["field_weights"]["metadata"]}
        self.ids: dict = {}      # term -> term_id, or None if the index has never seen it
        self.df: dict = {}       # term -> number of visible documents containing it
        self.post: dict = {}     # term -> {doc_pk: {field: (tf, positions)}}
        self.lens: dict = {}     # doc_pk -> {field: length}
        self._phrase: dict = {}

    def _resolve(self, terms):
        missing = sorted({t for t in terms if t not in self.ids})
        for start in range(0, len(missing), 400):
            chunk = missing[start:start + 400]
            params: dict = {}
            marks = _in_list("t", chunk, params)
            found = dict(self.conn.execute(
                f"SELECT term, term_id FROM terms WHERE term IN ({marks})", params))
            for t in chunk:
                self.ids[t] = found.get(t)

    def load_df(self, terms) -> None:
        self._resolve(terms)
        todo = sorted({t for t in terms if t not in self.df})
        known = [t for t in todo if self.ids[t] is not None]
        for t in todo:
            self.df[t] = 0
        back = {self.ids[t]: t for t in known}
        for start in range(0, len(known), 400):
            params = {"uid": self.uid}
            marks = _in_list("i", [self.ids[t] for t in known[start:start + 400]], params)
            for term_id, count in self.conn.execute(
                    f"WITH {acl.VISIBLE_CTE} SELECT p.term_id, COUNT(DISTINCT p.doc_pk) "
                    "FROM postings p JOIN docs d ON d.doc_pk = p.doc_pk "
                    f"WHERE p.term_id IN ({marks}) AND d.matter_id IN (SELECT matter_id FROM vis)"
                    f"{self.field_sql} GROUP BY p.term_id", params):
                self.df[back[term_id]] = count

    def fetch(self, terms) -> None:
        self.load_df(terms)
        todo = sorted({t for t in terms if t not in self.post})
        for t in todo:
            self.post[t] = {}
        known = [t for t in todo if self.df[t] > 0]
        back = {self.ids[t]: t for t in known}
        for start in range(0, len(known), 400):
            params = {"uid": self.uid}
            marks = _in_list("i", [self.ids[t] for t in known[start:start + 400]], params)
            for pk, term_id, field, tf, positions, lt, lb, lm in self.conn.execute(
                    f"WITH {acl.VISIBLE_CTE} SELECT p.doc_pk, p.term_id, p.field, p.tf, "
                    "p.positions, d.len_title, d.len_body, d.len_meta FROM postings p "
                    "JOIN docs d ON d.doc_pk = p.doc_pk "
                    f"WHERE p.term_id IN ({marks}) AND d.matter_id IN (SELECT matter_id FROM vis)"
                    f"{self.field_sql}", params):
                self.post[back[term_id]].setdefault(pk, {})[field] = (tf, positions)
                if pk not in self.lens:
                    self.lens[pk] = {FIELD_TITLE: lt, FIELD_BODY: lb, FIELD_META: lm}

    def allowed(self, filters: dict):
        """doc_pks passing the field filters, or None when there are no filters."""
        if not filters:
            return None
        params = {"uid": self.uid}
        sql = _filter_sql(filters, params)
        return {r[0] for r in self.conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk FROM docs d "
            "JOIN matters m ON m.matter_id = d.matter_id "
            f"WHERE d.matter_id IN (SELECT matter_id FROM vis){sql}", params)}

    def all_visible(self, filters: dict) -> set:
        params = {"uid": self.uid}
        sql = _filter_sql(filters, params)
        return {r[0] for r in self.conn.execute(
            f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk FROM docs d "
            "JOIN matters m ON m.matter_id = d.matter_id "
            f"WHERE d.matter_id IN (SELECT matter_id FROM vis){sql}", params)}

    def _phrase_occ(self, unit) -> dict:
        if unit not in self._phrase:
            parts = unit[1]
            first, rest = parts[0], parts[1:]
            out: dict = {}
            docs = set(self.post.get(first[0], {}))
            for t, _ in rest:
                docs &= set(self.post.get(t, {}))
            for pk in docs:
                counts = {}
                for field, (_, positions) in self.post[first[0]][pk].items():
                    others = []
                    for t, off in rest:
                        entry = self.post[t][pk].get(field)
                        if entry is None:
                            others = None
                            break
                        others.append((off, {int(x) for x in entry[1].split(",")}))
                    if others is None:
                        continue
                    n = sum(1 for x in positions.split(",")
                            if all((int(x) + off) in s for off, s in others))
                    if n:
                        counts[field] = n
                if counts:
                    out[pk] = counts
            self._phrase[unit] = out
        return self._phrase[unit]

    def unit_docs(self, unit) -> dict:
        """doc_pk -> {field: tf} for a term or phrase unit, visible documents only."""
        if unit[0] == "t":
            return {pk: {f: v[0] for f, v in fields.items()}
                    for pk, fields in self.post.get(unit[1], {}).items()}
        return self._phrase_occ(unit)

    def unit_tf(self, unit, pk):
        if unit[0] == "t":
            fields = self.post.get(unit[1], {}).get(pk)
            return {f: v[0] for f, v in fields.items()} if fields else None
        return self._phrase_occ(unit).get(pk)

    def unit_df(self, unit) -> int:
        return self.df.get(unit[1], 0) if unit[0] == "t" else len(self._phrase_occ(unit))

    def idf(self, df: int) -> float:
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def bm25(self, tfs: dict, pk: int, idf: float) -> float:
        wtf = 0.0
        lens = self.lens[pk]
        for f, tf in sorted(tfs.items()):
            wtf += self.w[f] * tf / (1.0 - self.b + self.b * (lens[f] / self.avg[f]))
        return idf * wtf / (self.k1 + wtf)


def _prepare(engine: _Engine, groups: list, config: dict, expand: bool) -> dict:
    """Add corpus-dependent alternatives, then drop everything that does not
    occur in the visible set. Returns notes for the response."""
    conn = engine.conn
    xcfg = config["expansion"]
    weights = xcfg["weights"]
    corrected = []
    if expand:
        for g in groups:
            single = g.get("single")
            if not single or g["quoted"] or len(single) < 4 or not single.isalpha():
                continue
            have = {expand_mod.unit_label(u) for a in g["alts"] for u in a["units"]}
            forms = sorted(r[0] for r in conn.execute(
                "SELECT term FROM terms WHERE root = :r AND term != :t",
                {"r": root(single), "t": single}))
            for form in forms:
                if form not in have:
                    g["alts"].append({"units": [("t", form)], "source": "word form",
                                      "weight": weights["word_form"], "label": form,
                                      "why": f"another form of {single!r}"})
                    have.add(form)
            for variant in sorted(expand_mod.static_variants(single)):
                if variant not in have:
                    g["alts"].append({"units": [("t", variant)], "source": "spelling",
                                      "weight": weights["spelling"], "label": variant,
                                      "why": f"another spelling of {single!r}"})
                    have.add(variant)

    def alt_terms(alt):
        return [t for u in alt["units"] for t in expand_mod.unit_terms(u)]

    engine.load_df([t for g in groups for a in g["alts"] for t in alt_terms(a)])

    if expand:
        tcfg = xcfg["typo"]
        for g in groups:
            single = g.get("single")
            if (not single or g["quoted"] or g["thesaurus"] or len(single) < tcfg["min_length"]
                    or not single.isalpha() or engine.df[single] > 0):
                continue
            if any(all(engine.df[t] > 0 for t in alt_terms(a)) for a in g["alts"][1:]):
                continue  # another form or spelling of the word exists; no need to guess
            limit = tcfg["max_edits_long"] if len(single) >= tcfg["long_from"] else tcfg["max_edits_short"]

            def plausible(term, d):
                # Changing one letter of a short word usually gives a different
                # real word (parent, patent), so that is not treated as a typo.
                if d == 1 and len(term) == len(single) and sorted(term) != sorted(single):
                    return len(single) >= tcfg["substitution_min_length"]
                return True

            near = []
            for (term,) in conn.execute(
                    "SELECT term FROM terms WHERE substr(term, 1, 1) = :c "
                    "AND length(term) BETWEEN :lo AND :hi",
                    {"c": single[0], "lo": len(single) - limit, "hi": len(single) + limit}):
                if term != single and term.isalpha():
                    d = edit_distance(single, term, limit)
                    if d <= limit:
                        near.append((d, term))
            engine.load_df([t for _, t in near])
            # Only spellings that occur in a document this user can open are
            # candidates; the choice among them uses visible counts only.
            live = sorted((d, -engine.df[t], t) for d, t in near
                          if engine.df[t] > 0 and plausible(t, d))
            for d, _, term in live[:tcfg["max_corrections"]]:
                g["alts"].append({"units": [("t", term)], "source": "typo",
                                  "weight": weights["typo"], "label": term,
                                  "why": f"{single!r} is in no document you can open; "
                                         f"{term!r} is {d} letter change{'s' if d > 1 else ''} away"})
                corrected.append({"typed": g["label"], "read_as": term})

    # Keep only alternatives whose every word occurs in the visible set.
    for g in groups:
        g["alts"] = [a for a in g["alts"]
                     if a["source"] == expand_mod.OWN or all(engine.df[t] > 0 for t in alt_terms(a))]
    engine.fetch([t for g in groups for a in g["alts"] for t in alt_terms(a)])

    used, not_found = [], []
    for g in groups:
        own = g["alts"][0]
        own_dfs = [engine.unit_df(u) for u in own["units"]]
        own_idf = None
        if all(d > 0 for d in own_dfs):
            own["idf"] = [engine.idf(d) for d in own_dfs]
            own["df"] = own_dfs
            own_idf = sum(own["idf"])
        live = [own] if own_idf is not None else []
        for alt in g["alts"][1:]:
            dfs = [engine.unit_df(u) for u in alt["units"]]
            if not all(d > 0 for d in dfs):
                continue  # for example a phrase whose words never occur together
            alt["df"] = dfs
            # An alternative never carries more weight than the user's own
            # words would: its rarity is capped at theirs.
            alt["idf"] = [min(engine.idf(d), own_idf) if own_idf is not None else engine.idf(d)
                          for d in dfs]
            live.append(alt)
            used.append({"for": g["label"], "also_searched": alt["label"], "source": alt["source"],
                         "weight": alt["weight"], "why": alt["why"],
                         "documents_you_can_see": min(dfs)})
        g["live"] = live
        g["weight"] = max((sum(a["idf"]) for a in live), default=0.0)
        if not live:
            not_found.append(g["label"])
    return {"used": used, "not_found": not_found, "corrected": corrected}


def _score_doc(engine: _Engine, pk: int, groups: list):
    """Best-alternative score per group for one document."""
    total, covered, rows = 0.0, 0.0, []
    for gi, g in enumerate(groups):
        best = None
        for alt in g["live"]:
            parts = []
            for unit, idf in zip(alt["units"], alt["idf"]):
                tfs = engine.unit_tf(unit, pk)
                if not tfs:
                    parts = None
                    break
                parts.append((unit, idf, tfs, alt["weight"] * engine.bm25(tfs, pk, idf)))
            if parts is None:
                continue
            score = sum(p[3] for p in parts)
            if best is None or score > best[0]:
                best = (score, alt, parts)
        if best is not None:
            total += best[0]
            covered += g["weight"]
            rows.append((gi, best[1], best[2]))
    return total, covered, rows


def _direct_matches(engine: _Engine, groups: list, allowed, require_all: bool,
                    min_coverage: float = 0.0, power: float = 1.0) -> dict:
    live = [g for g in groups if g["live"]]
    if not live:
        return {}
    quoted = {i for i, g in enumerate(live) if g["quoted"]}
    total_weight = sum(g["weight"] for g in live) or 1.0
    pool = set()
    for g in live:
        for alt in g["live"]:
            pool |= set(engine.unit_docs(alt["units"][0]))
    if allowed is not None:
        pool &= allowed
    out = {}
    for pk in pool:
        total, covered, rows = _score_doc(engine, pk, live)
        matched = {gi for gi, _, _ in rows}
        if not quoted <= matched:
            continue
        if require_all and len(matched) != len(live):
            continue
        if not require_all and len(live) > len(quoted) and not (matched - quoted):
            continue
        coverage = covered / total_weight
        if coverage < min_coverage:
            continue
        out[pk] = {"bm25": total, "coverage": coverage, "text": total * coverage ** power,
                   "rows": [(live[gi], alt, parts) for gi, alt, parts in rows], "via": "direct"}
    return out


def _feedback(engine: _Engine, seeds: list, exclude: set, config: dict) -> list:
    """Terms that recur in the user's own top results. Visible documents only."""
    fcfg = config["expansion"]["feedback"]
    need = max(2, math.ceil(fcfg["min_seed_share"] * len(seeds)))
    params = {"uid": engine.uid, "need": need, "ft": FIELD_TITLE, "fb": FIELD_BODY}
    marks = _in_list("s", seeds, params)
    counts = dict(engine.conn.execute(
        f"WITH {acl.VISIBLE_CTE} SELECT t.term, COUNT(DISTINCT p.doc_pk) FROM postings p "
        "JOIN terms t ON t.term_id = p.term_id JOIN docs d ON d.doc_pk = p.doc_pk "
        f"WHERE p.doc_pk IN ({marks}) AND p.field IN (:ft, :fb) "
        "AND d.matter_id IN (SELECT matter_id FROM vis) "
        "GROUP BY t.term HAVING COUNT(DISTINCT p.doc_pk) >= :need", params))
    terms = [t for t in counts if t not in exclude and t not in STOP_WORDS
             and t not in QUERY_FILLER and len(t) >= 3 and t.isalpha()]
    engine.load_df(terms)
    ceiling = fcfg["max_df_share"] * engine.n
    scored = []
    for t in terms:
        df = engine.df[t]
        if df < 2 or df > ceiling:
            continue
        scored.append((-(counts[t] / len(seeds)) * engine.idf(df), t, df, counts[t]))
    scored.sort()
    return [{"term": t, "documents_you_can_see": df, "in_top_results": c}
            for _, t, df, c in scored[:fcfg["terms"]]]


def _related(engine: _Engine, feedback: list, direct: dict, allowed, config: dict) -> dict:
    fcfg = config["expansion"]["feedback"]
    terms = [f["term"] for f in feedback]
    engine.fetch(terms)
    need = min(fcfg["min_terms_matched"], len(terms))
    pool = set()
    for t in terms:
        pool |= set(engine.post[t])
    if allowed is not None:
        pool &= allowed
    out = {}
    for pk in pool - set(direct):
        rows, total = [], 0.0
        for t in terms:
            tfs = engine.unit_tf(("t", t), pk)
            if not tfs:
                continue
            idf = engine.idf(engine.df[t])
            score = fcfg["weight"] * engine.bm25(tfs, pk, idf)
            total += score
            rows.append(({"label": t}, {"source": "related term", "weight": fcfg["weight"],
                                        "label": t, "df": [engine.df[t]],
                                        "why": "recurs in your top results"},
                         [(("t", t), idf, tfs, score)]))
        if len(rows) >= need:
            out[pk] = {"bm25": total, "coverage": 1.0, "text": total, "rows": rows, "via": "related"}
    keep = sorted(out, key=lambda pk: (-out[pk]["text"], pk))  # trimmed again after blending
    return {pk: out[pk] for pk in keep}


def get_document(conn, user_id: str, doc_id: str, config: dict | None = None, now=None):
    """One document by id, or None. The same answer for "does not exist" and
    "exists but you may not open it": the lookup itself is visibility-filtered."""
    config = config or load_config()
    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable:
        return None
    row = conn.execute(
        f"WITH {acl.VISIBLE_CTE} SELECT d.doc_pk FROM docs d "
        "WHERE d.doc_id = :doc_id AND d.matter_id IN (SELECT matter_id FROM vis)",
        {"uid": user_id, "doc_id": doc_id}).fetchone()
    if row is None:
        return None
    doc = _load_docs(conn, user_id, [row[0]]).get(row[0])
    if doc is None:
        return None
    return {k: doc[k] for k in ("doc_id", "title", "body", "doc_type", "date", "matter_id",
                                "matter_name", "practice", "matter_type", "jurisdiction",
                                "client_industry", "office", "author_id", "author_name",
                                "version_no", "is_final", "was_filed", "model_form",
                                "reuse_count")}


def search(conn, user_id: str, query: str = "", filters: dict | None = None,
           config: dict | None = None, limit: int = 10, offset: int = 0, explain: bool = False,
           as_of=None, reranker=None, now=None, expand: bool | None = None) -> dict:
    """Run one query as one user. Returns a plain dict ready for JSON.

    ``expand`` False switches vocabulary bridging off for this query."""
    config = config or load_config()
    xcfg = config["expansion"]
    expand = bool(xcfg["enabled"]) if expand is None else bool(expand) and bool(xcfg["enabled"])
    parsed = parse_query(query)
    merged = dict(parsed["filters"])
    merged.update(filters or {})
    flt = normalise_filters(merged)

    try:
        acl.assert_usable(conn, now=now, max_age_hours=config.get("acl_max_age_hours"))
    except acl.PermissionDataUnavailable as exc:
        return _empty(user_id, query, flt, "unavailable", f"Search is unavailable: {exc}.")
    if not acl.user_can_search(conn, user_id):
        return _empty(user_id, query, flt, "denied",
                      "This user is not an active person in the permission data.")
    groups = expand_mod.build_groups(parsed, config, expand)
    if not groups and not flt:
        return _empty(user_id, query, flt, "ok", "Enter a search term or choose a filter.")

    engine = _Engine(conn, user_id, config)
    notes = {"used": [], "not_found": [], "corrected": []}
    related_terms: list = []
    relaxed = False
    mode = config.get("match_mode", "all")
    if engine.n == 0:
        candidates = {}
    elif not groups:
        candidates = {pk: {"bm25": 0.0, "coverage": 1.0, "text": 0.0, "rows": [], "via": "direct"}
                      for pk in engine.all_visible(flt)}
    else:
        notes = _prepare(engine, groups, config, expand)
        # A run of words read as one thesaurus phrase ("parent company
        # guarantee") may match nothing the user can open, as a phrase or
        # through its equivalents. Then read the words separately instead.
        max_span: dict = {}
        for _ in range(8):
            dead = [g for g in groups if not g["quoted"] and g.get("span", 1) > 1 and not g["live"]]
            if not dead:
                break
            for g in dead:
                max_span[g["pos"]] = g["span"] - 1
            groups = expand_mod.build_groups(parsed, config, expand, max_span=max_span)
            notes = _prepare(engine, groups, config, expand)
        allowed = engine.allowed(flt)
        mode = config.get("match_mode", "all")
        require_all = mode == "all"
        weighted = config.get("weighted_match", {})
        live = [g for g in groups if g["live"]]
        # A quoted phrase is a requirement. If it occurs nowhere the user can
        # see, nothing matches; it is never dropped like a loose word.
        phrase_missing = any(g["quoted"] and not g["live"] for g in groups)
        if phrase_missing:
            candidates = {}
        elif mode == "weighted":
            candidates = _direct_matches(engine, groups, allowed, False,
                                         float(weighted.get("min_share_of_query", 0.5)),
                                         float(weighted.get("power", 2.0)))
            # "relaxed" here means: nothing matches the whole query.
            relaxed = bool(candidates) and len(live) > 1 and all(
                c["coverage"] < 0.999 for c in candidates.values())
        else:
            candidates = _direct_matches(engine, groups, allowed, require_all)
        if (not candidates and require_all and not phrase_missing and len(live) > 1
                and config.get("relax_to_any_when_empty")):
            candidates = _direct_matches(engine, groups, allowed, False)
            relaxed = bool(candidates)
        fcfg = xcfg["feedback"]
        if (expand and fcfg["enabled"] and candidates
                and len(candidates) < fcfg["run_when_direct_results_below"]):
            ranked = sorted(candidates, key=lambda pk: (-candidates[pk]["text"], pk))
            seeds = [pk for pk in ranked
                     if candidates[pk]["coverage"] >= fcfg["seed_min_coverage"]][:fcfg["seed_documents"]]
            if len(seeds) >= fcfg["min_seeds"]:
                exclude = {t for g in groups for a in g["alts"] for u in a["units"]
                           for t in expand_mod.unit_terms(u)}
                related_terms = _feedback(engine, seeds, exclude, config)
                if related_terms:
                    candidates.update(_related(engine, related_terms, candidates, allowed, config))

    docs = _load_docs(conn, user_id, list(candidates))
    blend = config["blend"]
    when = _as_of(config, as_of)
    max_text = max((c["text"] for pk, c in candidates.items()
                    if pk in docs and c["via"] == "direct"), default=0.0)
    reuse_cap = max(1, int(config.get("reuse_cap", 20)))
    scored = []
    for pk, cand in candidates.items():
        doc = docs.get(pk)
        if doc is None:
            continue
        text_value = min(1.0, cand["text"] / max_text) if max_text > 0 else 0.0
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
    # Direct matches always come before documents found only through related terms.
    scored.sort(key=lambda r: (r["cand"]["via"] != "direct", -round(r["score"], 9),
                               r["doc"]["doc_id"]))
    max_related = int(xcfg["feedback"]["max_related"])
    trimmed, n_related = [], 0
    for r in scored:
        if r["cand"]["via"] == "related":
            n_related += 1
            if n_related > max_related:
                continue
        trimmed.append(r)
    scored = trimmed

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
        if keep["cand"]["via"] == "related" and any(m["cand"]["via"] == "direct" for m in members):
            keep = max((m for m in members if m["cand"]["via"] == "direct"),
                       key=lambda r: (r["doc"]["is_final"], r["doc"]["version_no"],
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
    kept = []
    for r in reps:
        target = None
        for other in kept:
            if other["pk"] in neighbours.get(r["pk"], ()):
                target = other
                break
        if target is None:
            kept.append(r)
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

    results = []
    page = kept[offset:offset + limit]
    for rank, r in enumerate(page, start=offset + 1):
        doc = r["doc"]
        wanted = {t for _, _, parts in r["cand"]["rows"] for unit, _, _, _ in parts
                  for t in expand_mod.unit_terms(unit)}
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
            "share_of_query_matched": round(r["cand"]["coverage"], 3),
            "found_by": ("related terms" if r["cand"]["via"] == "related" else
                         ("equivalent terms" if any(alt["source"] != expand_mod.OWN
                                                    for _, alt, _ in r["cand"]["rows"])
                          else "your words")),
            "snippet": _snippet(doc["body"], wanted, int(config.get("snippet_words", 30))),
            "other_versions": r.get("other_versions", []),
            "near_duplicates": r.get("near_duplicates", []),
        }
        if explain:
            item["explain"] = _explain(r, engine, blend, max_text, reranked)
        results.append(item)

    messages = []
    if notes["corrected"]:
        messages.append("; ".join(f"read {c['typed']!r} as {c['read_as']!r}"
                                  for c in notes["corrected"]).capitalize() + ".")
    if notes["not_found"]:
        messages.append("No document you can open contains: " + ", ".join(notes["not_found"]) + ".")
        found = [g["label"] for g in groups if g.get("live")]
        if kept and len(notes["not_found"]) >= len(found):
            messages.append("These results match only: " + ", ".join(found)
                            + ". Try other words for the rest.")
    if relaxed:
        messages.append("No document has every term. Showing documents that match most of the query."
                        if mode == "weighted" else
                        "No document has every term. Showing documents that match some of them.")
    elif not kept:
        messages.append("Nothing found among the documents you can open.")
    return {"user": user_id, "query": query, "filters": flt, "access": "ok",
            "message": " ".join(messages), "relaxed": relaxed, "reranked": reranked,
            "total": len(kept), "offset": offset, "results": results, "facets": facets,
            "expansion": {"on": expand, "used": notes["used"], "not_found": notes["not_found"],
                          "corrected": notes["corrected"], "related_terms": related_terms}}


def _explain(r: dict, engine: _Engine, blend: dict, max_text: float, reranked: bool) -> dict:
    terms = []
    for group, alt, parts in r["cand"]["rows"]:
        for unit, idf, tfs, score in parts:
            row = {
                "term": expand_mod.unit_label(unit),
                "matched_in": {FIELD_NAMES[f]: tf for f, tf in sorted(tfs.items())},
                "documents_you_can_see_with_term": engine.unit_df(unit),
                "idf": round(idf, 4),
                "bm25": round(score, 4),
                "source": alt["source"],
                "weight": alt["weight"],
            }
            if alt["source"] != expand_mod.OWN:
                row["for_your_words"] = group["label"]
                row["why"] = alt["why"]
            terms.append(row)
    signals = [{"signal": name, "value": round(value, 4), "weight": blend[name],
                "contribution": round(blend[name] * value, 4)} for name, value in r["signals"]]
    out = {
        "text": {"bm25": round(r["cand"]["bm25"], 4),
                 "share_of_query_matched": round(r["cand"]["coverage"], 4),
                 "best_bm25_in_your_results": round(max_text, 4),
                 "value": round(r["text_value"], 4), "weight": blend["text"],
                 "contribution": round(blend["text"] * r["text_value"], 4), "terms": terms},
        "signals": signals,
        "total": round(r["score"], 6),
        "statistics_scope": f"{engine.n} documents you can open",
    }
    if r["cand"]["via"] == "related":
        out["note"] = ("Does not contain your words. Listed after the direct matches because it "
                       "shares terms that recur in your top results.")
    if reranked and "rerank_score" in r:
        out["rerank_score"] = r["rerank_score"]
    return out


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
