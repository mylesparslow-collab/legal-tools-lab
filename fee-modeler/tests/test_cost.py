from decimal import Decimal

import pytest

from feemodel.cost import CostBook, TaskCodeMap, assign_phase, build_cost, fallback_phase, parse_reductions
from helpers import CODE_MAP, COSTS, RATES, d, mk_dataset, mk_entry, mk_invoice, mk_matter

D = Decimal


def test_task_code_map_exact_beats_prefix_and_unknown_is_none():
    cm = TaskCodeMap(exact={"DR99": "hearing"}, prefixes={"DR": "drafting", "D": "discovery"})
    assert cm.phase_for("DR99") == "hearing"
    assert cm.phase_for("DR10") == "drafting"       # longest prefix
    assert cm.phase_for("D7") == "discovery"
    assert cm.phase_for("ZZ99") is None and cm.phase_for("") is None
    with pytest.raises(ValueError):
        TaskCodeMap(prefixes={"X": "not_a_phase"})


def test_date_window_fallback_boundaries():
    m = mk_matter("M", open_="2021-01-01", close="2021-04-11")   # 100 days
    assert fallback_phase(d("2021-01-01"), m) == "assessment"
    assert fallback_phase(d("2021-01-15"), m) == "assessment"    # day 14
    assert fallback_phase(d("2021-01-16"), m) == "drafting"      # day 15
    assert fallback_phase(d("2021-02-15"), m) == "discovery"     # day 45
    assert fallback_phase(d("2021-03-22"), m) == "closing"       # day 80
    assert fallback_phase(d("2021-05-30"), m) == "closing"       # after close: clamped


def test_fallback_uses_hearing_date_window():
    m = mk_matter("M", open_="2021-01-01", close="2021-04-11", hearing_date=d("2021-03-01"))
    assert fallback_phase(d("2021-02-20"), m) == "hearing"       # 9 days before
    assert fallback_phase(d("2021-02-01"), m) == "drafting"      # 28 days before: outside the window
    assert fallback_phase(d("2021-03-02"), m) == "discovery"     # after the hearing


def test_phase_source_and_low_confidence_flag():
    m = mk_matter("M")
    coded = mk_entry("1", "M", "2021-03-01", 8, code="HR10")
    blank = mk_entry("2", "M", "2021-01-05", 2, code=None)
    unknown = mk_entry("3", "M", "2021-01-05", 1, code="ZZ99")
    assert assign_phase(coded, m, CODE_MAP) == ("hearing", "task_code")
    assert assign_phase(blank, m, CODE_MAP) == ("assessment", "date_window")
    assert assign_phase(unknown, m, CODE_MAP)[1] == "date_window"
    mc = build_cost(m, [coded, blank], [], CODE_MAP)
    assert mc.fallback_share == D("0.2") and mc.phase_confidence == "task_code"        # exactly 20% is still ok
    mc = build_cost(m, [coded, blank, unknown], [], CODE_MAP)
    assert mc.phase_confidence == "date_window"


def test_raw_normalized_and_internal_cost_by_hand():
    m = mk_matter("M")
    entries = [mk_entry("1", "M", "2021-02-01", "10.0", rate="300", level="associate", code="DR10"),
               mk_entry("2", "M", "2021-02-02", "2.5", rate="450", level="partner", code="AS10")]
    mc = build_cost(m, entries, [], CODE_MAP)
    assert mc.raw_worked == D("4125")                      # 10 x 300 + 2.5 x 450
    assert mc.value_total(RATES) == D("5500")              # 10 x 400 + 2.5 x 600 at today's card
    assert mc.value_total(COSTS) == D("1500")              # 10 x 100 + 2.5 x 200
    assert mc.value_by_phase(RATES)["drafting"] == D("4000")
    assert mc.hours_by_level() == {"associate": D("10.0"), "partner": D("2.5")}
    assert mc.phases_occurred() == {"drafting", "assessment"}


def test_write_downs_and_uncollected_shown_separately():
    m = mk_matter("M")
    entries = [mk_entry("1", "M", "2021-02-01", 10, rate="300", billed=8)]
    invoices = [mk_invoice("I1", "M", "2021-03-01", "2400", "2000", "400")]
    mc = build_cost(m, entries, invoices, CODE_MAP)
    assert mc.raw_worked == D("3000") and mc.raw_billed == D("2400")
    assert mc.write_down == D("600")
    assert mc.collected == D("2000") and mc.uncollected == D("400") and mc.written_off == D("400")


def test_missing_level_rate_is_an_error_not_a_guess():
    m = mk_matter("M")
    mc = build_cost(m, [mk_entry("1", "M", "2021-02-01", 1, level="of_counsel")], [], CODE_MAP)
    with pytest.raises(KeyError):
        mc.value_total(RATES)


def test_as_of_ignores_later_entries_and_invoices():
    m = mk_matter("M")
    entries = [mk_entry("1", "M", "2021-02-01", 10), mk_entry("2", "M", "2021-09-01", 5)]
    invoices = [mk_invoice("I1", "M", "2021-03-01", "3000", "3000"), mk_invoice("I2", "M", "2021-10-01", "1500", "1500")]
    book = CostBook(mk_dataset([m], entries, invoices), CODE_MAP)
    assert book.cost("M").total_hours == D("15")
    early = book.cost_as_of("M", d("2021-08-31"))
    assert early.total_hours == D("10") and early.invoiced == D("3000")
    assert book.cost_as_of("M", d("2022-01-01")) is book.cost("M")


def test_hours_reduction_applies_only_to_named_phase():
    m = mk_matter("M")
    entries = [mk_entry("1", "M", "2021-02-01", 10, code="DR10"), mk_entry("2", "M", "2021-01-02", 2, level="partner", code="AS10")]
    mc = build_cost(m, entries, [], CODE_MAP)
    red = parse_reductions({"drafting": "20"})
    assert mc.value_total(RATES) == D("5200")
    assert mc.value_total(RATES, red) == D("4400")          # 8 x 400 + 2 x 600
    assert mc.hours_by_phase(red)["assessment"] == D("2")
    assert mc.total_hours == D("12")                        # the record itself is untouched


def test_parse_reductions_validation_and_zero_default():
    assert parse_reductions(None) == {} and parse_reductions({}) == {}
    assert parse_reductions({"drafting": "0"}) == {}
    assert parse_reductions({"drafting": 25}) == {"drafting": D("0.25")}
    with pytest.raises(ValueError):
        parse_reductions({"drafting": "150"})
    with pytest.raises(ValueError):
        parse_reductions({"lunch": "10"})
    with pytest.raises(TypeError):
        parse_reductions({"drafting": 12.5})
