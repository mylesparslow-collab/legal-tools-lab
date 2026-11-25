"""app/scoring.js, run in Node. The overlap rule and its edge cases."""
import random
import sys
from types import SimpleNamespace

from conftest import KIT, js

RULE = {"minMarkChars": 20, "maxMarkChars": 600, "overlapCap": 30}

# Two planted defects 100 characters long, 50 apart, and one short one.
D1 = {"id": "D1", "type": "clause_high", "code": "L2", "severity": "high", "spans": [[100, 200]]}
D2 = {"id": "D2", "type": "clause_medium", "code": "L7", "severity": "medium", "spans": [[250, 350]]}
D3 = {"id": "D3", "type": "omission", "code": "L1", "severity": "high", "spans": [[500, 540]]}
DEFECTS = [D1, D2, D3]


def mark(i, start, end, type_="clause_high"):
    return {"id": f"m{i}", "start": start, "end": end, "type": type_}


def score(marks, defects=DEFECTS):
    return js(("scoreMarks", defects, marks, RULE))


def statuses(result):
    return [m["status"] for m in result["marks"]]


def test_default_rule_matches_the_data_file(data):
    assert js(("const", "DEFAULT_RULE")) == data["rule"] == RULE


def test_exact_selection_of_the_planted_span_is_a_hit():
    r = score([mark(1, 100, 200)])
    assert statuses(r) == ["hit"] and r["counts"]["found"] == 1 and r["counts"]["falseAlarms"] == 0
    assert r["defects"][0]["status"] == "found"


def test_partial_overlap_of_30_characters_counts_and_29_does_not():
    assert statuses(score([mark(1, 60, 130)])) == ["hit"]           # overlaps 100..130
    assert statuses(score([mark(1, 60, 129)])) == ["false_alarm"]   # overlaps 100..129
    assert statuses(score([mark(1, 170, 240)])) == ["hit"]          # tail end, 30 characters
    assert statuses(score([mark(1, 171, 240)])) == ["false_alarm"]


def test_short_planted_span_needs_half_its_length():
    # D3 is 40 characters long, so the mark must cover 20 of them.
    assert js(("needFor", [500, 540], RULE)) == 20
    assert statuses(score([mark(1, 470, 520, "omission")])) == ["hit"]
    assert statuses(score([mark(1, 470, 519, "omission")])) == ["false_alarm"]
    assert js(("needFor", [0, 1], RULE)) == 1


def test_mark_that_only_touches_the_edge_is_a_false_alarm():
    assert statuses(score([mark(1, 200, 240)])) == ["false_alarm"]
    assert statuses(score([mark(1, 50, 100)])) == ["false_alarm"]


def test_selection_covering_two_defects_counts_for_the_larger_overlap_only():
    r = score([mark(1, 140, 350)])  # 60 characters of D1, all 100 of D2
    assert r["marks"][0]["defectId"] == "D2" and r["marks"][0]["alsoCovered"] == ["D1"]
    assert r["counts"]["found"] == 1 and r["counts"]["hits"] == 1
    assert [d["status"] for d in r["defects"]] == ["missed", "misclassified", "missed"]


def test_tie_between_two_defects_goes_to_the_first_in_the_key():
    r = score([mark(1, 150, 300)])  # 50 characters of each
    assert r["marks"][0]["defectId"] == "D1" and r["marks"][0]["alsoCovered"] == ["D2"]


def test_second_mark_can_pick_up_the_defect_the_first_one_left():
    r = score([mark(1, 140, 350, "clause_medium"), mark(2, 100, 200)])
    assert statuses(r) == ["hit", "hit"] and r["counts"]["found"] == 2


def test_duplicate_marks_count_once_and_are_not_false_alarms():
    r = score([mark(1, 100, 200), mark(2, 110, 190), mark(3, 100, 200)])
    assert statuses(r) == ["hit", "duplicate", "duplicate"]
    c = r["counts"]
    assert (c["found"], c["hits"], c["duplicates"], c["falseAlarms"]) == (1, 1, 2, 0)
    assert r["defects"][0]["markIds"] == ["m1", "m2", "m3"]


def test_wrong_type_in_the_right_place_is_found_misclassified():
    r = score([mark(1, 100, 200, "omission")])
    assert statuses(r) == ["misclassified"]
    c = r["counts"]
    assert (c["found"], c["correctType"], c["misclassified"], c["missed"]) == (1, 0, 1, 2)
    assert r["defects"][0]["chosenType"] == "omission" and r["recall"] == 1 / 3


def test_first_mark_made_decides_the_type():
    r = score([mark(1, 100, 200, "omission"), mark(2, 100, 200, "clause_high")])
    assert r["defects"][0]["status"] == "misclassified"
    r = score([mark(1, 100, 200, "clause_high"), mark(2, 100, 200, "omission")])
    assert r["defects"][0]["status"] == "found"


def test_marks_that_are_too_short_or_too_long_are_not_scored():
    r = score([mark(1, 100, 119), mark(2, 0, 601), mark(3, 100, 120), mark(4, 0, 600)])
    assert statuses(r) == ["too_short", "too_long", "false_alarm", "hit"]
    assert r["counts"]["notScored"] == 2 and r["counts"]["falseAlarms"] == 1


def test_selecting_the_whole_document_is_refused_not_rewarded():
    r = score([mark(1, 0, 5000)])
    assert statuses(r) == ["too_long"] and r["counts"]["found"] == 0


def test_defect_with_two_spans_is_found_through_either():
    d = dict(D1, spans=[[100, 200], [800, 900]])
    assert score([mark(1, 820, 880)], [d, D2])["defects"][0]["status"] == "found"
    r = score([mark(1, 100, 200), mark(2, 800, 900)], [d, D2])
    assert statuses(r) == ["hit", "duplicate"]


def test_no_marks_means_everything_missed_and_zero_recall():
    r = score([])
    assert r["counts"]["missed"] == 3 and r["recall"] == 0 and r["marks"] == []


def test_no_planted_defects_gives_null_recall_not_a_division_error():
    r = score([mark(1, 100, 200)], [])
    assert r["recall"] is None and statuses(r) == ["false_alarm"]


def test_breakdown_by_type_and_by_rule():
    r = score([mark(1, 100, 200), mark(2, 250, 350, "clause_high")])
    assert r["byType"] == {
        "clause_high": {"planted": 1, "found": 1, "misclassified": 0, "missed": 0},
        "clause_medium": {"planted": 1, "found": 1, "misclassified": 1, "missed": 0},
        "omission": {"planted": 1, "found": 0, "misclassified": 0, "missed": 1},
    }
    assert r["byCode"]["L1"]["missed"] == 1 and r["byCode"]["L2"]["found"] == 1


def test_matching_agrees_with_the_eval_kit_scorer_on_random_spans():
    sys.path.insert(0, str(KIT / "eval_harness"))
    from harness.score import _match

    rng = random.Random(7)
    calls, expected = [], []
    for _ in range(300):
        defects, pos = [], 0
        for i in range(rng.randint(1, 5)):
            spans = []
            for _s in range(rng.choice([1, 1, 2])):
                pos += rng.randint(0, 80)
                length = rng.randint(2, 200)
                spans.append([pos, pos + length])
                pos += length
            defects.append({"id": f"D{i}", "spans": spans})
        a = rng.randint(0, pos)
        span = [a, a + rng.randint(20, 400)]
        kit_doc = SimpleNamespace(doc_id="t", defects=[
            SimpleNamespace(id=d["id"], spans=[tuple(s) for s in d["spans"]], kind="clause", authority_keys=[])
            for d in defects])
        got, _basis = _match(kit_doc, {}, [tuple(span)])
        expected.append(got.id if got else None)
        calls.append(("matchSpan", span, defects, RULE))
    results = js(*calls)
    assert [r["defectId"] for r in results] == expected
    assert len(set(expected)) > 3


def test_real_document_every_planted_span_scores_as_its_own_defect(docs):
    for doc in docs.values():
        marks = [{"id": d["id"], "start": d["spans"][0][0], "end": d["spans"][0][1], "type": d["type"]}
                 for d in doc["defects"]]
        r = js(("scoreMarks", doc["defects"], marks, RULE))
        assert r["counts"]["found"] == r["counts"]["correctType"] == len(doc["defects"])
        assert [m["defectId"] for m in r["marks"]] == [d["id"] for d in doc["defects"]]


def test_every_planted_span_fits_inside_the_mark_length_limit(docs):
    for doc in docs.values():
        for d in doc["defects"]:
            for s, e in d["spans"]:
                assert RULE["minMarkChars"] <= e - s <= RULE["maxMarkChars"]


# ---------- verify list ----------

ITEMS = [{"id": "V1", "defect": "D1"}, {"id": "V2", "defect": None}, {"id": "V3", "defect": "D2"}, {"id": "V4", "defect": None}]


def test_verify_counts_planted_ticked_missed_and_extra_checks():
    r = js(("scoreVerify", ITEMS, ["V1", "V2"], DEFECTS))
    assert r["counts"] == {"planted": 2, "found": 1, "missed": 1, "extraChecks": 1, "items": 4, "ticked": 2}
    assert [i["status"] for i in r["items"]] == ["found", "extra_check", "missed", "left"]
    assert r["recall"] == 0.5 and r["byCode"]["L7"]["missed"] == 1


def test_verify_ticking_everything_finds_all_and_reports_the_extra_checks():
    r = js(("scoreVerify", ITEMS, ["V1", "V2", "V3", "V4"], DEFECTS))
    assert r["counts"]["found"] == 2 and r["counts"]["extraChecks"] == 2 and r["recall"] == 1


def test_verify_ticking_nothing_misses_all():
    r = js(("scoreVerify", ITEMS, [], DEFECTS))
    assert r["counts"]["missed"] == 2 and r["counts"]["extraChecks"] == 0


# ---------- session totals, result files, group results ----------

def test_combine_adds_exercises_and_keeps_modes_apart():
    a = score([mark(1, 100, 200), mark(2, 600, 700)])
    b = js(("scoreVerify", ITEMS, ["V1", "V2"], DEFECTS))
    t = js(("combine", [{"mode": "spot", "score": a}, {"mode": "verify", "score": b}]))
    assert (t["planted"], t["found"], t["missed"], t["falseAlarms"], t["extraChecks"]) == (5, 2, 3, 1, 1)
    assert t["recall"] == 0.4
    assert t["byMode"]["spot"]["planted"] == 3 and t["byMode"]["verify"]["found"] == 1
    assert t["byCode"]["L2"] == {"planted": 2, "found": 2, "misclassified": 0, "missed": 0}


def result(rid, exercises):
    return {"schema": "catch-the-error-drill/result/1", "id": rid, "build": "b", "exercises": exercises}


def exercise(mode, doc, found=(), missed=(), wrong=(), false_blocks=()):
    return {"mode": mode, "doc": doc,
            "defects": [{"id": i, "status": "found"} for i in found] + [{"id": i, "status": "missed"} for i in missed]
            + [{"id": i, "status": "misclassified"} for i in wrong],
            "marks": [{"status": "false_alarm", "block": b} for b in false_blocks]}


def test_validate_result_accepts_a_good_file_and_names_problems():
    good = result("r1", [exercise("spot", "lease-01", found=["A"], missed=["B"])])
    assert js(("validateResult", good)) == []
    assert js(("validateResult", {"hello": 1}))
    assert js(("validateResult", [1, 2]))
    assert js(("validateResult", dict(good, schema="other")))
    bad = result("r2", [{"mode": "quiz", "doc": "x", "defects": [{"id": "A", "status": "aced"}]}])
    assert len(js(("validateResult", bad))) == 2


def test_aggregate_lists_most_missed_first_without_any_per_person_output():
    people = [
        result("p1", [exercise("spot", "lease-01", found=["A"], missed=["B", "C"], false_blocks=[7, 9])]),
        result("p2", [exercise("spot", "lease-01", missed=["A", "B"], wrong=["C"], false_blocks=[7, 7])]),
        result("p3", [exercise("spot", "lease-01", found=["A", "C"], missed=["B"], false_blocks=[12])]),
    ]
    agg = js(("aggregate", people))
    assert [(d["id"], d["missed"], d["attempts"]) for d in agg["defects"]] == [("B", 3, 3), ("A", 1, 3), ("C", 1, 3)]
    assert agg["defects"][2]["misclassified"] == 1
    assert agg["people"] == 3 and agg["byMode"]["spot"] == {"planted": 9, "found": 4, "misclassified": 1, "missed": 5}
    assert agg["falseAlarms"] == [{"doc": "lease-01", "block": 7, "people": 2}]
    assert set(agg) == {"people", "defects", "byMode", "falseAlarms"}
    assert "p1" not in str(agg)


def test_aggregate_keeps_spot_and_review_recall_apart():
    people = [result("p1", [exercise("spot", "lease-01", missed=["A", "B"]), exercise("review", "lease-02", found=["X"], missed=["Y"])])]
    agg = js(("aggregate", people))
    assert agg["byMode"]["spot"]["found"] == 0 and agg["byMode"]["review"]["found"] == 1
