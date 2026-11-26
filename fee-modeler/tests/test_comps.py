import pytest

from feemodel.comps import InsufficientComps, SelectionRules, require_min, select_comps
from helpers import d, mk_dataset, mk_matter

AS_OF = d("2024-01-01")


def pool():
    return mk_dataset([
        mk_matter("C1", forum="court", num_parties=2, amount_band="B", num_units=1, hearing_occurred=True),
        mk_matter("C2", forum="court", num_parties=3, amount_band="C", num_units=2, hearing_occurred=False),
        mk_matter("C3", forum="agency", num_parties=6, amount_band="D", num_units=5, hearing_occurred=False),
        mk_matter("C4", forum="court", num_parties=2, amount_band="A", num_units=1, hearing_occurred=False,
                  open_="2018-01-01", close="2018-06-30"),
        mk_matter("S1", forum="court", num_parties=2, amount_band="B", reason="settled_early"),
        mk_matter("T1", forum="court", num_parties=2, amount_band="B", reason="transferred"),
        mk_matter("O1", forum="court", num_parties=2, amount_band="B", status="open", close=None, reason=None),
        mk_matter("L1", forum="court", num_parties=2, amount_band="B", open_="2023-06-01", close="2024-01-01"),
        mk_matter("X1", mtype="other_type", forum="court", num_parties=2, amount_band="B"),
    ])


ATTRS = {"forum": "court", "num_parties": 2, "amount_band": "B", "hearing_expected": True}


def ids(sel):
    return sorted(m.matter_id for m in sel.included)


def test_type_only_rules_exclude_open_abnormal_and_other_types():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(), AS_OF)
    assert ids(sel) == ["C1", "C2", "C3", "C4"]
    reasons = {m.matter_id: r for m, r in sel.excluded}
    assert reasons["O1"] == ["open matter"]
    assert reasons["S1"] == ["abnormal close excluded"] and reasons["T1"] == ["abnormal close excluded"]
    assert "X1" not in reasons and sel.type_total == 8


def test_as_of_is_strict_a_matter_closing_that_day_is_not_a_comp():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(), AS_OF)
    assert dict((m.matter_id, r) for m, r in sel.excluded)["L1"] == ["closed on or after the as-of date"]
    later = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(), d("2024-01-02"))
    assert "L1" in ids(later)


def test_include_abnormal_adds_them_with_a_flag():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(include_abnormal=True), AS_OF)
    assert {"S1", "T1"} <= set(ids(sel))
    assert sel.flags["S1"] == ["closed abnormally: settled_early"]
    assert sel.flags["C1"] == []
    assert "O1" not in ids(sel)         # open matters stay out whatever the rules say


def test_forum_rule():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(forum="same"), AS_OF)
    assert ids(sel) == ["C1", "C2", "C4"]


def test_parties_tolerance_rule():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(num_parties_tolerance=1), AS_OF)
    assert ids(sel) == ["C1", "C2", "C4"]
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(num_parties_tolerance=0), AS_OF)
    assert ids(sel) == ["C1", "C4"]


def test_amount_band_same_and_adjacent():
    same = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(amount_band="same"), AS_OF)
    assert ids(same) == ["C1"]
    adj = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(amount_band="adjacent"), AS_OF)
    assert ids(adj) == ["C1", "C2", "C4"]      # A and C are next to B; D is not


def test_units_range_hearing_and_recency_rules():
    assert ids(select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(num_units_range=[2, 5]), AS_OF)) == ["C2", "C3"]
    assert ids(select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(hearing="same"), AS_OF)) == ["C1"]
    assert ids(select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(closed_within_years=3), AS_OF)) == ["C1", "C2", "C3"]


def test_refuses_below_minimum_and_says_what_is_needed():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(forum="same", min_comps=5), AS_OF)
    with pytest.raises(InsufficientComps) as exc:
        require_min(sel)
    msg = str(exc.value)
    assert "3 comparable closed matters" in msg and "5 required" in msg and "2 more are needed" in msg
    assert "different forum (+1)" in msg and "abnormal close excluded (+2)" in msg
    assert exc.value.selection is sel


def test_at_minimum_passes():
    sel = select_comps(pool(), "widget_dispute", ATTRS, SelectionRules(min_comps=4), AS_OF)
    assert require_min(sel) is sel


def test_rules_are_visible_as_plain_sentences():
    rules = SelectionRules(forum="same", num_parties_tolerance=1, amount_band="adjacent", closed_within_years=3)
    lines = rules.describe("widget_dispute", ATTRS, AS_OF)
    text = " ".join(lines)
    assert "Matter type is widget_dispute." in lines
    assert "Same forum as proposed (court)." in lines
    assert "within 1 of proposed (2)" in text and "A < B < C < D" in text
    assert "At least 8 comps are required" in text and "excluded" in text


def test_rules_from_dict_reject_typos():
    assert SelectionRules.from_dict(None).min_comps == 8
    assert SelectionRules.from_dict({"forum": "same"}).forum == "same"
    for bad in ({"forums": "same"}, {"forum": "similar"}, {"amount_band": "near"}, {"min_comps": 0}):
        with pytest.raises(ValueError):
            SelectionRules.from_dict(bad)


def test_open_matters_are_never_comps_in_the_synthetic_data(ws):
    for mtype in {m.matter_type for m in ws.dataset.matters.values()}:
        sel = select_comps(ws.dataset, mtype, {}, SelectionRules(include_abnormal=True), d("2030-01-01"))
        assert all(m.status == "closed" and m.close_date is not None for m in sel.included)
