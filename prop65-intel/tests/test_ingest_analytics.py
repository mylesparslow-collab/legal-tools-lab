import csv
from pathlib import Path
import pytest
from prop65 import ingest, analytics

H = ingest.EXPECTED_HEADER


def write(tmp_path, rows):
    p = tmp_path / "x.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL); w.writerow(H)
        for r in rows:
            w.writerow(r)
    return p


def row(ag, party="Fictional Watch", atty="Example Firm, APC.", seg="", pen="", fee="", oth="", docket="", chem="Lead", src="Seaweed Snack", date="01/05/2024"):
    return [ag, date, party, atty, "Fictional Defendant Inc.", chem, src, "", seg, "Case" if seg else "", docket, pen, fee, oth, "", "", ""]


def test_dedup_rules(tmp_path):
    rows = [
        row("2024-00001", seg="Settlement 100", pen="1000", fee="9000", oth="0", docket="24CV1"),
        row("2024-00001", seg="Judgment 50", pen="1000", fee="9000", oth="0", docket="24CV1"),      # court entering the same deal
        row("2024-00002", seg="Settlement 101", pen="1000", fee="9000", oth="0", docket="24CV1"),   # same deal reported under an amended notice
        row("2024-00003", seg="Settlement 400", pen="1000", fee="9000", oth="0", docket="24CV1"),   # far-apart report id: a different deal
        row("2024-00004", seg="Complaint 7"),
        row("2024-00005"),
    ]
    notices, res = ingest.load([write(tmp_path, rows)])
    assert len(notices) == 5 and len(res) == 2
    merged = next(r for r in res if len(r["ag_numbers"]) == 2)
    assert merged["court_entered"] and merged["total"] == 10000


def test_large_global_settlement_counted_once(tmp_path):
    rows = [row(f"2025-0000{i}", seg=f"Settlement {i*500}", pen="500000", fee="1500000", oth="0", docket="CGC-25-1") for i in range(1, 4)]
    _, res = ingest.load([write(tmp_path, rows)])
    assert len(res) == 1 and len(res[0]["ag_numbers"]) == 3


def test_header_change_is_an_error(tmp_path):
    p = tmp_path / "bad.csv"; p.write_text('"AG Number","Date"\n"2024-00001","01/01/2024"\n')
    with pytest.raises(ValueError):
        ingest.read_rows([p])


def test_keys_and_classes():
    assert ingest.firm_key("Manning Law, APC.") == ingest.firm_key("Manning Law APC") == "manning law"
    assert ingest.firm_key("Evan J. Smith") == ingest.firm_key("Evan Smith")
    assert ingest.split_chemicals("Cadmium, Lead and lead compounds") == ["Cadmium", "Lead"]
    assert ingest.split_chemicals("Di(2-ethylhexyl)phthalate (DEHP)") == ["DEHP"]
    assert ingest.product_class("Roasted Seaweed Snack") == "seafood"
    assert ingest.product_class("Thermal Receipt Paper") == "receipt_paper"
    assert ingest.product_class("zzz") == "other"


def test_percentiles_match_inclusive_method():
    v = [10, 20, 30, 40]
    assert analytics.percentile(v, .5) == 25 and analytics.percentile(v, .25) == 17.5 and analytics.percentile(v, .75) == 32.5
    assert analytics.percentile([], .5) is None and analytics.percentile([7], .25) == 7


def test_summary_excludes_zero_payments_and_flags_thin():
    res = [{"total": t, "civil_penalty": t * .1, "attorney_fees": t * .9, "other_payments": 0, "litigated": False} for t in (0, 10000, 20000)]
    s = analytics.summarize(res)
    assert s["n_paid"] == 2 and s["n_zero"] == 1 and s["thin_sample"] and s["total_p50"] == 15000 and s["fee_share"] == pytest.approx(.9)


DATA = sorted((Path(__file__).resolve().parent.parent / "data").glob("oag_60day_notices_*.csv.gz"))


@pytest.mark.skipif(not DATA, reason="OAG data file not present")
def test_real_export_loads_and_is_sane():
    notices, res = ingest.load(DATA)
    assert len(notices) > 25000 and 5000 < len(res) < sum(len(n.events) for n in notices.values())
    s = analytics.summarize(res)
    assert 5000 <= s["total_p50"] <= 100000 and s["total_p25"] <= s["total_p50"] <= s["total_p75"]
    assert abs(s["fee_share"] + s["penalty_share"] + s["other_share"] - 1) < 1e-9
