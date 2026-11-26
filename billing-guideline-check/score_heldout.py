"""Score the tool on a held-out batch written by an independent author.

    python score_heldout.py heldout/batch_a heldout_results/batch_a_first_run.json

Three measurements, kept apart:

(a) intake      the intake helper against INTAKE_KEY.json: for each rule a person
                would take from the document, did intake propose the right type on
                the right sentence, and with the right stated parameters.
(b) engine      the engine with the hand-confirmed guideline JSON against
                ANSWER_KEY.json.
(c) end_to_end  the engine using only what intake proposed, as if a person had
                confirmed every proposal unchanged.

Scoring rules, from heldout/README.md:
- A planted violation is found when a finding of the same rule type sits on the
  same invoice and line with the expected status (open or waived).
- alternate_lines are honoured first: for attendance limits a finding of that
  rule on any listed line counts as the planted one and is not a false positive.
- Research limit: a finding of that rule on another line of the same invoice
  counts as found. Daily cap: a finding of that rule for the same person and
  day counts as found.
- A finding of any rule on a must_not_flag line is a false positive, unless an
  alternate line or one of the two tolerances above accounts for it.
- An invoice-level finding that is not planted is a false positive.
- A different rule raised on a planted line is counted as unjudged.
- Items marked schema_limit, and receipt, cost and AI-flag items on a LEDES
  file, are left out of recall and listed separately.

Fictional data. Not legal or billing advice.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from billcheck import guidelines as G  # noqa: E402
from billcheck import intake  # noqa: E402
from billcheck.engine import check_invoice  # noqa: E402
from billcheck.model import DataError, dec  # noqa: E402
from billcheck.readers import read_invoice_file  # noqa: E402
from billcheck.waivers import load_waivers  # noqa: E402

LEDES_UNCHECKABLE = {"expense_receipt_threshold", "expense_markup", "ai_disclosure_required", "ai_nonpayable_task"}


def _type(finding):
    return finding.rule_id if finding.rule_type == "arithmetic" else finding.rule_type


def _norm(text):
    return " ".join(re.sub(r"[^a-z0-9$%. ]+", " ", text.lower()).split())


def _overlap(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) * 2 >= len(ta | tb)


def _same(value, expected):
    if isinstance(expected, bool) or isinstance(value, bool):
        return value is expected
    if isinstance(expected, list) and isinstance(value, dict):
        # the key names the categories only; keyword lists are not ground truth
        return sorted(value) == sorted(map(str, expected))
    if isinstance(expected, list):
        return isinstance(value, list) and sorted(map(str, value)) == sorted(map(str, expected))
    if isinstance(expected, dict):
        return isinstance(value, dict) and set(value) == set(expected) and all(_same(value[k], expected[k]) for k in expected)
    try:
        return dec(value) == dec(expected)
    except DataError:
        return str(value) == str(expected)


# ------------------------------------------------------------------ (a) intake


def score_intake(batch_dir):
    with open(os.path.join(batch_dir, "INTAKE_KEY.json"), "r", encoding="utf-8") as handle:
        key = json.load(handle)
    per_client = []
    proposals = {}
    for client in key["clients"]:
        with open(os.path.join(batch_dir, client["document"]), "r", encoding="utf-8") as handle:
            text = handle.read()
        proposed = intake.propose_rules(text, client["client_id"], client["client_id"], client["document"])
        proposals[client["client_id"]] = proposed
        used = set()
        correct, wrong_params, missed, severity_diff = [], [], [], []
        for expected in client["expected_rules"]:
            match = None
            for index, rule in enumerate(proposed["rules"]):
                if index not in used and rule["type"] == expected["type"] and _overlap(rule["source_quote"], expected["source_quote"]):
                    match = index
                    break
            if match is None:
                missed.append({"rule_id": expected["rule_id"], "type": expected["type"], "source_quote": expected["source_quote"]})
                continue
            used.add(match)
            rule = proposed["rules"][match]
            bad = {
                name: {"expected": value, "proposed": rule["params"].get(name)}
                for name, value in expected["key_params"].items()
                if name not in rule["params"] or not _same(rule["params"][name], value)
            }
            if bad:
                wrong_params.append({"rule_id": expected["rule_id"], "type": expected["type"], "differences": bad, "source_quote": expected["source_quote"]})
            else:
                correct.append(expected["rule_id"])
        not_rules = client.get("sentences_that_are_not_rules", [])
        wrong = []
        for index, rule in enumerate(proposed["rules"]):
            if index in used:
                continue
            trap = any(_overlap(rule["source_quote"], item["text"]) for item in not_rules)
            wrong.append({"type": rule["type"], "source_quote": rule["source_quote"], "on_a_listed_non_rule_sentence": trap})
        per_client.append(
            {
                "client_id": client["client_id"],
                "expected_rules": len(client["expected_rules"]),
                "proposed_correctly": len(correct),
                "right_type_wrong_parameters": wrong_params,
                "missed": missed,
                "wrong_proposals": wrong,
                "candidates_proposed": len(proposed["rules"]),
            }
        )
    total = sum(c["expected_rules"] for c in per_client)
    summary = {
        "expected_rules": total,
        "proposed_correctly": sum(c["proposed_correctly"] for c in per_client),
        "right_type_wrong_parameters": sum(len(c["right_type_wrong_parameters"]) for c in per_client),
        "missed": sum(len(c["missed"]) for c in per_client),
        "wrong_proposals": sum(len(c["wrong_proposals"]) for c in per_client),
    }
    return {"summary": summary, "clients": per_client}, proposals


# ------------------------------------------------------------------ (b) and (c) engine


def run_engine(batch_dir, key, guides, waivers):
    matters = G.load_matters(os.path.join(batch_dir, "matters.json"))
    results = {}
    for invoice_id, rel in sorted(key["invoice_files"].items()):
        for invoice in read_invoice_file(os.path.join(batch_dir, rel)):
            guide = guides[key["invoice_guidelines"][invoice.invoice_id]]
            results[invoice.invoice_id] = check_invoice(invoice, guide, matters.get(invoice.matter_id), waivers(guide))
    return results


def score_engine(key, results):
    formats = {inv: results[inv].invoice.source_format for inv in results}
    alternates = {(a["invoice_id"], a["line_no"]): set(a["also_acceptable_lines"]) for a in key.get("alternate_lines", [])}
    must_not = {(inv, n) for inv, lines in key["must_not_flag"].items() for n in lines}
    planted_lines = {(p["invoice_id"], p["line_no"]) for p in key["planted"] if p["line_no"] is not None}
    schema_limit = {(h["invoice_id"], h["line_no"]) for h in key.get("hard_cases_clean", []) if h.get("schema_limit")}

    listed = key.get("not_checkable_in_ledes")
    listed_uncheckable = {(x["invoice_id"], x.get("line_no")) for x in listed if isinstance(x, dict)} if isinstance(listed, list) else set()

    findings = [(inv, f) for inv, r in results.items() for f in r.findings]
    accounted = set()  # ids of findings that match a planted item
    found, missed, wrong_status, excluded = [], [], [], []

    for p in key["planted"]:
        inv, line, rtype = p["invoice_id"], p["line_no"], p["rule_type"]
        if formats.get(inv) == "ledes1998b" and rtype in LEDES_UNCHECKABLE or (inv, line) in listed_uncheckable:
            excluded.append(dict(p, why="not checkable in the LEDES layout"))
            continue
        if p.get("schema_limit"):
            excluded.append(dict(p, why="the rule parameters cannot express it (schema limit)"))
            continue
        same_rule = [f for i, f in findings if i == inv and _type(f) == rtype]
        if line is None:
            hits = [f for f in same_rule if f.line_no is None and (not p["timekeeper_id"] or f.timekeeper_id == p["timekeeper_id"])]
        else:
            accept = {line} | alternates.get((inv, line), set()) if rtype == "staffing_event_limit" else {line}
            hits = [f for f in same_rule if f.line_no in accept]
            if not hits and rtype == "research_approval":
                hits = [f for f in same_rule if f.line_no is not None]
            if not hits and rtype == "daily_hour_cap":
                planted_line = next(ln for ln in results[inv].invoice.lines if ln.line_no == line)
                hits = [f for f in same_rule if f.timekeeper_id == planted_line.timekeeper_id and f.entry_date == planted_line.date]
        if not hits:
            missed.append(p)
            continue
        accounted.update(id(f) for f in hits)
        if any(f.status == p["expected_status"] for f in hits):
            found.append(p)
        else:
            wrong_status.append(p)

    false_positives, unjudged, schema_hits = [], [], []
    for inv, f in findings:
        if id(f) in accounted:
            continue
        row = {"invoice_id": inv, "line_no": f.line_no, "rule_type": _type(f), "rule_id": f.rule_id,
               "narrative": f.entry_narrative, "explanation": f.explanation}
        if (inv, f.line_no) in schema_limit:
            schema_hits.append(row)
        elif f.line_no is None or (inv, f.line_no) in must_not:
            false_positives.append(row)
        elif (inv, f.line_no) in planted_lines:
            unjudged.append(row)
        else:
            false_positives.append(row)

    counted = len(key["planted"]) - len(excluded)

    def tally(field):
        out = {}
        for group, items in (("found", found), ("missed", missed + wrong_status)):
            for p in items:
                out.setdefault(p.get(field, "?"), {"found": 0, "missed": 0})[group] += 1
        return dict(sorted(out.items()))

    return {
        "planted_total": len(key["planted"]),
        "planted_counted": counted,
        "planted_found": len(found),
        "planted_missed": len(missed),
        "planted_wrong_status": len(wrong_status),
        "false_positive_findings": len(false_positives),
        "must_not_flag_lines": len(must_not),
        "must_not_flag_lines_flagged": len({(r["invoice_id"], r["line_no"]) for r in false_positives if r["line_no"] is not None}),
        "unjudged_extra_findings_on_planted_lines": len(unjudged),
        "excluded_from_recall": excluded,
        "schema_limit_findings": schema_hits,
        "by_difficulty": tally("difficulty"),
        "by_rule_type": tally("rule_type"),
        "missed": missed,
        "wrong_status": wrong_status,
        "false_positives": false_positives,
        "unjudged": unjudged,
        "not_enforced_respected": all(
            not [f for f in results[item["invoice_id"]].findings if f.rule_id == item["rule_id"]] for item in key.get("not_enforced", [])
        ),
        "not_checked_notes": {inv: r.not_checked for inv, r in results.items() if r.not_checked},
    }


def score_batch(batch_dir):
    with open(os.path.join(batch_dir, "ANSWER_KEY.json"), "r", encoding="utf-8") as handle:
        key = json.load(handle)
    intake_score, proposals = score_intake(batch_dir)

    # (b) hand-confirmed guideline files
    hand = {rel: G.load_guideline(os.path.join(batch_dir, rel)) for rel in set(key["invoice_guidelines"].values())}
    hand_waivers = load_waivers(os.path.join(batch_dir, "waivers.json"))
    engine = score_engine(key, run_engine(batch_dir, key, hand, lambda guide: hand_waivers))

    # (c) only what intake proposed, every proposal confirmed unchanged
    confirmed = {}
    for rel, guide in hand.items():
        data = json.loads(json.dumps(G.to_jsonable(proposals[guide.client_id])))
        for rule in data["rules"]:
            if intake.PREFERENCE_NOTE in rule.get("notes", ""):
                continue  # intake itself says the wording is a preference; it stays proposed
            rule.update(status="confirmed", confirmed_by="scorer: every proposal confirmed unchanged", confirmed_on="2026-11-26")
        confirmed[rel] = G.from_dict(G.loads(json.dumps(data)))

    def mapped_waivers(guide):
        # a waiver names the hand rule id; point it at the proposed rule of the same type
        hand_guide = next(g for g in hand.values() if g.client_id == guide.client_id)
        types = {r.rule_id: r.type for r in hand_guide.rules}
        out = []
        for waiver in load_waivers(os.path.join(batch_dir, "waivers.json")):
            for rule in guide.rules:
                if types.get(waiver.rule_id) == rule.type:
                    copy = load_waivers(os.path.join(batch_dir, "waivers.json"))
                    copy = next(w for w in copy if w.waiver_id == waiver.waiver_id)
                    copy.rule_id = rule.rule_id
                    out.append(copy)
        return out

    end_to_end = score_engine(key, run_engine(batch_dir, key, confirmed, mapped_waivers))
    return {
        "notice": "Fictional data. Not legal or billing advice.",
        "batch": os.path.basename(os.path.normpath(batch_dir)),
        "intake": intake_score,
        "engine_with_hand_confirmed_rules": engine,
        "engine_with_intake_proposals_only": end_to_end,
    }


def headline(score):
    a = score["intake"]["summary"]
    lines = ["batch: %s" % score["batch"],
             "(a) intake: %d of %d rules proposed correctly, %d right type with wrong parameters, %d missed, %d wrong proposals"
             % (a["proposed_correctly"], a["expected_rules"], a["right_type_wrong_parameters"], a["missed"], a["wrong_proposals"])]
    for label, name in (("(b) engine, hand-confirmed rules", "engine_with_hand_confirmed_rules"),
                        ("(c) engine, intake proposals only", "engine_with_intake_proposals_only")):
        e = score[name]
        lines.append(
            "%s: %d of %d planted found, %d missed, %d wrong status; %d false-positive findings on %d of %d must-not-flag lines; %d unjudged; %d excluded"
            % (label, e["planted_found"], e["planted_counted"], e["planted_missed"], e["planted_wrong_status"], e["false_positive_findings"],
               e["must_not_flag_lines_flagged"], e["must_not_flag_lines"], e["unjudged_extra_findings_on_planted_lines"], len(e["excluded_from_recall"]))
        )
        lines.append("    by difficulty: %s" % json.dumps(e["by_difficulty"]))
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python score_heldout.py <batch_dir> <output.json>")
    result = score_batch(sys.argv[1])
    os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
    with open(sys.argv[2], "w", encoding="utf-8") as handle:
        handle.write(json.dumps(G.to_jsonable(result), indent=2, ensure_ascii=False) + "\n")
    print(headline(result))
