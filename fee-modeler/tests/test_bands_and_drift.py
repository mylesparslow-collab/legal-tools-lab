"""Planning bands, the change check, and what the tool does when a type's costs have changed."""

import json
import os
from datetime import date, timedelta
from decimal import Decimal

import pytest

from feemodel import backtest, bands, drift, memo, sensitivity, stats, synth
from feemodel.cost import CostBook
from feemodel.engine import calibration_scores, planning_for, price_proposal, scenario_at_planning
from feemodel.loader import load_json
from helpers import CODE_MAP, RATES, mk_dataset, mk_entry, mk_matter

D = Decimal


# ---- bands ----------------------------------------------------------------------------------

def test_finite_sample_position_by_hand():
    assert bands.position(9, D("0.90")) == (9, True)        # ceil(10 x 0.9) = 9
    assert bands.position(8, D("0.90")) == (8, False)       # ceil(9 x 0.9) = 9, past the end: largest comp, flagged
    assert bands.position(19, D("0.75")) == (15, True)
    assert bands.position(3, D("0.25")) == (1, True)
    assert bands.finite_sample_quantile([D(i) for i in range(1, 20)], D("0.75")) == (D(15), True)
    with pytest.raises(ValueError):
        bands.finite_sample_quantile([], D("0.5"))


def test_finite_sample_band_covers_the_left_out_matter_where_the_interpolated_quantile_does_not():
    # Leave each of ten values out in turn and predict it from the other nine.
    values = [D(v) for v in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)]
    fs = interp = 0
    for i, target in enumerate(values):
        rest = values[:i] + values[i + 1:]
        fs += target <= bands.finite_sample_quantile(rest, D("0.90"))[0]
        interp += target <= stats.quantile(rest, D("0.90"))
    assert fs == 9          # 9 in 10, as the band promises
    assert interp == 8      # the descriptive quantile falls short


def test_adjustment_needs_history_and_only_ever_raises():
    q = D("0.75")
    few = [D("1.5")] * (bands.MIN_CAL_HISTORY - 1)
    assert bands.adjustment(few, q) == (D(1), "none", bands.MIN_CAL_HISTORY - 1)
    low = [D("0.6")] * 12
    assert bands.adjustment(low, q) == (D(1), "type", 12)                 # bands were generous: not lowered
    mixed = [D("0.8")] * 6 + [D("1.4")] * 6
    assert bands.adjustment(mixed, q) == (D("1.4"), "type", 12)           # ceil(13 x 0.75) = 10th of 12
    assert bands.adjustment(mixed, q, min_history=20)[1] == "none"


def test_planning_bands_stay_in_order_and_at_or_above_the_finite_sample_step():
    values = [D(v) for v in range(100, 2100, 100)]
    scores = {"p25": [D("1.3")] * 12, "p50": [D("1")] * 12, "p75": [D("1.1")] * 12, "p90": [D("0.5")] * 12}
    pb = bands.planning_bands(values, scores)
    assert pb["calibrated"] and pb["source_summary"] == "type"
    order = [pb["plan"][b] for b in ("p25", "p50", "p75", "p90")]
    assert order == sorted(order)
    assert all(pb["plan"][b] >= pb["base"][b] for b in pb["base"])
    assert pb["factor"]["p90"] == D(1)
    assert all(isinstance(v, Decimal) for v in pb["plan"].values())
    plain = bands.planning_bands(values, {})
    assert not plain["calibrated"] and plain["plan"] == plain["base"]


def test_planning_note_says_when_unadjusted_and_when_p90_cannot_be_placed():
    out = planning_for([D(v) for v in range(1, 9)], {})                    # eight comps, no history
    assert out["calibrated"] is False and out["unreachable"] == ["P90"]
    assert out["bands"]["p90"] == D(8)
    assert out["notes"][0].startswith("Not adjusted: 0 earlier matters")
    assert "treat it as a floor" in out["notes"][1]


# ---- change check ---------------------------------------------------------------------------

def _items(values, start=date(2018, 1, 1), gap=30):
    return [(start + timedelta(days=gap * i), "M-%03d" % i, D(v)) for i, v in enumerate(values)]


FLAT = [100 + (i * 37) % 23 for i in range(40)]
STEP = FLAT[:20] + [v * 2 for v in FLAT[20:]]


def test_change_check_finds_a_clean_step_and_its_date_without_being_told():
    out = drift.change_point_scan(_items(STEP))
    assert out["flagged"] and out["judged"]
    assert out["change_date"] == date(2018, 1, 1) + timedelta(days=600)      # the 21st matter, exactly
    assert (out["n_before"], out["n_after"]) == (20, 20)
    assert D("1.8") <= out["after_over_before"] <= D("2.2")
    assert out["shuffles_as_extreme"] * 20 <= out["n_shuffles"]
    assert drift.change_point_scan(list(reversed(_items(STEP)))) == out       # input order does not matter; seeded


def test_change_check_leaves_noise_small_shifts_and_short_histories_alone():
    assert drift.change_point_scan(_items(FLAT))["flagged"] is False
    small = FLAT[:20] + [v * D("1.23") for v in FLAT[20:]]                   # cleanly separated but under 1.25x
    out = drift.change_point_scan(_items(small))
    assert out["after_over_before"] < drift.DRIFT_MATERIAL and out["flagged"] is False
    short = drift.change_point_scan(_items(STEP[13:28]))                     # 15 matters: under 2 x 8
    assert short["judged"] is False and short["flagged"] is False
    assert (drift.DRIFT_MIN_SEG, drift.DRIFT_ALPHA, drift.DRIFT_MATERIAL, drift.DRIFT_SHUFFLES) == (8, (1, 20), D("1.25"), 1000)


def test_change_check_flags_a_fall_as_well_as_a_rise():
    out = drift.change_point_scan(_items(list(reversed(STEP))))
    assert out["flagged"] and out["after_over_before"] < D("0.6")


# ---- walk-forward with both -----------------------------------------------------------------

def _step_history(n_before=20, n_after=24):
    """Matters open 40 days apart and close 30 days later; hours double from matter n_before on."""
    matters, entries = [], []
    for i in range(n_before + n_after):
        opened = date(2016, 1, 1) + timedelta(days=40 * i)
        hours = (100 + (i * 37) % 23) * (2 if i >= n_before else 1)
        mid = "S-%02d" % i
        matters.append(mk_matter(mid, "widget_dispute", opened.isoformat(), (opened + timedelta(days=30)).isoformat()))
        entries.append(mk_entry("E-%02d" % i, mid, (opened + timedelta(days=5)).isoformat(), hours))
    return mk_dataset(matters, entries), date(2016, 1, 1) + timedelta(days=40 * n_before)


def test_walk_forward_takes_the_higher_version_once_the_change_is_visible_and_never_looks_ahead():
    ds, changed = _step_history()
    book = CostBook(ds, CODE_MAP)
    records = backtest.walk_forward(ds, book, RATES)
    acted = [r for r in records if r["drift"] and r["drift"]["flagged"]]
    assert acted and all(r["open_date"] > changed for r in acted)             # cannot fire before the change exists
    # Early on, fewer than eight matters from after the change have closed, so the split is placed too early.
    assert all(r["drift"]["change_date"] <= changed for r in acted)
    assert acted[-1]["drift"]["change_date"] == changed                       # with enough of them, it is exact
    with_recent = [r for r in acted if r["drift"]["recent_version"]]
    assert with_recent
    for r in with_recent:
        assert r["plan"] == bands.higher_of(r["plan_whole"], r["plan_recent"])
        assert len(r["recent_values"]) == r["drift"]["n_after"] < r["n_comps"]
        assert r["drift"]["raised"]                                           # costs doubled: the recent version is higher
    for r in records:
        if r["plan_tested"]:
            assert all(r["plan"][b] >= r["plan_whole"][b] for b in r["plan"])
    # Once it acts, matters after the change stop running over their P75.
    assert sum(1 for r in acted if not r["plan_at_or_under_p75"]) < sum(1 for r in acted if not r["at_or_under_p75"])
    off = backtest.walk_forward(ds, book, RATES, act_on_drift=False, calibrate=False)
    assert all(r["drift"] is None for r in off)
    assert all(r["plan"] == r["base"] for r in off if r["plan_tested"])


def test_a_flag_that_says_costs_fell_never_lowers_a_planning_figure():
    """The mirror image of the step history: costs halve. The check flags it; no band moves down."""
    ds, _changed = _step_history()
    for e in ds.entries:                                    # turn the doubling into a halving
        i = int(e.matter_id.split("-")[1])
        e.hours_worked = e.hours_billed = D((100 + (i * 37) % 23) * (2 if i < 20 else 1))
    book = CostBook(ds, CODE_MAP)
    records = backtest.walk_forward(ds, book, RATES)
    fell = [r for r in records if r["drift"] and r["drift"]["flagged"]]
    assert fell and all(r["drift"]["after_over_before"] < 1 for r in fell)
    for r in fell:
        assert r["plan"] == r["plan_whole"] and r["drift"]["raised"] == []
        if r["drift"]["recent_version"]:
            assert r["plan_recent"]["p90"] < r["plan"]["p90"]                # the recent-only version would have been lower


def test_flag_can_only_raise_on_the_committed_data_and_for_every_matter_type(bt, ws):
    records, _summary, _table = bt
    flagged = [r for r in records if r["plan_tested"] and r["drift"] and r["drift"]["flagged"]]
    assert flagged
    for r in records:
        if r["plan_tested"]:
            assert all(r["plan"][b] >= r["plan_whole"][b] for b in r["plan"]), r["matter_id"]
    for mtype in sorted({m.matter_type for m in ws.dataset.matters.values()}):
        base = {"matter_type": mtype, "as_of": "2026-01-01", "target_probability": "0.8",
                "scenarios": [{"type": "fixed", "fee": "50000"}]}
        default, ignored = price_proposal(ws, base), price_proposal(ws, dict(base, drift_action="ignore"))
        if default["status"] != "modeled":
            continue
        for b in ("p25", "p50", "p75", "p90"):
            assert default["planning"]["bands"][b] >= ignored["planning"]["bands"][b], mtype
        assert (default["target"]["planning_fee_covering_standard_value"]
                >= ignored["target"]["planning_fee_covering_standard_value"]), mtype
        for b in ("p50", "p75", "p90"):                      # a higher band can only make the stated margin worse
            assert default["scenarios"][0]["at_planning"][b]["margin"] <= ignored["scenarios"][0]["at_planning"][b]["margin"]


def test_downward_false_alarm_on_the_shipped_data_leaves_the_quote_alone(ws, root):
    proposal = load_json(os.path.join(root, "data", "proposals", "P-005.json"))
    r = price_proposal(ws, proposal)
    d = r["drift"]
    assert d["flagged"] and d["direction"] == "fallen" and d["action"] == "higher_of_two" and d["raised"] == []
    recent, whole = d["versions"]
    assert (recent["n"], whole["n"]) == (11, 66) and r["selection"]["n"] == 66
    assert r["planning"]["bands"] == whole["planning"]
    assert recent["planning"]["p90"] < whole["planning"]["p90"]
    assert any("This memo has not lowered the bands" in w and "after checking why" in w for w in r["warnings"])
    html = memo.render_memo(r)
    assert "Change check: costs for this matter type appear to have fallen" in html
    assert "Used in this memo: the higher of the two at each band" in html
    lowered = price_proposal(ws, dict(proposal, drift_action="recent_only"))       # a person may choose this
    assert lowered["selection"]["n"] == 11 and lowered["planning"]["bands"]["p90"] < r["planning"]["bands"]["p90"]


def test_adjustment_history_is_checked_for_look_ahead(bt, ws):
    records, _summary, _table = bt
    assert backtest.verify_no_lookahead(records, ws.dataset) is True
    used = [r for r in records if r["cal_ids"]]
    assert used
    for r in used[:60]:
        assert all(ws.dataset.matters[c].matter_type == r["matter_type"] for c in r["cal_ids"])     # same type only
        assert len(r["cal_ids"]) >= bands.MIN_CAL_HISTORY
    victim = dict(used[0])
    later = [m.matter_id for m in ws.dataset.matters.values()
             if m.close_date is not None and m.close_date > victim["open_date"]][0]
    victim["cal_ids"] = victim["cal_ids"] + [later]
    with pytest.raises(backtest.LookAheadError):
        backtest.verify_no_lookahead([victim], ws.dataset)


def test_planning_bands_never_sit_below_the_finite_sample_step_in_the_backtest(bt):
    records, summary, _table = bt
    planned = [r for r in records if r["plan_tested"]]
    assert len(planned) == summary["n_tested"] == 385
    for r in planned:
        assert all(r["plan"][b] >= r["base"][b] for b in ("p25", "p50", "p75", "p90"))
        assert all(isinstance(v, Decimal) for v in list(r["plan"].values()) + list(r["scores"].values()))
        assert r["cal_source"] in ("type", "none")
    for row in summary["by_type"]:
        c = row["calibration"]
        assert c["adjusted"] + c["unadjusted"] == row["n_tested"]
        assert row["n_tested"] + row["n_skipped"] == row["n_clean_closed"]


def test_overruns_old_against_new_on_the_committed_data(bt):
    """The measured result of the fix on the shipped seed. Other seeds: output/calibration_study.txt."""
    _records, summary, _table = bt
    got = {r["matter_type"]: (r["descriptive"]["overruns"]["p75"]["count"], r["descriptive"]["overruns"]["p90"]["count"],
                              r["overruns"]["p75"]["count"], r["overruns"]["p90"]["count"], r["n_tested"])
           for r in summary["by_type"]}
    assert got == {
        "administrative_licensing_appeal": (5, 1, 3, 1, 27), "commercial_lease_review": (11, 7, 11, 4, 38),
        "contract_dispute_arbitration": (2, 0, 1, 0, 19), "election_law_advisory": (0, 0, 0, 0, 0),
        "employment_single_plaintiff_defense": (15, 10, 13, 7, 41), "facility_change_of_ownership": (9, 8, 9, 3, 37),
        "internal_investigation": (13, 9, 10, 5, 31), "ordinance_drafting": (16, 5, 9, 3, 41),
        "paga_response": (15, 7, 9, 3, 35), "public_records_litigation": (16, 9, 13, 4, 53),
        "public_works_bid_protest": (10, 3, 8, 2, 41), "regulatory_compliance_audit": (2, 1, 2, 0, 22)}
    for r in summary["by_type"]:                         # the fix never makes a type's overruns worse here
        assert r["overruns"]["p75"]["count"] <= r["descriptive"]["overruns"]["p75"]["count"]
        assert r["overruns"]["p90"]["count"] <= r["descriptive"]["overruns"]["p90"]["count"]


# ---- pricing --------------------------------------------------------------------------------

def test_memo_leads_with_planning_figures_and_keeps_comp_quantiles_labelled(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    pl, q = r["planning"], r["distribution"]["normalized"]["quantiles"]
    assert pl["calibrated"] and pl["n_scores"] == 53 and pl["n"] == 43
    assert all(pl["bands"][b] >= pl["base"][b] for b in q)
    assert pl["bands"]["p90"] > q["p90"]
    html = memo.render_memo(r)
    assert "Planning P50 at" in html and "Planning figures are the ones to price from." in html
    assert "Of the comps (descriptive)" in html and "of the comps: " in html
    assert html.index("Planning P50 at") < html.index("Of the comps (descriptive)")
    assert "Costs for this matter type changed" not in html


def test_scenarios_and_target_fee_use_the_planning_bands(ws, root):
    r = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-001.json")))
    plan, share = r["planning"]["bands"], r["planning"]["cost_share_of_value"]
    fixed, capped = r["scenarios"][0], r["scenarios"][1]
    at = fixed["at_planning"]["p90"]
    assert at["value"] == plan["p90"] and at["revenue"] == D("90000")
    assert abs(at["margin"] - (D("90000") - plan["p90"] * share)) < D("200")       # share is shown rounded
    assert capped["at_planning"]["p90"]["revenue"] == D("120000")                  # the cap binds at planning P90
    assert capped["at_planning"]["p50"]["revenue"] == plan["p50"]                  # under the cap: billed as worked
    t = r["target"]
    assert t["planning_calibrated"] and t["planning_factor"] >= 1
    assert t["planning_fee_covering_standard_value"] == t["planning_base"] * t["planning_factor"]
    assert t["planning_floored_at_band"] is False
    shifted = price_proposal(ws, load_json(os.path.join(root, "data", "proposals", "P-003c.json")))
    ts = shifted["target"]                       # here the 80% figure came out under the planning P75: floored
    assert ts["planning_floored_at_band"] and ts["planning_fee_covering_standard_value"] == shifted["planning"]["bands"]["p75"]
    assert plan["p75"] <= t["planning_fee_covering_standard_value"] <= plan["p90"]  # 80% sits between 75 and 90
    assert t["planning_fee_covering_standard_value"] >= t["fee_covering_standard_value"]
    collar = {"params": {"fee": D(100), "band_low": D(90), "band_high": D(110), "share_pct": D(50)}}
    out = scenario_at_planning({"type": "collar"}, collar, {"p50": D(100), "p75": D(130), "p90": D(60)}, D("0.5"))
    assert (out["p50"]["revenue"], out["p75"]["revenue"], out["p90"]["revenue"]) == (D(100), D(110), D(85))


def test_calibration_scores_for_a_proposal_only_use_outcomes_known_by_its_date(ws):
    early = calibration_scores(ws, "public_records_litigation", date(2023, 1, 1), None, bands.BANDS)
    late = calibration_scores(ws, "public_records_litigation", date(2026, 1, 1), None, bands.BANDS)
    assert len(early["p75"]) == 16 and len(late["p75"]) == 53
    cut = calibration_scores(ws, synth.DRIFT_TYPE, date(2026, 1, 1), date(2022, 4, 12), bands.BANDS)
    assert len(cut["p75"]) == 26                                    # only matters opened since the change


def test_falls_back_with_a_warning_when_there_is_too_little_history_to_adjust(ws):
    r = price_proposal(ws, {"matter_type": "regulatory_compliance_audit", "as_of": "2023-01-01",
                            "scenarios": [{"type": "fixed", "fee": "30000"}], "target_probability": "0.8"})
    assert r["status"] == "modeled" and r["planning"]["calibrated"] is False and r["planning"]["n_scores"] == 4
    assert r["planning"]["bands"] == r["planning"]["base"]
    assert any(w.startswith("Planning figures: Not adjusted: 4 earlier matters") for w in r["warnings"])
    assert r["target"]["planning_calibrated"] is False and r["target"]["planning_factor"] == 1
    html = memo.render_memo(r)
    assert "Planning (not adjusted) P50" in html and "not adjusted" in html


def test_recent_only_refuses_when_too_few_recent_comps_and_the_default_does_not(ws):
    base = {"matter_type": synth.DRIFT_TYPE, "as_of": "2026-01-01", "selection_rules": {"min_comps": 30},
            "scenarios": [{"type": "fixed", "fee": "100000"}]}
    r = price_proposal(ws, dict(base, drift_action="recent_only"))
    assert r["status"] == "refused" and "planning" not in r and "scenarios" not in r
    assert "Only 26 of the 41 selected comps opened since then; 30 are required." in r["refusal"]
    assert "the proposal asks for those only" in memo.render_memo(r)
    d = price_proposal(ws, base)                     # default: whole history, and it says the recent version is missing
    assert d["status"] == "modeled" and d["drift"]["recent_version_available"] is False
    assert any("too few for a recent-only version" in w and "they are too low" in w for w in d["warnings"])
    with pytest.raises(ValueError):
        price_proposal(ws, dict(base, drift_action="restrict"))


def test_shifted_type_memos_show_both_versions_under_each_setting(root):
    def read(name):
        with open(os.path.join(root, "output", name), encoding="utf-8") as fh:
            return fh.read()
    default = read("memo_P-003.html")
    assert "Change check: costs for this matter type appear to have risen" in default
    assert "Comps opened from 2022-04-12 only" in default and "All selected comps, whole history" in default
    assert "Used in this memo: the higher of the two at each band" in default
    assert "A flag can only raise a planning figure: each one is the higher of the recent-only and whole-history versions." in default
    off = read("memo_P-003b.html")
    assert "All selected comps, whole history <strong>(used in this memo)</strong>" in off and "drift_action to ignore" in off
    only = read("memo_P-003c.html")
    assert "Comps opened from 2022-04-12 only <strong>(used in this memo)</strong>" in only
    assert "uses only the 26 selected comps opened from that date; 15 older ones are left out" in only


# ---- measured on other seeds ----------------------------------------------------------------

def _committed(root, name):
    with open(os.path.join(root, "output", name), encoding="utf-8") as fh:
        return json.load(fh)


def test_generator_can_plant_a_gradual_drift_without_touching_the_default():
    world = synth.generate(5, drift_per_year=0.12)
    plain = synth.generate(5, drift_factor=1.0)
    hours = lambda w: sum(e["tenths"] for e in w["entries"]
                          if e["matter"] in {m["id"] for m in w["matters"] if m["type"] == synth.DRIFT_TYPE})
    assert hours(world) > hours(plain) * 1.2
    assert synth.DRIFT_FACTOR == 1.7
    assert sensitivity.parse_seeds("1-3,7") == (1, 2, 3, 7)


def test_committed_drift_study_states_what_was_and_was_not_reached(root):
    """Evaluation seeds 1 to 20. The 18 of 20 aim is met at 2.0x and missed at 1.7x; this pins the miss."""
    study = _committed(root, "drift_sensitivity.json")
    assert study["seeds"] == list(range(1, 21)) and study["alpha"] == [1, 20] == study["shipped_alpha"]
    rows = {r["condition"]: r for r in study["rows"]}
    order = ["1.0x (none)", "1.3x", "1.5x", "1.7x", "2.0x", "gradual 12% a year"]
    assert [rows[k]["new_flagged"] for k in order] == [0, 5, 11, 13, 19, 10]
    assert [rows[k]["old_flagged"] for k in order] == [0, 1, 6, 11, 14, 4]
    u = study["no_planted_shift"]
    assert (u["new_flagged"], u["new_judged"], u["old_flagged"], u["old_judged"]) == (15, 220, 1, 220)
    for k in order[1:]:                                   # acting on it lowers the planted type's overruns
        assert rows[k]["drift_type_planning"]["over_p90"] * 2 < rows[k]["drift_type_descriptive"]["over_p90"] + 20
        assert rows[k]["drift_type_planning"]["over_p75"] < rows[k]["drift_type_descriptive"]["over_p75"]


def test_one_drift_study_run_reproduces_the_committed_row(ws, root):
    study = _committed(root, "drift_sensitivity.json")
    committed = [r for r in study["rows"] if r["condition"] == "2.0x"][0]["runs"][0]
    run = sensitivity.one_run(1, ws.code_map, ws.rate_card, step="2.0")
    assert run["seed"] == committed["seed"] == 1
    assert (run["new_flagged"], run["old_flagged"]) == (committed["new_flagged"], committed["old_flagged"])
    assert run["change_date"].isoformat() == committed["change_date"]
    assert run["drift_type_planning"] == committed["drift_type_planning"]


def test_committed_calibration_study_and_one_live_seed(ws, root):
    study = _committed(root, "calibration_study.json")
    assert study["seeds"] == list(range(1, 21)) and study["min_history"] == bands.MIN_CAL_HISTORY == 12
    t = study["total"]
    assert (t["descriptive"]["over_p75"], t["descriptive"]["over_p90"], t["descriptive"]["n"]) == (2220, 1096, 7490)
    assert (t["planning"]["over_p75"], t["planning"]["over_p90"], t["planning"]["n"]) == (1678, 552, 7490)
    u = study["unplanted_flags"]                           # a flag on an unplanted type never lowered a figure
    assert u["flagged_predictions"] == 384 and u["said_costs_fell"] == 139
    assert u["p90_below_whole_history"] == 0 and u["any_band_below_whole_history"] == 0
    assert (t["descriptive"]["types_more_p90"], t["planning"]["types_more_p90"]) == (51, 2)
    for r in study["runs"]:                               # every seed: planning P90 overruns at or under 10 percent
        assert r["planning"]["over_p90"] * 10 <= r["planning"]["n"]
        assert r["planning"]["over_p90"] < r["descriptive"]["over_p90"]
    live = sensitivity.calibration_run(3, ws.code_map, ws.rate_card)
    committed = [r for r in study["runs"] if r["seed"] == 3][0]
    assert (live["planning"]["over_p90"], live["planning"]["n"]) == (27, 374)
    assert live["unplanted_flags"]["any_band_below_whole_history"] == 0
    assert live["planning"] == committed["planning"] and live["descriptive"] == committed["descriptive"]


def test_readme_numbers_match_the_committed_outputs(root, bt):
    """The README quotes measurements; each one checked here comes from a committed output or a live run."""
    with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    _records, summary, _table = bt
    for r in summary["by_type"]:
        if r["n_tested"]:
            d, o = r["descriptive"]["overruns"], r["overruns"]
            line = "| %s | %s | %s |" % (r["matter_type"], "%d of %d (about %d)" % (d["p75"]["count"], d["p75"]["n"], d["p75"]["implied_count"]),
                                         "%d of %d (about %d)" % (d["p90"]["count"], d["p90"]["n"], d["p90"]["implied_count"]))
            assert line in readme, r["matter_type"]
            assert "| %d of %d (about %d) | %d of %d (about %d) |" % (
                o["p75"]["count"], o["p75"]["n"], o["p75"]["implied_count"],
                o["p90"]["count"], o["p90"]["n"], o["p90"]["implied_count"]) in readme, r["matter_type"]
    cal = _committed(root, "calibration_study.json")
    for name in ("descriptive", "finite_sample_only", "planning"):
        t = cal["total"][name]
        assert "%s of 7,490" % format(t["over_p90"], ",") in readme and "%s of 7,490" % format(t["over_p75"], ",") in readme
    for r in cal["runs"]:
        pct = (Decimal(r["planning"]["over_p90"]) * 100 / r["planning"]["n"]).quantize(Decimal("0.1"))
        assert "| %s%% |" % pct in readme or "| %s%% " % pct in readme, r["seed"]
    study = _committed(root, "drift_sensitivity.json")
    label = {"1.0x (none)": "nothing (1.0x)", "1.3x": "1.3x step", "1.5x": "1.5x step", "1.7x": "1.7x step",
             "2.0x": "2.0x step", "gradual 12% a year": "gradual, 12% a year"}
    for r in study["rows"]:
        assert "| %s | %d of 20 | %d of 20 | %d of %d (" % (label[r["condition"]], r["old_flagged"], r["new_flagged"],
                                                           r["new_other_flagged"], r["new_other_judged"]) in readme
    for alpha, name in (("1 in 50", "1_50"), ("1 in 20 (shipped)", "1_20"), ("1 in 10", "1_10")):
        with open(os.path.join(root, "output", "tuning", "drift_seeds_101_120_alpha_%s.json" % name), encoding="utf-8") as fh:
            tune = json.load(fh)
        rows = {r["condition"]: r for r in tune["rows"]}
        u = tune["no_planted_shift"]
        assert "| %s | %d of 20 | %d of 20 | %d of %d (" % (alpha, rows["1.7x"]["new_flagged"], rows["2.0x"]["new_flagged"],
                                                           u["new_flagged"], u["new_judged"]) in readme
