"""Hand-computed checks of the density rules. Expected values were worked out on paper from the
statute tables, not produced by the engine."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import density as de

BASE = dict(site_acres=2.4, zoning_density_du_ac=40, sb4_applies=False, base_path="VLI", base_affordable_units=0,
            add_path="NONE", add_units=0, near_major_transit=False, share_0_1_br=1.0, share_2_3_br=0.0, share_4plus_br=0.0)
calc = lambda **k: de.calculate({**BASE, **k})


def test_base_units_round_up():
    assert calc(site_acres=1.01, zoning_density_du_ac=30)["base_units"] == 31       # 30.3 -> 31
    assert calc(site_acres=0.1, zoning_density_du_ac=30)["base_units"] == 3         # exactly 3, no float creep to 4
    assert calc()["base_units"] == 96


@pytest.mark.parametrize("path,units,pct,bonus", [
    ("VLI", 5, 20.0, 20),      # 5/96 = 5.2% -> 5% row -> 20% -> 19.2 -> 20
    ("VLI", 4, 0, 0),          # 4.1% is below the 5% minimum
    ("VLI", 15, 50.0, 48),     # 15.6% -> 15% row
    ("VLI", 40, 50.0, 48),     # table tops out at 50%
    ("LI", 10, 20.0, 20),      # 10.4% -> 10% row
    ("LI", 20, 35.0, 34),      # 20.8% -> 20% row: 33.6 -> 34
    ("LI", 21, 38.75, 38),     # 21.9% -> 21% row: 37.2 -> 38
    ("LI", 24, 50.0, 48),      # 25%
    ("MOD_SALE", 10, 5.0, 5),  # 4.8 -> 5
    ("MOD_SALE", 39, 35.0, 34),   # 40.6% -> 40% row
    ("MOD_SALE", 43, 50.0, 48),   # 44.8% -> 44% row
    ("STUDENT", 20, 35.0, 34),
])
def test_base_tables(path, units, pct, bonus):
    r = calc(base_path=path, base_affordable_units=units)
    assert (r["bonus_pct"], r["bonus_units"]) == (pct, bonus)


def test_additional_bonus_reaches_100_percent():
    r = calc(base_affordable_units=15, add_path="MOD", add_units=15)   # 15% VLI + 15% moderate
    assert (r["bonus_units"], r["add_bonus_units"], r["total_units"], r["total_bonus_pct_of_base"]) == (48, 48, 192, 100.0)


def test_additional_very_low_tops_out_at_38_75():
    r = calc(base_affordable_units=15, add_path="VLI", add_units=10)   # 10.4% -> 10% row -> 38.75% -> 37.2 -> 38
    assert (r["add_bonus_pct"], r["add_bonus_units"], r["total_units"]) == (38.75, 38, 182)
    assert calc(base_affordable_units=15, add_path="VLI", add_units=30)["add_bonus_pct"] == 38.75


def test_additional_bonus_needs_maximum_base_tier():
    r = calc(base_affordable_units=14, add_path="MOD", add_units=15)   # 14.6% VLI: not at 15%
    assert r["add_bonus_units"] == 0 and r["total_units"] == 96 + 45   # 14% row = 46.25% -> 44.4 -> 45


def test_fifty_percent_cap_blocks_moderate_on_moderate():
    assert calc(base_path="MOD_SALE", base_affordable_units=43, add_path="MOD", add_units=15)["add_bonus_units"] == 0   # 58 of 96 restricted
    r = calc(base_path="MOD_SALE", base_affordable_units=43, add_path="MOD", add_units=5)    # 48 of 96 = exactly 50%
    assert (r["add_bonus_pct"], r["add_bonus_units"]) == (20.0, 20)
    assert calc(base_path="MOD_SALE", base_affordable_units=43, add_path="MOD", add_units=6)["add_bonus_units"] == 0    # 49 of 96


def test_additional_bonus_not_available_to_100_percent_affordable():
    r = calc(base_path="AFF100", base_affordable_units=96, add_path="MOD", add_units=10)
    assert r["add_bonus_units"] == 0 and any("only for" in f for f in r["flags"])


def test_100_percent_affordable():
    r = calc(base_path="AFF100", base_affordable_units=96, aff100_moderate_units=19)   # 77 lower units * 80% = 61.6 -> 62
    assert (r["bonus_units"], r["concessions"]) == (62, 5)
    assert calc(base_path="AFF100", base_affordable_units=96, aff100_moderate_units=20)["bonus_units"] == 0   # 20.8% moderate


def test_senior_and_special():
    assert calc(base_path="SENIOR")["bonus_units"] == 20                               # 19.2 -> 20
    assert calc(base_path="SPECIAL", base_affordable_units=10)["bonus_units"] == 2     # 20% of 10 units
    assert calc(base_path="SPECIAL", base_affordable_units=9)["bonus_units"] == 0      # 9.4% < 10%


@pytest.mark.parametrize("path,units,n", [("VLI", 5, 1), ("VLI", 10, 2), ("VLI", 15, 3), ("VLI", 16, 4), ("LI", 16, 1), ("LI", 17, 2),
                                          ("LI", 24, 3), ("MOD_SALE", 29, 3), ("MOD_SALE", 44, 4), ("SENIOR", 0, 0)])
def test_concessions(path, units, n):
    assert calc(base_path=path, base_affordable_units=units)["concessions"] == n


def test_parking():
    mix = dict(share_0_1_br=0.5, share_2_3_br=0.4, share_4plus_br=0.1)               # 0.5 + 0.6 + 0.25 = 1.35
    r = calc(base_affordable_units=5, **mix)
    assert r["parking_ratio"] == 1.35 and r["max_required_parking"] == 157             # 116 units * 1.35 = 156.6
    assert calc(base_affordable_units=10, near_major_transit=True)["parking_ratio"] == 1.0     # 10% VLI is under the 11% needed
    assert calc(base_affordable_units=11, near_major_transit=True)["parking_ratio"] == 0.5
    assert calc(base_path="LI", base_affordable_units=20, near_major_transit=True)["max_required_parking"] == 65  # 130 * 0.5
    assert calc(base_path="AFF100", base_affordable_units=96, near_major_transit=True)["max_required_parking"] == 0


def test_sb4_density_and_parking():
    r = calc(sb4_applies=True, zoning_density_du_ac=0, sb4_density_du_ac=40, base_path="AFF100", base_affordable_units=96,
             share_0_1_br=0.0, share_2_3_br=1.0)
    assert r["base_units"] == 96 and r["parking_ratio"] == 1.0                         # SB 4 caps parking at 1 per unit
    assert calc(sb4_applies=True, zoning_density_du_ac=60, sb4_density_du_ac=40, base_path="AFF100")["density_used"] == 60
    assert any("100% affordable" in f for f in calc(sb4_applies=True, sb4_density_du_ac=40)["flags"])


def test_sb4_and_ab130_checklists():
    import json
    site = json.loads((Path(de.ROOT) / "sample_data/site_sb4.json").read_text())["site"]
    res = {c["id"]: c["result"] for c in de.sb4_gate(site)}
    assert res["owned_by"] == "PASS" and res["site_criteria"] == "NEEDS REVIEW"
    assert {c["id"]: c["result"] for c in de.sb4_gate({**site, "owner_acquired": "2024-01-02"})}["owned_by"] == "FAIL"
    assert {c["id"]: c["result"] for c in de.sb4_gate({**site, "owner_acquired": "2024-01-01"})}["owned_by"] == "PASS"
    assert {c["id"]: c["result"] for c in de.sb4_gate({**site, "ft_to_heavy_industrial": 1199})}["heavy_industrial"] == "FAIL"
    a = lambda **k: {c["id"]: c["result"] for c in de.ab130_gate({**site, **k})}
    assert a()["acres"] == "PASS" and a(site_acres=20.01)["acres"] == "FAIL"
    assert a(site_acres=4.5, builders_remedy=True)["acres"] == "FAIL" and a(site_acres=4, builders_remedy=True)["acres"] == "PASS"
    assert a(previously_urban_use=False, perimeter_urban_pct=74, quarter_mile_urban_pct=74)["urban_use"] == "FAIL"


def test_tribal_clock():
    rows = {r["step"]: str(r["date"]) for r in de.tribal_clock("2027-01-11", "2027-02-08", extension=True)}
    assert rows["Send notice to affiliated tribes by"] == "2027-01-25"
    assert rows["Begin consultation by"] == "2027-02-22"
    assert [d for s, d in rows.items() if s.startswith("Conclude")] == ["2027-04-23"]   # Feb 22 + 60 days


def test_scenario_grid_never_exceeds_100_percent():
    g = de.scenario_grid(BASE)
    assert max(x["total_bonus_pct_of_base"] for x in g) == 100.0
    assert all(x["base_aff_units"] + x["add_units"] <= 48 for x in g if x["add_path"] != "NONE")
