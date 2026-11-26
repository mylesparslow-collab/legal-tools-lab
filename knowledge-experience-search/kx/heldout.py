"""Score the tool against a held-out batch (heldout/README.md has the rules).

The relevance lists are hand-judged samples, capped at ten, so:

* strict precision at 5 counts a result only if it is listed as relevant;
* lenient precision at 5 also counts documents the author marked as on the
  same subject but did not list;
* "hit in top 10" is whether any listed document appears in the first ten;
* everything else is unjudged, not wrong. No recall is computed.

Results and listed documents are both mapped through the answer key's
``equivalents`` (drafts and adapted copies of one document count as one).
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from kx import experience, search
from kx.config import DEFAULT_CONFIG_PATH, load_config
from kx.expand import DEFAULT_THESAURUS_PATH


def _fingerprint() -> dict:
    out = {}
    for name, path in (("ranking_config", DEFAULT_CONFIG_PATH), ("thesaurus", DEFAULT_THESAURUS_PATH)):
        out[name + "_sha256"] = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    return out


def _mean(values):
    values = list(values)
    return round(sum(values) / len(values), 3) if values else None


def run(conn, batch_dir, equivalents: dict, as_of: str, config=None, expand=None) -> dict:
    config = config or load_config()
    with open(Path(batch_dir) / "ANSWER_KEY.json", encoding="utf-8") as fh:
        key = json.load(fh)
    unit = lambda doc_id: equivalents.get(doc_id, doc_id)
    rows = []
    for q in key["queries"]:
        result = search.search(conn, q["as_user"], q["query"], config=config, limit=10,
                               as_of=as_of, expand=expand)
        units = []
        for r in result["results"]:
            if unit(r["doc_id"]) not in units:
                units.append(unit(r["doc_id"]))
        listed = {unit(d) for d in q["relevant"]}
        same_topic = listed | {unit(d) for d in q.get("same_topic_not_listed", [])}
        kind = ("different words" if q["category"] == "different vocabulary"
                else "documents' own words")
        rows.append({
            "id": q["id"], "kind": kind, "category": q["category"],
            "variation": q.get("variation", ""), "query": q["query"],
            "returned": result["total"],
            "strict_precision_at_5": round(sum(1 for u in units[:5] if u in listed) / 5, 3),
            "lenient_precision_at_5": round(sum(1 for u in units[:5] if u in same_topic) / 5, 3),
            "listed_document_in_top_10": any(u in listed for u in units[:10]),
            "first_listed_rank": next((i + 1 for i, u in enumerate(units) if u in listed), None),
            "expansions_used": [f"{u['for']} -> {u['also_searched']} ({u['source']})"
                                for u in result["expansion"]["used"]],
            "not_found": result["expansion"]["not_found"],
            "corrected": result["expansion"]["corrected"],
            "top_5": [r["doc_id"] for r in result["results"][:5]],
        })

    def summarise(items):
        items = list(items)
        return {"queries": len(items),
                "strict_precision_at_5": _mean(r["strict_precision_at_5"] for r in items),
                "lenient_precision_at_5": _mean(r["lenient_precision_at_5"] for r in items),
                "share_with_a_listed_document_in_top_10":
                    _mean(1.0 if r["listed_document_in_top_10"] else 0.0 for r in items),
                "queries_with_a_listed_document_in_top_10":
                    sum(1 for r in items if r["listed_document_in_top_10"])}

    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)

    who_rows = []
    for q in key.get("experience_queries", []):
        result = experience.who(conn, q["as_user"], q["query"], config=config, as_of=as_of,
                                limit=10, expand=expand)
        ranked = [p["person_id"] for p in result["people"] if p["rank"]]
        ids = lambda name: [(p.get("user_id") or p.get("person_id")) if isinstance(p, dict) else p
                            for p in q.get(name, [])]
        strongest, near = ids("strongest"), ids("should_rank_near_top")
        expected = strongest + [p for p in near if p not in strongest]
        who_rows.append({
            "id": q.get("id", ""), "query": q["query"], "variation": q.get("variation", ""),
            "matters_matched": result["matters_matched"], "message": result["message"],
            "every_strongest_in_top_3": bool(strongest) and all(p in ranked[:3] for p in strongest),
            "expected_in_top_5": sum(1 for p in expected if p in ranked[:5]),
            "expected": len(expected), "top_5": ranked[:5],
        })
    who_summary = {
        "queries": len(who_rows),
        "queries_with_every_strongest_person_in_top_3":
            sum(1 for r in who_rows if r["every_strongest_in_top_3"]),
        "expected_people_in_top_5": sum(r["expected_in_top_5"] for r in who_rows),
        "expected_people": sum(r["expected"] for r in who_rows),
    }
    return {
        "batch": Path(batch_dir).name, "expansion": "off" if expand is False else "on",
        "scoring": "strict = listed as relevant; lenient = listed or marked same topic; "
                   "other results are unjudged; no recall",
        "tool_state": _fingerprint(),
        "document_queries": {"all": summarise(rows),
                             **{k: summarise(v) for k, v in sorted(by_kind.items())}},
        "who_has_done_this": who_summary,
        "per_query": rows, "per_who_query": who_rows,
    }
