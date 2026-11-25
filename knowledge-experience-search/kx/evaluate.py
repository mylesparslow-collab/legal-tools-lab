"""Score search against the generator's answer key.

Precision at 5: of the first five results, the share that are relevant.
Recall at 10: of the relevant documents, the share found in the first ten.
A draft or adapted copy counts as its final or original, once.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from kx import search
from kx.config import load_config


def load_key(data_dir) -> dict:
    with open(Path(data_dir) / "ANSWER_KEY.json", encoding="utf-8") as fh:
        return json.load(fh)


def _units(result, equivalents) -> list:
    seen, out = set(), []
    for r in result["results"]:
        unit = equivalents.get(r["doc_id"], r["doc_id"])
        if unit not in seen:
            seen.add(unit)
            out.append(unit)
    return out


def evaluate(conn, key: dict, config=None) -> dict:
    config = config or load_config()
    eq = key["equivalents"]
    per_query = []
    for q in key["queries"]:
        result = search.search(conn, q["as_user"], q["query"], config=config, limit=10,
                               as_of=key["as_of"])
        units = _units(result, eq)
        relevant = set(q["relevant"])
        p5 = sum(1 for u in units[:5] if u in relevant) / 5
        r10 = sum(1 for u in units[:10] if u in relevant) / len(relevant) if relevant else 0.0
        row = {"id": q["id"], "category": q["category"], "query": q["query"],
               "relevant": len(relevant), "returned": result["total"],
               "relaxed": result["relaxed"], "precision_at_5": round(p5, 3),
               "recall_at_10": round(r10, 3)}
        if "best" in q:
            row["best_rank"] = units.index(q["best"]) + 1 if q["best"] in units else None
        per_query.append(row)

    def summarise(rows):
        n = len(rows)
        out = {"queries": n,
               "precision_at_5": round(sum(r["precision_at_5"] for r in rows) / n, 3),
               "recall_at_10": round(sum(r["recall_at_10"] for r in rows) / n, 3)}
        best = [r for r in rows if "best_rank" in r]
        if best:
            out["best_example_ranked_first"] = sum(1 for r in best if r["best_rank"] == 1)
            out["best_example_in_top_3"] = sum(1 for r in best if r["best_rank"] and r["best_rank"] <= 3)
            out["best_example_queries"] = len(best)
        return out

    by_category = defaultdict(list)
    for r in per_query:
        by_category[r["category"]].append(r)
    same_words = [r for r in per_query if r["category"] != "different vocabulary"]

    leaks = []
    checks = 0
    for group in ("wall_tests", "restricted_tests"):
        for t in key[group]:
            hidden = set(t["must_never_appear"])
            for user in t["denied_users"]:
                for query in t["queries"]:
                    checks += 1
                    result = search.search(conn, user, query, config=config, limit=1000,
                                           as_of=key["as_of"])
                    shown = set()
                    for r in result["results"]:
                        shown.add(r["doc_id"])
                        shown.update(v["doc_id"] for v in r["other_versions"])
                        shown.update(v["doc_id"] for v in r["near_duplicates"])
                    bad = sorted(shown & hidden)
                    if bad:
                        leaks.append({"test": t["id"], "user": user, "query": query, "leaked": bad})
    return {
        "all_queries": summarise(per_query),
        "queries_using_the_corpus_vocabulary": summarise(same_words),
        "by_category": {c: summarise(rows) for c, rows in sorted(by_category.items())},
        "permission_checks": {"checks_run": checks, "leaks": leaks},
        "per_query": per_query,
    }
