"""One-command demo: python run_demo.py [--serve]

Generates the synthetic corpus if it is missing, builds the index, and writes
sample outputs into output/. Everything is seeded and uses fixed clocks, so
running it again reproduces the same files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from kx import audit, config as cfg, evaluate, experience, index, search  # noqa: E402
from kx.__main__ import print_search, print_who  # noqa: E402
from kx.schema import PermissionSnapshot, Wall  # noqa: E402
from kx.server import PRESETS, page_html  # noqa: E402
from kx.service import Service  # noqa: E402
from sources.synthetic_files import SyntheticFileAdapter  # noqa: E402

OUT = ROOT / "output"
DATA = cfg.DEFAULT_DATA_DIR
DB = cfg.DEFAULT_DB_PATH


class FixedClock:
    """Deterministic timestamps: one minute per call from a fixed start."""

    def __init__(self, start="2026-06-30T09:00:00+00:00"):
        self.now = dt.datetime.fromisoformat(start)

    def __call__(self):
        self.now += dt.timedelta(minutes=1)
        return self.now


class WithExtraWall(SyntheticFileAdapter):
    """The same source with one more wall, to show a permission change."""

    def __init__(self, *args, extra_wall: Wall, **kwargs):
        super().__init__(*args, **kwargs)
        self.extra_wall = extra_wall

    def permissions(self):
        snap = super().permissions()
        return PermissionSnapshot(snap.group_members, snap.grants, snap.walls + (self.extra_wall,))


def write(name: str, text: str):
    (OUT / name).write_text(text, encoding="utf-8")
    print(f"  wrote output/{name}")


def text_of(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    fn(*args, out=buf, **kwargs)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="start the local web UI afterwards")
    parser.add_argument("--regenerate", action="store_true", help="rewrite the synthetic corpus")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    if args.regenerate or not (DATA / "documents.jsonl").exists():
        from synth.generate import generate
        print("Generating synthetic corpus")
        generate(DATA)
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    key = evaluate.load_key(DATA)
    as_of = manifest["as_of"]
    config = cfg.load_config()

    print("Building index")
    DB.parent.mkdir(parents=True, exist_ok=True)
    for stale in DB.parent.glob("*.sqlite*"):
        stale.unlink()
    conn = index.connect(DB)
    indexer = index.Indexer(conn, config["near_duplicate_threshold"], clock=FixedClock())
    adapter = SyntheticFileAdapter(DATA, cfg.DEFAULT_MAPPING_PATH)
    report = indexer.sync(adapter, full=True)
    report["source"] = "synthetic files in data/synthetic"
    report["index"] = indexer.stats()
    write("index_report.json", json.dumps(report, indent=1) + "\n")

    demo = manifest["demo_users"]
    newcomer, walled, lead, walled2, departed = (u["person_id"] for u in demo)
    w1 = manifest["walls"]["W1"]
    codename = w1["codenames"][0]

    # 1. Same query, different users.
    parts = ["Same query, different users\n===========================\n",
             "The matter behind wall W1 is Project " + codename + ". The second user is excluded "
             "by that wall.\nNothing in that user's output mentions the matter: no result, no count, "
             "no filter value.\n"]
    for query in (f"project {codename.lower()}", "earn-out provisions memo"):
        for u in demo:
            parts.append(f"\n--- {u['label']} ({u['name']}, {u['person_id']}) ---\n")
            parts.append(text_of(print_search, search.search(conn, u["person_id"], query,
                                                             config=config, limit=3, as_of=as_of)))
    write("same_query_different_users.txt", "".join(parts))

    # 2. Explain.
    result = search.search(conn, newcomer, "indemnification cap and basket agreement",
                           config=config, limit=3, explain=True, as_of=as_of)
    write("search_explain_example.txt", text_of(print_search, result, show_explain=True))
    write("search_explain_example.json", json.dumps(result, indent=1, ensure_ascii=False) + "\n")

    # 2b. Different wording: the same query with and without vocabulary bridging.
    wording = "deferred price contingent on future performance agreement"
    parts = ["Different wording\n=================\n",
             "No document uses the words \"deferred price\". With bridging on, the thesaurus reads them\n"
             "as \"deferred consideration\" and searches its listed equivalents at a lower weight.\n"
             "Every alternative shown is one that occurs in a document this user can open.\n",
             "\n--- bridging on (default) ---\n",
             text_of(print_search, search.search(conn, newcomer, wording, config=config, limit=3,
                                                 explain=True, as_of=as_of), show_explain=True),
             "\n--- bridging off (python -m kx search --no-expand, or the tick box in the page) ---\n",
             text_of(print_search, search.search(conn, newcomer, wording, config=config, limit=3,
                                                 as_of=as_of, expand=False)),
             "\n--- a misspelling ---\n",
             text_of(print_search, search.search(conn, newcomer, "indemnifcation basket memo",
                                                 config=config, limit=2, as_of=as_of))]
    write("different_wording_example.txt", "".join(parts))

    # 3. Experience finder.
    parts = []
    for user, query in ((newcomer, "loan workout"), (newcomer, "zoning entitlement"),
                        (newcomer, "charitable planning"),
                        (lead, f"project {codename.lower()}"), (walled, f"project {codename.lower()}")):
        parts.append(text_of(print_who, experience.who(conn, user, query, config=config,
                                                       as_of=as_of, limit=4)))
        parts.append("\n" + "-" * 60 + "\n")
    write("who_has_done_this.txt", "".join(parts))

    # 4. A wall goes up: permissions-only sync on a copy of the index.
    conn.commit()
    copy_path = DB.parent / "wall_demo.sqlite"
    shutil.copyfile(DB, copy_path)
    conn2 = index.connect(copy_path)
    indexer2 = index.Indexer(conn2, clock=FixedClock("2026-06-30T12:00:00+00:00"))
    probe = "earn-out provisions agreement"
    before = search.search(conn2, newcomer, probe, config=config, limit=5, as_of=as_of)
    target_matter = before["results"][0]["matter_id"]
    postings_before = conn2.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    indexer2.sync_permissions(WithExtraWall(
        DATA, cfg.DEFAULT_MAPPING_PATH,
        extra_wall=Wall("W-DEMO", (target_matter,), (newcomer,))))
    after = search.search(conn2, newcomer, probe, config=config, limit=5, as_of=as_of)
    postings_after = conn2.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    text = ("A wall goes up\n==============\n"
            f"Query {probe!r} as {newcomer}.\n"
            f"Before: {before['total']} results; top result is in matter {target_matter}.\n"
            f"Then a new wall excludes {newcomer} from {target_matter}. Only the permission "
            "tables are refreshed (python -m kx index --permissions-only does the same).\n"
            f"After: {after['total']} results; documents from {target_matter} shown: "
            f"{sum(1 for r in after['results'] if r['matter_id'] == target_matter)}.\n"
            f"Postings before and after: {postings_before} and {postings_after} "
            "(no document was re-indexed).\n\nBefore\n------\n"
            + text_of(print_search, before) + "\nAfter\n-----\n" + text_of(print_search, after))
    write("wall_goes_up.txt", text)
    conn2.close()
    copy_path.unlink()

    # 5. Retrieval quality against the answer key.
    quality = evaluate.evaluate(conn, key, config)
    write("retrieval_quality.json", json.dumps(quality, indent=1) + "\n")
    keyword_only = evaluate.evaluate(conn, key, config, expand=False)
    write("retrieval_quality_keyword_only.json", json.dumps(keyword_only, indent=1) + "\n")

    # 6. Audit log sample from a scripted session.
    conn.close()
    audit_path = OUT / "audit_sample.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    service = Service(DB, audit_path, config, clock=FixedClock(), as_of=as_of)
    session = [
        ("search", newcomer, "earn-out provisions memo", {}),
        ("search", walled, f"project {codename.lower()}", {}),
        ("search", lead, f"project {codename.lower()}", {}),
        ("search", newcomer, "escheat unclaimed property memo", {}),
        ("search", walled2, "escheat unclaimed property memo", {}),
        ("search", newcomer, '"franchise disclosure" checklist', {}),
        ("search", newcomer, "summary judgment", {"type": "motion", "filed": "yes"}),
        ("who", newcomer, "loan workout", {}),
        ("who", newcomer, "maritime salvage", {}),
        ("search", departed, "severance agreement", {}),
        ("search", newcomer, "escheat unclaimed property memo", {}),
    ]
    for action, user, query, filters in session:
        getattr(service, action)(user, query, filters)
    verdict = audit.verify(audit_path)
    write("audit_verify.json", json.dumps(verdict, indent=1) + "\n")
    rows = audit.zero_result_report(audit.read_entries(audit_path))
    write("zero_results_report.txt", audit.format_zero_result_report(rows))
    print("  wrote output/audit_sample.jsonl")

    # 7. Static snapshot of the web UI (opens without a server).
    conn = index.connect(DB, readonly=True)
    people = {p["person_id"]: p for p in service.users()}
    snapshot = {"meta": {"demo_users": demo, "people": [], "presets": PRESETS},
                "search": {}, "who": {}}
    for u in demo:
        for q in PRESETS["search"]:
            snapshot["search"][f"{u['person_id']}|{q}"] = search.search(
                conn, u["person_id"], q, config=config, limit=6, explain=True, as_of=as_of)
        for q in PRESETS["who"]:
            snapshot["who"][f"{u['person_id']}|{q}"] = experience.who(
                conn, u["person_id"], q, config=config, as_of=as_of, limit=6)
    assert all(u["person_id"] in people for u in demo)
    write("demo.html", page_html(snapshot))
    conn.close()

    q = quality["queries_using_the_corpus_vocabulary"]
    print(f"\nRetrieval on the synthetic key: precision at 5 = {q['precision_at_5']}, "
          f"recall at 10 = {q['recall_at_10']} ({q['queries']} queries in the corpus's own words); "
          f"all {quality['all_queries']['queries']} queries: "
          f"{quality['all_queries']['precision_at_5']} and {quality['all_queries']['recall_at_10']}.")
    print(f"Permission checks from the key: {quality['permission_checks']['checks_run']} run, "
          f"{len(quality['permission_checks']['leaks'])} leaks.")
    print("Open output/demo.html for a static snapshot, or run: python run_demo.py --serve")
    if args.serve:
        from kx.server import serve
        serve(Service(DB, cfg.DEFAULT_AUDIT_PATH, config, as_of=as_of), DATA, args.port)


if __name__ == "__main__":
    main()
