import copy
import json
import os
from datetime import date
from decimal import Decimal

import pytest

from feemodel.loader import MappingError, level_at, load_cost_rates, load_dataset, load_mapping, load_rate_card
from feemodel.money import ZERO

MAPPING = {
    "name": "tiny",
    "tables": {
        "matters": {"file": "m.csv", "date_format": "%d.%m.%Y",
                    "columns": {"matter_id": "No", "matter_type": "Kind", "status": "St", "open_date": "From",
                                "close_date": "To", "close_reason": "Why"},
                    "value_maps": {"status": {"X": "closed", "L": "open"}}},
        "time_entries": {"file": "t.csv", "date_format": "%d.%m.%Y",
                         "columns": {"entry_id": "Id", "matter_id": "No", "timekeeper_id": "Who", "work_date": "Day",
                                     "hours_worked": "Mins", "rate": "Rate", "level": "Grade"},
                         "scale": {"hours_worked": {"divide_by": "60"}}},
        "invoices": {"file": "i.csv", "date_format": "%d.%m.%Y",
                     "columns": {"invoice_id": "Inv", "matter_id": "No", "invoice_date": "Day",
                                 "amount_billed": "Billed", "amount_collected": "Paid"}},
    },
}


def write_tiny(tmp_path, matters=None, entries=None, invoices=None):
    (tmp_path / "m.csv").write_text(matters or "No,Kind,St,From,To,Why\nA1,lease,X,01.02.2021,01.05.2021,completed\n")
    (tmp_path / "t.csv").write_text(entries or "Id,No,Who,Day,Mins,Rate,Grade\nT1,A1,K1,03.02.2021,90,$300.00,associate\n")
    (tmp_path / "i.csv").write_text(invoices or "Inv,No,Day,Billed,Paid\nI1,A1,01.03.2021,\"$1,000.00\",$900.00\n")
    return str(tmp_path)


def test_mapping_renames_rescales_and_translates(tmp_path):
    ds = load_dataset(write_tiny(tmp_path), MAPPING)
    assert not ds.issues
    m = ds.matters["A1"]
    assert (m.status, m.open_date, m.close_date) == ("closed", date(2021, 2, 1), date(2021, 5, 1))
    e = ds.entries[0]
    assert e.hours_worked == Decimal("1.5")           # 90 minutes
    assert e.rate == Decimal("300.00")                # "$300.00"
    assert e.amount_worked == Decimal("450.000")
    assert ds.invoices[0].amount_billed == Decimal("1000.00")


def test_missing_billed_hours_assumed_and_flagged(tmp_path):
    ds = load_dataset(write_tiny(tmp_path), MAPPING)
    assert ds.entries[0].hours_billed == ds.entries[0].hours_worked
    assert ds.entries[0].billed_assumed is True


def test_bad_date_is_reported_not_raised(tmp_path):
    path = write_tiny(tmp_path, entries="Id,No,Who,Day,Mins,Rate,Grade\nT1,A1,K1,2021-02-03,90,300,associate\n")
    ds = load_dataset(path, MAPPING)
    assert ds.entries == []
    codes = {(i.code, i.field) for i in ds.issues}
    assert ("parse_error", "work_date") in codes
    assert ds.blocking_issues()


def test_unmapped_coded_value_is_reported(tmp_path):
    path = write_tiny(tmp_path, matters="No,Kind,St,From,To,Why\nA1,lease,Q,01.02.2021,01.05.2021,completed\n")
    ds = load_dataset(path, MAPPING)
    assert "A1" not in ds.matters
    assert any("value_maps" in i.problem for i in ds.issues)


def test_missing_required_column_blocks_table(tmp_path):
    mapping = copy.deepcopy(MAPPING)
    mapping["tables"]["time_entries"]["columns"]["rate"] = "NoSuchColumn"
    ds = load_dataset(write_tiny(tmp_path), mapping)
    assert ds.entries == []
    assert ds.table_info["time_entries"]["missing_required"] == ["rate"]
    assert any(i.code == "missing_column" and i.blocking for i in ds.issues)


def test_missing_file_reported(tmp_path):
    path = write_tiny(tmp_path)
    os.remove(os.path.join(path, "i.csv"))
    ds = load_dataset(path, MAPPING)
    assert any(i.code == "missing_table" and i.table == "invoices" and i.blocking for i in ds.issues)


def test_orphans_duplicates_and_negatives_dropped(tmp_path):
    entries = ("Id,No,Who,Day,Mins,Rate,Grade\nT1,A1,K1,03.02.2021,90,300,associate\n"
               "T1,A1,K1,04.02.2021,60,300,associate\nT2,ZZ,K1,04.02.2021,60,300,associate\n"
               "T3,A1,K1,04.02.2021,-60,300,associate\n")
    ds = load_dataset(write_tiny(tmp_path, entries=entries), MAPPING)
    assert [e.entry_id for e in ds.entries] == ["T1"]
    assert {i.code for i in ds.issues} == {"duplicate_id", "orphan_row", "negative_value"}


def test_close_before_open_rejected(tmp_path):
    path = write_tiny(tmp_path, matters="No,Kind,St,From,To,Why\nA1,lease,X,01.06.2021,01.05.2021,completed\n")
    ds = load_dataset(path, MAPPING)
    assert "A1" not in ds.matters
    assert any(i.code == "close_before_open" for i in ds.issues)


def test_mapping_file_validation(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"tables": {"matters": {"file": "m.csv", "columns": {"not_a_field": "x"}}}}))
    with pytest.raises(MappingError):
        load_mapping(str(bad))
    bad.write_text(json.dumps({"nothing": 1}))
    with pytest.raises(MappingError):
        load_mapping(str(bad))


def test_level_history_lookup():
    history = [(None, "associate"), (date(2022, 7, 1), "senior_associate")]
    assert level_at(history, date(2022, 6, 30)) == "associate"
    assert level_at(history, date(2022, 7, 1)) == "senior_associate"
    assert level_at([], date(2022, 7, 1)) is None


def test_two_export_shapes_load_to_the_same_canonical_data(ws, ws_b):
    a, b = ws.dataset, ws_b.dataset
    assert not a.issues and not b.issues
    assert a.matters == b.matters
    key = lambda e: e.entry_id
    assert sorted(a.entries, key=key) == sorted(b.entries, key=key)
    assert sorted(a.invoices, key=lambda i: i.invoice_id) == sorted(b.invoices, key=lambda i: i.invoice_id)
    assert sum((e.amount_worked for e in a.entries), ZERO) == sum((e.amount_worked for e in b.entries), ZERO)


def test_loaded_money_and_hours_are_decimal_never_float(ws_b):
    for e in ws_b.dataset.entries[:500]:
        for value in (e.hours_worked, e.hours_billed, e.rate, e.amount_worked, e.amount_billed):
            assert isinstance(value, Decimal)
    for inv in ws_b.dataset.invoices[:200]:
        assert isinstance(inv.amount_billed, Decimal) and isinstance(inv.amount_collected, Decimal)


def test_rate_files_reject_floats(tmp_path):
    p = tmp_path / "rates.json"
    p.write_text(json.dumps({"current": {"partner": 650.5}}))
    with pytest.raises(MappingError):
        load_rate_card(str(p))
    p.write_text(json.dumps({"cost_per_hour": {"partner": 230.0}}))
    with pytest.raises(MappingError):
        load_cost_rates(str(p))
    p.write_text(json.dumps({"cost_per_hour": {"partner": "230.00"}}))
    assert load_cost_rates(str(p)) == {"partner": Decimal("230.00")}
