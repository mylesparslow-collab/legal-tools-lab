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


# ---- points checked against the publisher's LEDES 98B format page and sample file (read 2026-11-26)

# Same structure and numbers as the published sample file; names and descriptions are our own.
PUBLISHED_SHAPE = (
    "LEDES1998B[]\r\n"
    + "|".join(LEDES_FIELDS) + "[]\r\n"
    "19990225|96542|00711|0528|1684.45|19990101|19990131|For services rendered|1|F|2.00|-70|630|19990115|L510||A102|22547|Research on fee claim|24-0000001|350|Lastname, First|PARTNR|423-987[]\r\n"
    "19990225|96542|00711|0528|1684.45|19990101|19990131|For services rendered|2|F|2.00|0|700|19990115|L510||A102|22547|Research for trial pleading|24-0000001|350|Lastname, First|PARTNR|423-987[]\r\n"
    "19990225|96542|00711|0528|1684.45|19990101|19990131|For services rendered|3|F|0.200|0|40|19990116|L510||A107|45875|Telephone conference with co-counsel|24-0000001|200|Othername, Second|ASSOC|423-987[]\r\n"
    "19990225|96542|00711|0528|1684.45|19990101|19990131|For services rendered|4|E|1|0|24.95|19990117||E111|||Meals|24-0000001|24.95|||423-987[]\r\n"
    "19990225|96542|00711|0528|1684.45|19990101|19990131|For services rendered|5|E|1|0|289.5|19990117||E110|||Out-of-town travel|24-0000001|289.5|||423-987[]\r\n"
    "19990225|96543|00711|1326|1250|19990101|19990131|Monthly Retainer|6|IF|1|1250.|1250|19990131|||||Monthly retainer fee|24-0000001||||425-936[]\r\n"
)


def test_published_field_order_matches_reader():
    assert LEDES_FIELDS == [
        "INVOICE_DATE", "INVOICE_NUMBER", "CLIENT_ID", "LAW_FIRM_MATTER_ID", "INVOICE_TOTAL", "BILLING_START_DATE",
        "BILLING_END_DATE", "INVOICE_DESCRIPTION", "LINE_ITEM_NUMBER", "EXP/FEE/INV_ADJ_TYPE", "LINE_ITEM_NUMBER_OF_UNITS",
        "LINE_ITEM_ADJUSTMENT_AMOUNT", "LINE_ITEM_TOTAL", "LINE_ITEM_DATE", "LINE_ITEM_TASK_CODE", "LINE_ITEM_EXPENSE_CODE",
        "LINE_ITEM_ACTIVITY_CODE", "TIMEKEEPER_ID", "LINE_ITEM_DESCRIPTION", "LAW_FIRM_ID", "LINE_ITEM_UNIT_COST",
        "TIMEKEEPER_NAME", "TIMEKEEPER_CLASSIFICATION", "CLIENT_MATTER_ID",
    ]


def test_file_shaped_like_the_published_sample_reads_cleanly():
    first, second = readers.read_ledes(PUBLISHED_SHAPE)
    assert (first.invoice_id, len(first.lines), first.declared_total) == ("96542", 5, D("1684.45"))
    assert first.invoice_date == dt.date(1999, 2, 25) and first.billing_end == dt.date(1999, 1, 31)
    assert [ln.kind for ln in first.lines] == ["fee", "fee", "fee", "expense", "expense"]
    assert readers.validate_arithmetic(first) == []  # 2.00 x 350 - 70 = 630, and the lines sum to 1684.45
    assert readers.validate_arithmetic(second) == []


def test_published_sample_number_spellings_are_accepted():
    first, second = readers.read_ledes(PUBLISHED_SHAPE)
    assert first.lines[0].adjustment == D("-70") and first.lines[2].units == D("0.200")
    assert second.lines[0].adjustment == D("1250")  # written as "1250." in the sample


def test_invoice_level_fee_line_may_leave_unit_cost_and_timekeeper_blank():
    _, second = readers.read_ledes(PUBLISHED_SHAPE)
    (line,) = second.lines
    assert line.kind == "adjustment" and line.rate == 0 and line.timekeeper_id == "" and line.amount == D("1250")


def test_line_numbers_may_continue_across_invoices_in_one_file():
    _, second = readers.read_ledes(PUBLISHED_SHAPE)
    assert second.lines[0].line_no == 6


def test_header_record_must_end_with_terminator():
    broken = PUBLISHED_SHAPE.replace("CLIENT_MATTER_ID[]", "CLIENT_MATTER_ID", 1)
    with pytest.raises(ReaderError, match="header"):
        readers.read_ledes(broken)


def test_writer_output_has_the_published_first_line_header_and_terminators():
    text = write_ledes([mk_invoice([mk_line(1), mk_expense(2)])])
    records = text.split("\r\n")
    assert records[0] == "LEDES1998B[]"
    assert records[1] == "|".join(LEDES_FIELDS) + "[]"
    assert all(r.endswith("[]") and r.count("|") == 23 for r in records[1:-1])
    assert "|20261006|" in records[2]


def test_non_ascii_is_reported_on_read_and_refused_on_write():
    assert readers.ledes_format_warnings(PUBLISHED_SHAPE) == []
    odd = PUBLISHED_SHAPE.replace("Meals", "Café meals")
    (warning,) = readers.ledes_format_warnings(odd)
    assert "ASCII" in warning
    assert len(readers.read_ledes(odd)) == 2  # still read
    with pytest.raises(ValueError, match="ASCII"):
        write_ledes([mk_invoice([mk_line(1, narrative="Café meeting with client")])])
