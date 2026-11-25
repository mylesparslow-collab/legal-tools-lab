# CEQA Record Compiler and Density Bonus Calculator (Tool 10)

Two small deterministic tools for California land use work. Personal portfolio demo built by a non-attorney.
Fictional data only. Not legal advice.

1. **`record.py`** works out the record-of-proceedings clock under Pub. Resources Code 21167.6, decides which
   internal-communications rule applies after SB 131, gives every candidate document a disposition with a reason,
   drops exact duplicates, and writes page-numbered PDF volumes with an index.
2. **`density.py`** computes Gov. Code 65915 density bonus units, including the AB 1287 additional bonus, and runs
   SB 4 and AB 130 eligibility checklists. It writes an Excel workbook whose Calc tab is live formulas.

No language model is called. Document labels (record category, internal or not, presented to the decision-making
body, privilege flag) are CSV inputs that a person or a separate reviewed classifier would supply.

## Run
```
python3 build_legal_data.py        # writes legal_data.json
python3 generate_synthetic.py      # writes sample_data/ (fictional, seed-fixed)
python3 record.py sample_data/record_case.json sample_data/documents.csv -o output/record
python3 record.py sample_data/record_case_distribution_center.json sample_data/documents.csv -o output/record_distribution_center
python3 density.py sample_data/site_mixed_income.json -o output/Density_Model_Mixed_Income.xlsx
python3 density.py sample_data/site_sb4.json -o output/Density_Model_SB4.xlsx
python3 -m pytest -q tests         # 46 hand-computed rule tests
python3 tests/parity_check.py      # LibreOffice recalculation: workbook formulas equal the engine, 13 variants
```
Needs Python 3.10+, `openpyxl`, `reportlab`; tests also use `pytest`, `pypdf`; the parity check needs LibreOffice.

## Record compiler
| Rule | Cite |
|---|---|
| Request served within 10 business days of filing | PRC 21167.6(a) |
| Record certified within 60 days of service of the request | PRC 21167.6(b)(1)(A) |
| Extensions by stipulation or order; over 60 days needs a public-interest finding | PRC 21167.6(c) |
| Project with a distribution center (50,000+ sq ft) or oil and gas infrastructure: all internal communications, including staff notes | PRC 21167.6(e)(10)(A) |
| Any other project: electronic internal communications not presented to the decision-making body are not required, unless reviewed by an executive or supervising official | PRC 21167.6(e)(10)(B) |
| Logistical communications excluded; privileged or exempt material not included | PRC 21167.6(e)(10) |
| Order of documents and index | Rule 3.2205 |
| Bookmarked, searchable electronic files; optional index hyperlinks | Rule 3.2207 |

Dispositions: `INCLUDE`, `NOT_REQUIRED` (agency may include; `--include-optional` does so), `EXCLUDE_LOGISTICAL`,
`EXCLUDE_DUPLICATE`, `WITHHOLD_PENDING_PRIVILEGE_REVIEW` (a person decides), `ATTORNEY_REVIEW`.

Outputs per run: `AR_Vol_NN.pdf`, `index.html`, `disposition_log.csv`, `privilege_log_candidates.csv`,
`record_clock.ics`, `summary.json`. The sample set is 42 fictional documents, run once as a housing project
(branch B) and once as a distribution center (branch A) to show the difference.

## Density calculator
Inputs are site acres, base density, a bonus category, and whole-unit affordable counts. Each component is rounded
up separately (65915(q)). The workbook has Inputs, Calc (live formulas), Engine Check, Scenarios, Eligibility,
Sources, Attorney Review and Tables tabs.

Sample results:
* Mixed income, 2.4 acres at 40 du/ac: 96 base units, 15% very low plus 15% moderate gives 48 + 48 bonus units, 192 total.
* SB 4 site, 2.4 acres at 40 du/ac, 100% affordable: 96 base units, 62 bonus units, 158 total, 5 concessions.

## Legal numbers
Every number is in `legal_data.json` with a cite, the source it was read from, the date, and a status:
`official_source`, `secondary_copy_of_primary_text`, or `unverified`. Unverified items are highlighted on the
workbook's Sources tab. The official legislative site was not reachable during the build, so statute text was read
on copies. Recheck on leginfo before relying on any of it.

See `CORRECTIONS.md` for 17 places where the research report differs from the text.

## Limits
* Weekend or holiday roll-forward of the due date is flagged, not applied. The holiday list is hand-entered.
* Cross-referenced site exclusions (Gov. Code 65913.4(a)(6)) are shown as NEEDS REVIEW.
* No ingestion of .pst or Microsoft 365 exports; duplicates are detected on files already on disk.
* Base density studies, replacement units, local inclusionary rules and AB 2097 are out of scope.
* Open legal questions are listed on the workbook's Attorney Review tab.
