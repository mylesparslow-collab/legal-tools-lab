"""Run the gate and the MFN election filter and write the memo.

python3 -m sideletter.cli --investor sample_data/investor_state.json -o output/state
"""
import argparse
import json
import os

from . import gate, memo, mfn

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(investor, fund, draft_text, compendium_text, registry, ruleset, model_items=None):
    terms = fund["mfn_terms"]
    provisions = mfn.parse_compendium(compendium_text)
    decisions = [mfn.decide(p, investor, terms) for p in provisions]
    model = None
    if model_items is not None:
        ok, bad = mfn.verify_model_items(model_items, provisions)
        decisions = mfn.apply_model_items(decisions, ok, terms, investor, provisions)
        model = {"accepted": ok, "rejected": bad}
    own = {}
    for s in gate.split_sections(draft_text):
        cat, _ = mfn.classify(s["title"])
        if cat == "other":
            cat, _ = mfn.classify(s["text"])
        if s["ref"] != "preamble" and cat != "other":
            own.setdefault(cat, []).append(s["ref"])
    for d in decisions:
        d["own_draft"] = ("Has a clause on this topic: " + ", ".join(own[d["category"]])) if d["category"] in own else "No clause on this topic"
    r = {"investor": investor, "fund": {k: v for k, v in fund.items() if k != "placement_agents"},
         "aggregated_commitment": mfn.aggregated_commitment(investor, terms),
         "deadline": mfn.election_deadline(terms, fund["compendium_delivery_date"]),
         "gate": gate.run_gate(ruleset, investor, fund, draft_text, registry),
         "mfn": decisions, "model": model,
         "counts": {v: sum(d["verdict"] == v for d in decisions) for v in ("ELECTABLE", "REVIEW", "NOT_ELECTABLE")}}
    memo.assert_quotes(r, draft_text, compendium_text)
    return r


def main(argv=None):
    sd = os.path.join(HERE, "sample_data")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--investor", default=os.path.join(sd, "investor_state.json"))
    ap.add_argument("--fund", default=os.path.join(sd, "fund.json"))
    ap.add_argument("--draft", default=os.path.join(sd, "draft_side_letter.txt"))
    ap.add_argument("--compendium", default=os.path.join(sd, "mfn_compendium.txt"))
    ap.add_argument("--registry", default=os.path.join(sd, "lobbyist_registry_snapshot.csv"))
    ap.add_argument("--rules", default=os.path.join(HERE, "rules", "statutory_rules.json"))
    ap.add_argument("--model-output", help="optional JSON of model-proposed items; each is quote-checked before use")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "output"))
    a = ap.parse_args(argv)
    load = lambda p: json.load(open(p, encoding="utf-8"))
    read = lambda p: open(p, encoding="utf-8").read()
    r = run(load(a.investor), load(a.fund), read(a.draft), read(a.compendium), gate.load_registry(a.registry),
            gate.load_rules(a.rules), load(a.model_output) if a.model_output else None)
    os.makedirs(a.out, exist_ok=True)
    json.dump(r, open(os.path.join(a.out, "results.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(os.path.join(a.out, "Election_Memo.md"), "w", encoding="utf-8").write(memo.build_markdown(r))
    memo.build_docx(r, os.path.join(a.out, "Election_Memo.docx"))
    open(os.path.join(a.out, "MFN_Election_Deadline.ics"), "w", encoding="utf-8", newline="").write(memo.build_ics(r))
    g = {}
    for f in r["gate"]:
        g[f["status"]] = g.get(f["status"], 0) + 1
    print(f"{r['investor']['name']}\n  gate: {g}\n  mfn: {r['counts']}\n  deadline: {r['deadline']['deadline']}\n  wrote {a.out}")
    return r


if __name__ == "__main__":
    main()
