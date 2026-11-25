# IFOA risk/reward pool checker and hospital seismic deadline tracker

A portfolio demonstration built from "Tool 4" of a research report on legal tools. It is not a firm tool, it was not
prepared by an attorney, and nothing here is legal advice. Every project, party, facility, dollar amount and date in
`sample_data/` is invented.

## What it does

**1. Amendment ledger for an Integrated Form of Agreement (IFOA).** A multi-party construction contract of this kind
is amended many times: trade partners join, the target cost moves, contingency is drawn. Each amendment restates
totals and profit shares in an exhibit. The ledger replays every amendment from its changes alone and compares the
result with what the exhibit says. It checks that

- restated target cost, contingencies, EMP and total ICL equal the prior totals plus that amendment's changes;
- stated ICL (profit-at-risk) shares sum to 100.00% and each matches the member's ICL dollars;
- no member receives ICL before signing the base agreement or a joining agreement;
- contingency balances never go negative, and the EMP covers target cost + shared contingency + ICL;
- every record carries a source reference (document, exhibit, page, quote);
- each joining record says whether the joining party had its own counsel (a workflow field, see Corrections).

**2. Closeout waterfall.** For a forecast final cost, an overrun is absorbed by shared contingency, then the team's
ICL up to 100%, then owner contingency, then the owner at cost. Savings are split owner/team with an optional cap.
Reimbursable costs are always paid; only profit is at risk. The tier order, split and cap are inputs, because these
terms are negotiated per project.

**3. Seismic deadline tracker.** For a hospital campus it works out the applicable deadline (January 1, 2030, or an
HCAI-approved delay), screens the delay conditions in Health & Safety Code § 130065.1, computes each building's float
to the deadline, carries construction schedule drift from the linked project into the buildings that depend on it,
and measures milestone slippage against the compliance plan: days late, the $5,000-per-day fine exposure, the
building-permit hold, and the date by which a schedule adjustment must be requested. It can cross-check the campus
file against a CalHHS "Hospital Building Data" CSV export.

## Output

`output/IFOA_Seismic_Model.xlsx` is a live-formula workbook. Running totals, checks, waterfall tiers, payouts, float
and lateness are Excel formulas over yellow input cells, so any number can be traced and the inputs can be changed.
The Python engine computes the same figures independently, and `tests/test_parity.py` recalculates the workbook with
LibreOffice and compares the two. `output/findings.json` lists the engine's findings.

The sample ledger contains two seeded drafting errors (Amendment 6 shares sum to 99.50%; Amendment 8 restates the
target cost $250,000 low). `sample_data/ifoa_ledger_clean.json` is the same ledger without them.

## Run it

```
pip install openpyxl pytest
python make_sample.py        # rewrites sample_data/
python build_workbook.py     # writes output/IFOA_Seismic_Model.xlsx and output/findings.json
python -m pytest -q          # 35 tests; the 7 parity tests need LibreOffice and skip without it
```

`python build_workbook.py <ledger.json> <campus.json> <out.xlsx>` runs it on other files of the same shape.

## Legal numbers

Every legal number is in `legal_params.json` with its citation, source link and a status: `verified` (read in the
statute or agency notice on 2026-11-25), `secondary` (read only in an agency summary of the regulation), or
`assumption` (a display choice, not law). The workbook's formulas point at the Legal Params sheet rather than
hard-coding them.

## Limits

- No actual IFOA was available. The waterfall is one plausible arrangement expressed as inputs, not a statement of
  what any real agreement provides. Cost above the EMP is reported, not allocated.
- The delay screen compares recorded facts with the statute's conditions. HCAI decides eligibility.
- The statute sets a $5,000 fine per calendar day and does not say whether overlapping misses stack. PIN 80 applies
  it per facility. The tracker counts each late calendar day once and shows a low and high bound.
- The CalHHS export has no NPC rating, and compliance needs NPC 5 as well as SPC, so NPC ratings are user-entered.
- Milestone forecast dates are entered by hand; the drift scenario moves building dates, not milestone dates.
- The report also describes a language-model layer that reads draft amendments and agency letters into typed records.
  That layer is not built. The ledger file is the typed record format it would have to produce, and the engine
  rejects any record without a document, exhibit, page and quote.
- The container that built this could not reach data.chhs.ca.gov, so there is no live download; export the CSV by
  hand and pass it to `engine.seismic.hcai_crosscheck`.

See `CORRECTIONS.md` for where the research report was wrong or unconfirmed.
