import datetime as dt
import os
from decimal import Decimal

import pytest

from billcheck import readers
from billcheck.readers import LEDES_FIELDS, ReaderError
from billcheck.writers import write_csv, write_ledes
from conftest import DATA, mk_expense, mk_invoice, mk_line

D = Decimal


def sample(name):
    with open(os.path.join(DATA, "invoices", name), "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def small_ledes(**changes):
    inv = mk_invoice([mk_line(1), mk_expense(2)])
    text = write_ledes([inv])
    for old, new in changes.items():
        text = text.replace(old, new)
    return text


def test_ledes_field_list_is_the_24_documented_fields():
    assert len(LEDES_FIELDS) == 24
    assert LEDES_FIELDS[0] == "INVOICE_DATE" and LEDES_FIELDS[-1] == "CLIENT_MATTER_ID"


def test_ledes_sample_file_reads_into_model():
    (inv,) = readers.read_ledes(sample("INV-Q-1001.ledes.txt"))
    assert inv.invoice_id == "INV-Q-1001" and inv.client_id == "quillfeather"
    assert inv.invoice_date == dt.date(2026, 11, 5)
    assert len(inv.lines) == 42
    assert {ln.kind for ln in inv.lines} == {"fee", "expense"}
    first_fee = inv.fee_lines[0]
    assert first_fee.timekeeper_id and first_fee.task_code.startswith("L")
    # LEDES 1998B has no receipt, cost or AI field
    assert all(ln.receipt is None and ln.cost is None and ln.ai_assisted is None for ln in inv.lines)


def test_ledes_round_trip_preserves_every_field():
    inv = mk_invoice([mk_line(1, hours="2.3", rate="415"), mk_expense(2, amount="86.25")])
    (back,) = readers.read_ledes(write_ledes([inv]))
    assert back.declared_total == inv.declared_total
    for a, b in zip(inv.lines, back.lines):
        assert (a.line_no, a.kind, a.date, a.units, a.rate, a.amount, a.narrative, a.task_code, a.activity_code, a.expense_code) == (
            b.line_no, b.kind, b.date, b.units, b.rate, b.amount, b.narrative, b.task_code, b.activity_code, b.expense_code)


def test_csv_round_trip_preserves_optional_columns():
    inv = mk_invoice([mk_line(1, ai_assisted=True), mk_expense(2, receipt=False, cost=D("80.00"))])
    (back,) = readers.read_csv(write_csv([inv]))
    assert back.lines[0].ai_assisted is True
    assert back.lines[1].receipt is False and back.lines[1].cost == D("80.00")
    assert back.lines[0].receipt is None


def test_ledes_requires_first_line():
    with pytest.raises(ReaderError, match="first record"):
        readers.read_ledes(small_ledes(**{"LEDES1998B[]": "LEDES1998BI[]"}))


def test_ledes_rejects_changed_header():
    with pytest.raises(ReaderError, match="header"):
        readers.read_ledes(small_ledes(**{"TIMEKEEPER_NAME": "TK_NAME"}))


def test_ledes_rejects_wrong_field_count_and_names_the_record():
    text = small_ledes(**{"|AS|": "|AS|extra|"})
    with pytest.raises(ReaderError, match=r"record 3 has 25 fields"):
        readers.read_ledes(text)


def test_ledes_rejects_bad_date():
    with pytest.raises(ReaderError, match="YYYYMMDD"):
        readers.read_ledes(small_ledes(**{"20261006": "2026-10-06"}))


def test_ledes_rejects_missing_terminator_on_last_record():
    text = small_ledes().rstrip()
    assert text.endswith("[]")
    with pytest.raises(ReaderError, match="does not end"):
        readers.read_ledes(text[:-2])


def test_ledes_tolerates_line_break_inside_a_record():
    text = small_ledes(**{"Draft responses to second": "Draft responses\r\n to second"})
    (inv,) = readers.read_ledes(text)
    assert inv.lines[0].narrative == "Draft responses to second set of interrogatories"


def test_ledes_rejects_unknown_line_type():
    with pytest.raises(ReaderError, match="unknown line type"):
        readers.read_ledes(small_ledes(**{"|1|F|": "|1|X|"}))


def test_csv_missing_column_is_named():
    text = write_csv([mk_invoice([mk_line(1)])]).replace("narrative", "description")
    with pytest.raises(ReaderError, match="narrative"):
        readers.read_csv(text)


def test_csv_rejects_number_with_thousands_separator():
    text = write_csv([mk_invoice([mk_line(1, hours="4", rate="300")])]).replace(",1200.00,", ',"1,200.00",')
    with pytest.raises(ReaderError, match="not a number"):
        readers.read_csv(text)


def test_csv_without_optional_columns_reads_unknowns_as_none():
    header = "invoice_id,invoice_date,client_id,matter_id,invoice_total,billing_start,billing_end,line_no,kind,date,timekeeper_id,timekeeper_name,classification,units,rate,amount,task_code,activity_code,expense_code,narrative\n"
    row = "I1,2026-11-05,c,m,120.00,,,1,fee,2026-10-02,TK1,A Person,AS,0.4,300,120.00,L110,A104,,Review lease\n"
    (inv,) = readers.read_csv(header + row)
    ln = inv.lines[0]
    assert ln.receipt is None and ln.cost is None and ln.ai_assisted is None and ln.adjustment == 0
    assert inv.billing_start is None


def test_format_detection():
    assert readers.detect_format(sample("INV-Q-1001.ledes.txt")) == "ledes"
    assert readers.detect_format(sample("INV-Q-1002.csv")) == "csv"
    assert len(readers.read_invoice_text(sample("INV-Q-1002.csv"))[0].lines) == 24


def test_file_with_two_invoices_is_grouped():
    a = mk_invoice([mk_line(1)])
    b = mk_invoice([mk_line(1), mk_line(2, narrative="Review lease")])
    b.invoice_id = "INV-T-2"
    invoices = readers.read_ledes(write_ledes([a, b]))
    assert [(i.invoice_id, len(i.lines)) for i in invoices] == [("INV-T-1", 1), ("INV-T-2", 2)]


def test_inconsistent_invoice_total_between_lines_is_an_error():
    text = write_csv([mk_invoice([mk_line(1), mk_line(2, narrative="Review lease")])])
    rows = text.split("\n")
    rows[2] = rows[2].replace(",720.00,", ",721.00,", 1)
    with pytest.raises(ReaderError, match="declared_total differs"):
        readers.read_csv("\n".join(rows))


def test_repeated_line_number_is_an_error():
    text = write_csv([mk_invoice([mk_line(1), mk_line(1, narrative="Review lease")])])
    with pytest.raises(ReaderError, match="repeated"):
        readers.read_csv(text)


def test_arithmetic_line_mismatch_is_reported_with_difference():
    inv = mk_invoice([mk_line(1, hours="0.9", rate="110", amount="109.00")])
    (issue,) = readers.validate_arithmetic(inv)
    assert issue["scope"] == "line" and issue["line_no"] == 1
    assert issue["expected"] == D("99.00") and issue["difference"] == D("10.00")


def test_arithmetic_allows_one_cent_but_not_two():
    ok = mk_invoice([mk_line(1, hours="0.3", rate="333.33", amount="100.00")])  # exact 99.999
    assert readers.validate_arithmetic(ok) == []
    one_cent = mk_invoice([mk_line(1, hours="1", rate="100", amount="100.01")])
    assert readers.validate_arithmetic(one_cent) == []
    two_cents = mk_invoice([mk_line(1, hours="1", rate="100", amount="100.02")])
    assert len(readers.validate_arithmetic(two_cents)) == 1


def test_arithmetic_total_mismatch_is_reported():
    inv = mk_invoice([mk_line(1), mk_line(2, narrative="Review lease")], total="800.00")
    (issue,) = readers.validate_arithmetic(inv)
    assert issue["scope"] == "invoice" and issue["expected"] == D("720.00") and issue["difference"] == D("80.00")


def test_adjustment_is_part_of_line_arithmetic():
    line = mk_line(1, hours="2", rate="300", amount="550.00")
    line.adjustment = D("-50.00")
    assert readers.validate_arithmetic(mk_invoice([line])) == []
