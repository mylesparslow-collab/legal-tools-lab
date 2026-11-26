"""Command line: python -m kx generate|index|search|who|suggest|audit|eval|serve"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kx import audit as audit_mod
from kx import config as cfg
from kx import index as index_mod


def _add_common(p):
    p.add_argument("--db", default=str(cfg.DEFAULT_DB_PATH), help="index database file")
    p.add_argument("--log", default=str(cfg.DEFAULT_AUDIT_PATH), help="audit log file")
    p.add_argument("--config", default=str(cfg.DEFAULT_CONFIG_PATH), help="ranking config")


def _service(args, as_of=None):
    from kx.service import Service
    if not Path(args.db).exists():
        sys.exit(f"No index at {args.db}. Run: python -m kx index")
    return Service(args.db, args.log, cfg.load_config(args.config), as_of=as_of)


def _filters(pairs):
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            sys.exit(f"--filter needs key=value, not {pair!r}")
        k, v = pair.split("=", 1)
        out[k] = v
    return out


def print_search(result, show_explain=False, out=None):
    w = (out or sys.stdout).write
    w(f"Query: {result['query']!r} as {result['user']}\n")
    if result["access"] != "ok":
        w(f"{result['message']}\n")
        return
    if result["message"]:
        w(result["message"] + "\n")
    w(f"{result['total']} result{'s' if result['total'] != 1 else ''} among documents this user can open\n")
    x = result.get("expansion") or {}
    for u in x.get("used", []):
        w(f"  also searched {u['also_searched']!r} for {u['for']!r} "
          f"({u['source']}, weight {u['weight']}; {u['why']})\n")
    if x.get("related_terms"):
        w("  few direct matches; related terms from your top results: "
          + ", ".join(t["term"] for t in x["related_terms"]) + "\n")
    if x and not x.get("on"):
        w("  expansion off: your exact words only\n")
    for r in result["results"]:
        flags = [f for f, on in (("model form", r["model_form"]), ("final", r["is_final"]),
                                 ("filed", r["was_filed"])) if on]
        if not r["is_final"]:
            flags.append(f"draft v{r['version_no']}")
        if r["reuse_count"]:
            flags.append(f"reused {r['reuse_count']}x")
        via = "" if r.get("found_by", "your words") == "your words" else f"  (found by {r['found_by']})"
        if r.get("share_of_query_matched", 1.0) < 0.999 and r.get("found_by") != "related terms":
            via += "  (matches part of the query)"
        w(f"\n{r['rank']:>2}. {r['title']}  [{r['doc_id']}]  score {r['score']:.3f}{via}\n")
        w(f"    {r['doc_type']} | {r['practice']} | {r['matter_type']} | {r['jurisdiction']} | {r['date']}\n")
        author = r["author"]["name"] + (" (left the firm)" if r["author"]["departed"] else "")
        w(f"    matter {r['matter_id']} {r['matter_name']} | author {author}\n")
        if flags:
            w(f"    {', '.join(flags)}\n")
        if r["other_versions"]:
            w(f"    {len(r['other_versions'])} earlier or other version(s) folded in: "
              f"{', '.join(v['doc_id'] for v in r['other_versions'])}\n")
        if r["near_duplicates"]:
            w(f"    {len(r['near_duplicates'])} near-duplicate(s) folded in: "
              f"{', '.join(v['doc_id'] for v in r['near_duplicates'])}\n")
        if r["snippet"]["text"]:
            w(f"    {' '.join(r['snippet']['text'].split())}\n")
        if show_explain and "explain" in r:
            e = r["explain"]
            w(f"    why: text {e['text']['contribution']:.3f} "
              f"(bm25 {e['text']['bm25']} / best {e['text']['best_bm25_in_your_results']}, "
              f"weight {e['text']['weight']}; statistics over {e['statistics_scope']})\n")
            for t in e["text"]["terms"]:
                where = ", ".join(f"{k} x{v}" for k, v in t["matched_in"].items())
                src = "" if t["source"] == "your words" else (
                    f" [{t['source']} for {t['for_your_words']!r}, weight {t['weight']}: {t['why']}]")
                w(f"         term {t['term']!r}{src}: {where}; in {t['documents_you_can_see_with_term']} "
                  f"visible documents; bm25 {t['bm25']}\n")
            for s in e["signals"]:
                w(f"         {s['signal']}: value {s['value']} x weight {s['weight']} = {s['contribution']}\n")
    if result["total"]:
        w("\nFilters available in these results:\n")
        for field, values in result["facets"].items():
            if values:
                w(f"  {field}: " + ", ".join(f"{v['value']} ({v['count']})" for v in values[:6]) + "\n")


def print_who(result, out=None):
    w = (out or sys.stdout).write
    w(f"Who has done: {result['query']!r} as {result['user']}\n")
    if result["access"] != "ok":
        w(result["message"] + "\n")
        return
    if result["message"]:
        w(result["message"] + "\n")
    w(f"{result['matters_matched']} matching matter(s) this user can open\n")
    for p in result["people"]:
        rank = f"{p['rank']:>2}." if p["rank"] else " - "
        w(f"\n{rank} {p['name']}  [{p['person_id']}]  {p['title']}, {p['practice']}, {p['office']}\n")
        if p["departed"]:
            w(f"    {p['status_note']}\n")
        w(f"    {p['matters']} matter(s), {p['lead_matters']} as lead, {p['hours']} hours, "
          f"last activity {p['last_activity']}, score {p['score']}\n")
        if p["evidence_level"] == "thin":
            w(f"    thin evidence: {p['evidence_note']}\n")
        for e in p["evidence"][:5]:
            w(f"      {e['matter_id']} {e['matter_name']} | {e['matter_type']} | {e['role']} | "
              f"{e['hours']}h | {e['last_activity']} | matched on {e['matched_on']}\n")
        if len(p["evidence"]) > 5:
            w(f"      and {len(p['evidence']) - 5} more\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m kx", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("generate", help="write the synthetic corpus")
    p.add_argument("--out", default=str(cfg.DEFAULT_DATA_DIR))
    p.add_argument("--seed", type=int, default=None)

    p = sub.add_parser("index", help="build or update the index from a source")
    _add_common(p)
    p.add_argument("--data", default=str(cfg.DEFAULT_DATA_DIR))
    p.add_argument("--mapping", default=str(cfg.DEFAULT_MAPPING_PATH))
    p.add_argument("--full", action="store_true", help="re-read everything and remove what the source no longer has")
    p.add_argument("--permissions-only", action="store_true", help="refresh people, groups, grants and walls only")

    for name, help_text in (("search", "find documents"), ("who", "find people who have done this work")):
        p = sub.add_parser(name, help=help_text)
        _add_common(p)
        p.add_argument("--user", required=True,
                       help="person id the query runs as (operator tool; the web UI uses a session)")
        p.add_argument("--filter", action="append", metavar="key=value")
        p.add_argument("--limit", type=int, default=10)
        p.add_argument("--as-of", default=None, help="date used for recency, YYYY-MM-DD")
        p.add_argument("--json", action="store_true")
        p.add_argument("--no-expand", action="store_true",
                       help="search the exact words only: no thesaurus, word forms, typo or related terms")
        if name == "search":
            p.add_argument("--explain", action="store_true")
        p.add_argument("query", nargs="*")

    p = sub.add_parser("suggest", help="complete a word from documents the user can open")
    _add_common(p)
    p.add_argument("--user", required=True)
    p.add_argument("prefix")

    p = sub.add_parser("audit", help="verify the query log or report on it")
    _add_common(p)
    p.add_argument("what", choices=["verify", "report", "tail"])
    p.add_argument("-n", type=int, default=10)

    p = sub.add_parser("eval", help="score search against the synthetic answer key")
    _add_common(p)
    p.add_argument("--data", default=str(cfg.DEFAULT_DATA_DIR))
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("timing", help="time queries with expansion on and off")
    _add_common(p)
    p.add_argument("--data", default=str(cfg.DEFAULT_DATA_DIR))

    p = sub.add_parser("heldout", help="score a held-out batch (see heldout/README.md)")
    _add_common(p)
    p.add_argument("--data", default=str(cfg.DEFAULT_DATA_DIR))
    p.add_argument("--batch", required=True, help="folder holding ANSWER_KEY.json")
    p.add_argument("--out", required=True, help="file to write; refused if it already exists")
    p.add_argument("--no-expand", action="store_true")

    p = sub.add_parser("serve", help="local web UI on 127.0.0.1")
    _add_common(p)
    p.add_argument("--data", default=str(cfg.DEFAULT_DATA_DIR))
    p.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    if args.command == "generate":
        from synth.generate import SEED, generate
        manifest = generate(args.out, args.seed if args.seed is not None else SEED)
        print(json.dumps(manifest["counts"], indent=1))
        return 0

    if args.command == "index":
        from sources.synthetic_files import SyntheticFileAdapter
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        conn = index_mod.connect(args.db)
        indexer = index_mod.Indexer(
            conn, near_dup_threshold=cfg.load_config(args.config)["near_duplicate_threshold"])
        adapter = SyntheticFileAdapter(args.data, args.mapping)
        if args.permissions_only:
            report = indexer.sync_permissions(adapter)
        else:
            report = indexer.sync(adapter, full=args.full)
        report["index"] = indexer.stats()
        print(json.dumps(report, indent=1))
        return 0

    if args.command in ("search", "who"):
        from kx.search import QueryError
        service = _service(args, as_of=args.as_of)
        query = " ".join(args.query)
        try:
            if args.command == "search":
                result = service.search(args.user, query, _filters(args.filter),
                                        limit=args.limit, explain=args.explain,
                                        expand=False if args.no_expand else None)
            else:
                result = service.who(args.user, query, _filters(args.filter), limit=args.limit,
                                     expand=False if args.no_expand else None)
        except QueryError as exc:
            sys.exit(f"Could not run that query: {exc}")
        if args.json:
            print(json.dumps(result, indent=1, ensure_ascii=False))
        elif args.command == "search":
            print_search(result, show_explain=args.explain)
        else:
            print_who(result)
        return 0

    if args.command == "suggest":
        print("\n".join(_service(args).suggest(args.user, args.prefix)))
        return 0

    if args.command == "audit":
        if args.what == "verify":
            result = audit_mod.verify(args.log)
            print(json.dumps(result, indent=1))
            return 0 if result["ok"] else 1
        entries = audit_mod.read_entries(args.log)
        if args.what == "tail":
            for e in entries[-args.n:]:
                print(f"{e['seq']:>5} {e['time']} {e['user']} {e['action']:<6} "
                      f"{e['result_count']:>3} results  {e['query']!r} {e['filters'] or ''}")
            return 0
        print(audit_mod.format_zero_result_report(audit_mod.zero_result_report(entries)), end="")
        return 0

    if args.command == "eval":
        from kx import evaluate
        if not Path(args.db).exists():
            sys.exit(f"No index at {args.db}. Run: python -m kx index")
        conn = index_mod.connect(args.db, readonly=True)
        report = evaluate.evaluate(conn, evaluate.load_key(args.data), cfg.load_config(args.config))
        if args.json:
            print(json.dumps(report, indent=1))
        else:
            print(json.dumps({k: v for k, v in report.items() if k != "per_query"}, indent=1))
        return 0

    if args.command == "timing":
        from kx import evaluate
        conn = index_mod.connect(args.db, readonly=True)
        print(json.dumps(evaluate.timing(conn, evaluate.load_key(args.data),
                                         cfg.load_config(args.config)), indent=1))
        return 0

    if args.command == "heldout":
        from kx import evaluate, heldout
        if Path(args.out).exists():
            sys.exit(f"{args.out} already exists. A recorded run is not overwritten.")
        conn = index_mod.connect(args.db, readonly=True)
        key = evaluate.load_key(args.data)
        report = heldout.run(conn, args.batch, key["equivalents"], key["as_of"],
                             cfg.load_config(args.config), expand=False if args.no_expand else None)
        Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("batch", "expansion", "tool_state",
                                                 "document_queries", "who_has_done_this")}, indent=1))
        return 0

    if args.command == "serve":
        from kx.server import serve
        serve(_service(args), args.data, args.port)
        return 0
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # output piped into something that stopped reading
        sys.stderr.close()
        sys.exit(0)
