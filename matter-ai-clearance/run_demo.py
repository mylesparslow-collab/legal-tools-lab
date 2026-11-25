"""Run the whole demo and write sample outputs into output/. One command: python run_demo.py"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from clearance import clauses, engine, lanes, reports  # noqa: E402
from clearance.cli import evaluate_all  # noqa: E402
from clearance.store import Store, load_policy  # noqa: E402

AS_OF = "2026-11-25"  # fixed so the committed outputs do not change from day to day
INDEX_MATTERS = ["M-1001", "M-1002", "M-1008", "M-1010"]


def main():
    out = ROOT / "output"
    if out.exists():
        shutil.rmtree(out)
    (out / "memos").mkdir(parents=True)
    store = Store()
    patterns = clauses.load_patterns()
    policy = load_policy()
    features, _ = lanes.load_lanes()

    def dump(path, obj):
        path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")

    # 1. Clause scan and measured accuracy
    scans = [store.scan(d["id"], patterns) for d in store.all_document_entries()]
    dump(out / "clause_hits.json", scans)
    ev = evaluate_all(store, patterns)
    dump(out / "classifier_evaluation.json", ev)
    ev_text = clauses.format_evaluation(ev)
    (out / "classifier_evaluation.txt").write_text(ev_text + "\n", encoding="utf-8")
    print(ev_text)
    print()

    # 2. Clearance memo for every matter
    summary = ["Matter banners as of %s" % AS_OF, ""]
    records = {}
    for mid in store.matter_ids():
        rec = engine.clear_matter(store.matter(mid), store, features, policy, patterns, AS_OF)
        records[mid] = rec
        dump(out / "memos" / (mid + ".json"), rec)
        (out / "memos" / (mid + ".html")).write_text(reports.memo_html(rec), encoding="utf-8")
        summary.append(reports.memo_text(rec))
        summary.append("")
        print("%s  %s" % (mid, rec["banner"]))
    (out / "matter_summary.txt").write_text("\n".join(summary), encoding="utf-8")
    print()

    # 3. Client-terms tracker
    rows = reports.tracker_rows(store, patterns)
    (out / "client_terms_tracker.csv").write_text(reports.tracker_csv(rows, patterns), encoding="utf-8")
    (out / "client_terms_tracker.html").write_text(reports.tracker_html(rows, patterns, ev), encoding="utf-8")

    # 4. Change report: a client's updated guidelines
    rep = reports.diff_terms("quillfether", "quillfether-ocg-v1-2025", "quillfether-ocg-v2-2026",
                             store, features, policy, patterns, AS_OF)
    dump(out / "change_report_quillfether.json", rep)
    (out / "change_report_quillfether.html").write_text(reports.diff_html(rep), encoding="utf-8")
    print(reports.diff_text(rep))
    print()

    # 5. Registry import: the same matter cleared against a registry-format file
    reg_features, reg_report = lanes.load_lanes(ROOT / "data" / "registry_sample.json")
    reg_rec = engine.clear_matter(store.matter("M-1001"), store, reg_features, policy, patterns, AS_OF)
    dump(out / "registry_import_report.json",
         {"import_report": reg_report, "matter": "M-1001", "banner": reg_rec["banner"],
          "decisions": [{"feature_id": d["feature_id"], "decision": d["decision"], "rule_ids": d["rule_ids"],
                         "by_data_class": d["by_data_class"]} for d in reg_rec["decisions"]]})
    print("Registry import: %d tools read; not mapped: %s" % (
        reg_report["tools_read"], ", ".join(reg_report["unmapped_top_level_fields"] + reg_report["unmapped_tool_fields"])))
    print("  M-1001 against the registry file: %s" % reg_rec["banner"])
    print()

    # 6. Static demo page
    (ROOT / "index.html").write_text(reports.index_html([records[m] for m in INDEX_MATTERS], ev), encoding="utf-8")
    stale = [r["rule_id"] for r in records["M-1001"]["rules_past_review"]]
    print("Policy rules past their review date as of %s: %s" % (AS_OF, ", ".join(stale) or "none"))
    print("Wrote %d files under output/ and index.html" % sum(1 for p in out.rglob("*") if p.is_file()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
