"""Writes legal_data.json. Every legal number the tools use lives in that file with a
citation, the source it was read from, and a verification status. Edit here, re-run."""
import json
from pathlib import Path

READ = "2026-11-25"
S_LEGISCAN_AB87 = "LegiScan copy of chaptered AB 87 (Stats. 2025, ch. 486), which reprints Gov. Code 65915"
S_PUBLAW = "california.public.law mirror of the code section"
S_SB131 = "LegiScan copy of chaptered SB 131 (Stats. 2025, ch. 24), sec. 19"
S_SB4 = "LegiScan copy of chaptered SB 4 (Stats. 2023, ch. 771)"
S_COURTS = "courts.ca.gov, California Rules of Court (2026)"
SEC = "secondary_copy_of_primary_text"   # read on a mirror of the statute text, not on leginfo itself
OFF = "official_source"
UNV = "unverified"

def item(value, cite, source, status, note=""):
    return {"value": value, "cite": cite, "source": source, "status": status, "read_on": READ, "note": note}

def rows(start, stop, base, step, tail=()):
    out = [[p, round(base + step * (p - start), 2)] for p in range(start, stop + 1)]
    return out + [list(t) for t in tail]

TAIL = lambda p0: [(p0, 38.75), (p0 + 1, 42.5), (p0 + 2, 46.25), (p0 + 3, 50.0)]

data = {
  "_about": "Legal numbers as data. status: official_source = read on the issuing body's site; "
            "secondary_copy_of_primary_text = read on a mirror of the chaptered text (leginfo was unreachable); "
            "unverified = not read against primary text, do not rely on it.",
  "density_bonus": {
    "tables": {
      "LI": item(rows(10, 20, 20.0, 1.5, TAIL(21)), "Gov. Code 65915(f)(1)", S_LEGISCAN_AB87, SEC,
                 "percent lower income units -> percent density bonus"),
      "VLI": item(rows(5, 11, 20.0, 2.5, TAIL(12)), "Gov. Code 65915(f)(2)", S_LEGISCAN_AB87, SEC,
                  "percent very low income units -> percent density bonus"),
      "MOD_SALE": item(rows(10, 40, 5.0, 1.0, TAIL(41)), "Gov. Code 65915(f)(4)", S_LEGISCAN_AB87, SEC,
                       "percent moderate income for-sale units -> percent density bonus"),
      "STUDENT": item([[20, 35.0]] + [list(t) for t in TAIL(21)], "Gov. Code 65915(f)(3)(C)", S_LEGISCAN_AB87, SEC,
                      "percent lower income student units -> percent density bonus"),
      "ADD_VLI": item(rows(5, 10, 20.0, 3.75), "Gov. Code 65915(v)(2)", S_LEGISCAN_AB87, UNV,
                      "additional percent very low income units -> additional bonus. Table rows fell outside the "
                      "text that could be read; the end points (5->20, 10->38.75) match HCD's April 2026 fact sheet. "
                      "Check every row on leginfo."),
      "ADD_MOD": item(rows(5, 11, 20.0, 2.5, TAIL(12)), "Gov. Code 65915(v)(2)", S_LEGISCAN_AB87, UNV,
                      "additional percent moderate income units -> additional bonus. Same caveat as ADD_VLI "
                      "(end points 5->20, 15->50 match HCD)."),
    },
    "flat": {
      "SENIOR_pct_of_senior_units": item(20.0, "Gov. Code 65915(f)(3)(A)", S_LEGISCAN_AB87, SEC),
      "SPECIAL_pct_of_qualifying_units": item(20.0, "Gov. Code 65915(f)(3)(B)", S_LEGISCAN_AB87, SEC,
            "transitional foster youth, disabled veterans, homeless persons; bonus is 20% of the units giving rise to it"),
      "SPECIAL_min_pct": item(10, "Gov. Code 65915(b)(1)(E)", S_PUBLAW, SEC),
      "AFF100_pct_of_lower_income_units": item(80.0, "Gov. Code 65915(f)(3)(D)(i)", S_LEGISCAN_AB87, SEC),
      "AFF100_max_moderate_pct": item(20, "Gov. Code 65915(b)(1)(G)", S_PUBLAW, SEC),
      "AFF100_no_density_cap_transit_miles": item(0.5, "Gov. Code 65915(f)(3)(D)(ii)", S_LEGISCAN_AB87, SEC,
            "within one-half mile of a major transit stop no maximum density applies"),
      "AFF100_height_bonus": item("up to three additional stories, or 33 feet", "Gov. Code 65915(d)(2)(D)", S_PUBLAW, SEC),
    },
    "additional_bonus_gate": {
      "LI": item(24, "Gov. Code 65915(v)(1)(A)", S_PUBLAW, SEC, "base project must provide 24% lower income"),
      "VLI": item(15, "Gov. Code 65915(v)(1)(B)", S_PUBLAW, SEC, "base project must provide 15% very low income"),
      "MOD_SALE": item(44, "Gov. Code 65915(v)(1)(C)", S_PUBLAW, SEC, "base project must provide 44% moderate income"),
      "max_restricted_pct_of_total_units": item(50, "Gov. Code 65915(v)(1)", S_PUBLAW, SEC,
            "additional bonus only if the development would not restrict more than 50% of total units"),
      "base_excludes_bonus_units": item(True, "Gov. Code 65915(v)(4), (o)(9)(A)", S_PUBLAW, SEC),
    },
    "concessions": item({
        "LI": [[10, 1], [17, 2], [24, 3]],
        "VLI": [[5, 1], [10, 2], [15, 3], [16, 4]],
        "MOD_SALE": [[10, 1], [20, 2], [30, 3], [45, 4]],
        "STUDENT": [[20, 1], [23, 2]],
        "AFF100": [[0, 5]], "SENIOR": [], "SPECIAL": []},
        "Gov. Code 65915(d)(2)(A)-(F)", S_PUBLAW, SEC, "minimum percent -> number of incentives or concessions"),
    "rounding": item("each component separately rounded up to the next whole number",
                     "Gov. Code 65915(q), (f)(5)", S_PUBLAW, SEC),
    "parking": {
      "per_unit_0_1_br": item(1.0, "Gov. Code 65915(p)(1)", S_PUBLAW, SEC),
      "per_unit_2_3_br": item(1.5, "Gov. Code 65915(p)(1)", S_PUBLAW, SEC),
      "per_unit_4plus_br": item(2.5, "Gov. Code 65915(p)(1)", S_PUBLAW, SEC),
      "transit_per_unit": item(0.5, "Gov. Code 65915(p)(2)(A)", S_PUBLAW, SEC,
            "needs 20% lower income or 11% very low income, within 1/2 mile of a major transit stop with unobstructed access"),
      "transit_min_pct": item({"LI": 20, "VLI": 11}, "Gov. Code 65915(p)(2)(A)", S_PUBLAW, SEC),
      "transit_mod_per_bedroom": item(0.5, "Gov. Code 65915(p)(2)(A)", S_PUBLAW, SEC, "40% moderate income for-sale"),
      "transit_mod_min_pct": item(40, "Gov. Code 65915(p)(2)(A)", S_PUBLAW, SEC),
      "aff100_transit": item(0.0, "Gov. Code 65915(p)(3)(A)", S_PUBLAW, SEC,
            "no parking standard for a 100% affordable (b)(1)(G) project within 1/2 mile of a major transit stop"),
      "ab2097": item("separate statute, not part of 65915(p)", "Gov. Code 65863.2", "HCD fact sheet (April 2026) mentions it", UNV,
            "not computed by this tool"),
    },
  },
  "sb4": {
    "ownership_cutoff": item("2024-01-01", "Gov. Code 65913.16(c)(1)", S_SB4, SEC, "land owned on or before this date"),
    "max_moderate_pct": item(20, "Gov. Code 65913.16(c)(9)", S_SB4, SEC),
    "max_staff_pct": item(5, "Gov. Code 65913.16(c)(9)", S_SB4, SEC),
    "heavy_industrial_ft": item(1200, "Gov. Code 65913.16(c)(6)", S_SB4, SEC),
    "title_v_ft": item(1600, "Gov. Code 65913.16(c)(7)", S_SB4, SEC),
    "oil_gas_ft": item(3200, "Gov. Code 65913.16(c)(8)", S_SB4, SEC, "applies where multifamily is not an existing permitted use"),
    "light_industrial_adjoining_share": item("more than one-third of square footage", "Gov. Code 65913.16(c)(5)(A)", S_SB4, SEC),
    "nonresidential_zone_du_ac": item(40, "Gov. Code 65913.16(j)(2)(A)", S_SB4, SEC),
    "residential_zone_density": item("density deemed appropriate for lower income housing", "Gov. Code 65913.16(j)(1)(A), 65583.2(c)(3)(B)", S_SB4, SEC),
    "default_density_du_ac": item({"metropolitan": 30, "suburban": 20, "nonmetro_incorporated": 15, "nonmetro_unincorporated": 10},
            "Gov. Code 65583.2(c)(3)(B)", "not read; commonly cited figures", UNV, "check the section before relying on these"),
    "height": item("one story above the maximum height otherwise applicable", "Gov. Code 65913.16(j)(1)(A), (j)(2)(A)", S_SB4, SEC,
            "in a non-residential zone a concession or waiver cannot be used to go higher: (j)(2)(B)"),
    "density_bonus_eligible": item(True, "Gov. Code 65913.16(j)(1)(C), (j)(2)(C)", S_SB4, SEC),
    "parking_max_per_unit": item(1.0, "Gov. Code 65913.16(k)(1)", S_SB4, SEC),
    "parking_zero_transit_miles": item(0.5, "Gov. Code 65913.16(k)(2)(A)", S_SB4, SEC, "also zero if a car share vehicle is within one block: (k)(2)(B)"),
    "prevailing_wage_over_units": item(10, "Gov. Code 65913.16(c)(12)(B)", S_SB4, SEC),
    "labor_standards_units": item(50, "Gov. Code 65913.16(g)", S_SB4, SEC),
    "sunset": item("2036-01-01", "Gov. Code 65913.16(p)", S_SB4, SEC),
    "consistency_review_days": item({"units_150_or_fewer": 60, "more_than_150": 90}, "Gov. Code 65913.16(l)(1)", S_SB4, SEC),
  },
  "ab130": {
    "max_acres": item(20, "Pub. Resources Code 21080.66(a)(1)(A)", S_PUBLAW, SEC),
    "max_acres_builders_remedy": item(4, "Pub. Resources Code 21080.66(a)(1)(B)", S_PUBLAW, SEC,
            "builder's remedy project per Gov. Code 65589.5(a)(11)"),
    "perimeter_urban_pct": item(75, "Pub. Resources Code 21080.66(a)(3)(B)", S_PUBLAW, SEC),
    "quarter_mile_urban_pct": item(75, "Pub. Resources Code 21080.66(a)(3)(C)", S_PUBLAW, SEC),
    "min_density_fraction": item(0.5, "Pub. Resources Code 21080.66(a)(5)", S_PUBLAW, SEC, "of the Gov. Code 65583.2(c)(3)(B) density"),
    "tribal_notice_days": item(14, "Pub. Resources Code 21080.66(b)(1)(A)(i)", S_PUBLAW, SEC, "from application deemed complete"),
    "tribal_response_days": item(60, "Pub. Resources Code 21080.66(b)(2)(A)", S_PUBLAW, SEC),
    "consult_start_days": item(14, "Pub. Resources Code 21080.66(b)(3)(A)", S_PUBLAW, SEC, "from the tribe's acceptance"),
    "consult_conclude_days": item(45, "Pub. Resources Code 21080.66(b)(3)(F)", S_PUBLAW, SEC),
    "consult_extension_days": item(15, "Pub. Resources Code 21080.66(b)(3)(F)", S_PUBLAW, SEC, "one time, on a participating tribe's request"),
    "freeway_ft": item(500, "Pub. Resources Code 21080.66(c)(2)", S_PUBLAW, SEC, "MERV 16 filtration and other conditions"),
    "labor_height_ft": item(85, "Pub. Resources Code 21080.66(d)(2)", S_PUBLAW, SEC),
    "approval_days_after_consultation": item(30, "attributed to SB 158 (2025)", "law firm summary (bwslaw.com)", UNV,
            "not found in the 21080.66 text that was read"),
  },
  "ceqa_record": {
    "request_service_business_days": item(10, "Pub. Resources Code 21167.6(a)", S_SB131, SEC,
            "request and petition personally served on the agency within 10 business days of filing"),
    "certify_days": item(60, "Pub. Resources Code 21167.6(b)(1)(A)", S_SB131, SEC,
            "from the date the request to prepare the record was served on the agency"),
    "cmc_days": item(30, "Pub. Resources Code 21167.6(b)(1)(B)", S_SB131, SEC, "case management conference within 30 days of filing"),
    "election_denial_business_days": item(5, "Pub. Resources Code 21167.6(b)(3)", S_SB131, SEC),
    "max_single_extension_days": item(60, "Pub. Resources Code 21167.6(c)", S_SB131, SEC,
            "unless the court finds a longer extension is in the public interest"),
    "record_categories": item(11, "Pub. Resources Code 21167.6(e)(1)-(11)", S_SB131, SEC),
    "distribution_center_min_sqft": item(50000, "Pub. Resources Code 21060.4", S_SB131, SEC,
            "warehouse distribution center as defined in Lab. Code 2100"),
    "oil_gas_definition": item("facility used for production, processing, transmission, storage, or distribution of petroleum or natural gas",
            "Pub. Resources Code 21064.8", S_SB131, SEC),
    "paper_bound_volume_max_pages": item(300, "Cal. Rules of Court, rule 3.2208(b)", S_COURTS, OFF, "binders: 400 pages"),
    "electronic_format": item("PDF or similar, bookmarked files, full-text searchable, unalterable medium; index may include hyperlinks",
            "Cal. Rules of Court, rule 3.2207(a)", S_COURTS, OFF),
    "order_of_documents": item(["A Notice of Determination", "B Resolutions or ordinances", "C CEQA findings",
            "D Final EIR and related documents", "E Initial study", "F Staff reports",
            "G Transcripts and minutes", "H Remainder of the record"],
            "Cal. Rules of Court, rule 3.2205(a)(1)(A)-(H)", S_COURTS, OFF),
    "weekend_holiday_roll": item("next court day", "Code Civ. Proc. 12, 12a", "not read", UNV,
            "whether day 60 rolls forward when it lands on a weekend or court holiday is an attorney call"),
    "court_holidays": item(["2026-11-26", "2026-11-27", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-12",
            "2027-02-15", "2027-03-31", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-09-27",
            "2027-11-11", "2027-11-25", "2027-11-26", "2027-12-24"],
            "Code Civ. Proc. 135; Gov. Code 6700", "not read; entered by hand", UNV, "replace with the court's published calendar"),
  },
}
Path(__file__).with_name("legal_data.json").write_text(json.dumps(data, indent=1))
print("wrote legal_data.json")
