# Prop 65 Notice Desk

A first-pass desk for a Proposition 65 sixty-day notice, plus a checker that ties every record
cite in a draft to its source page. It is Tool 12 from the research report.

**This is a personal portfolio demo built by a non-attorney. It is not legal advice and not a firm
tool.** Settlement figures come from the California Attorney General's public notice database.
Every case, chart, policy, lab report and draft under `sample/` is synthetic and every name in
them is fictional. Nothing here uses firm or client data.

## What it does

1. **Settlement benchmarks from the public record.** Reads the Attorney General's 60-day notice
   export (30,108 notices, January 1, 2020 to November 24, 2026) and reports the 25th, 50th and
   75th percentile of total payment by plaintiff firm, chemical and product class. It shows each
   slice with its sample size, from narrowest to widest, and marks slices with fewer than five
   payments as thin. It never fills a thin slice from a wider one.
2. **Deterministic triage.** Six checks, each naming the rule it applied:
   12-month grace period after listing, safe harbor dose arithmetic against the NSRL and MADL,
   the under-10-employee exemption, the 60-day clock with the mail extension, the 14-day special
   compliance procedure, and warning label content.
3. **Record check.** For every record cite in a draft, such as `(CHART-0003:8-9)`: the page
   exists, each quotation is on it word for word, each time, date, dollar amount and measurement
   is on it, and quoted policy language has not been replaced by an endorsement. A quote that
   fails gets the closest passage and a word-level difference.
4. **A gate between extraction and arithmetic.** A value pulled from a document, by a person or a
   model, must carry the page, line and words it came from. The record check confirms that anchor
   before any calculation uses the value. A wrong or missing anchor blocks the calculation.
5. **Sign-off log.** A hash-chained log of who verified each cite. A flagged cite cannot be signed
   without a note on how it was resolved.

No language model is called anywhere in this code. The report's "bounded LLM layer" is represented
by the anchored-claims format in `sample/cases/`: that is the shape an extraction step would have
to produce, and the gate is what keeps a bad extraction out of the math.

## Results

Public data, all firms, after removing duplicate reports:

| | |
|---|---|
| Notices | 30,108 |
| Settlements and judgments with a payment | 7,745 |
| Total payment, 25th / 50th / 75th percentile | $15,000 / $20,000 / $32,500 |
| Share of reported dollars paid as attorney fees and costs | about 79% |

Synthetic drafts, with planted errors, against the answer key in `tests/test_verifier.py`:

| Draft | Pass | Warn | Fail | What it caught |
|---|---|---|---|---|
| Coverage tender letter | 5 | 2 | 2 | Quoted exclusion replaced by an endorsement; $500,000 cited where the line says $250,000; "shall defend" for "will defend"; a page that does not exist |
| Trial brief excerpt | 6 | 0 | 4 | Chart time 20:40 for 21:40; quote on the wrong page; "and time" added to a quote; a quote with no cite |
| Prop 65 response memo | 5 | 0 | 1 | Cadmium 0.12 mg/kg for 1.2 mg/kg (one item has nothing checkable and is marked for manual reading) |

Run `python -m prop65 stats` for current figures. The numbers above are from the build on
2026-11-25.

## Run it

Python 3.10 or later.

```
pip install -r requirements.txt
python -m pytest -q
python -m prop65 build                      # writes output/
python -m prop65 stats
python -m prop65 benchmark --chemical Lead --product-class seafood --firm "Example Firm LLP"
python -m prop65 triage sample/cases/kelp_crisps_case.json --record sample/record/record_index.json --today 2026-11-25
python -m prop65 verify sample/drafts/trial_brief_excerpt.md --record sample/record/record_index.json
```

`output/prop65_notice_desk.html` is a single page with the benchmarks, the triage results and the
drafts beside their source pages. `output/Prop65_Notice_Desk.xlsx` has the same content plus every
payment event.

## Rules are data

`rules/prop65_rules.json` holds each rule with its citation, a short summary, its parameters, the
source that was read, and a verification status:

* `verified_primary`: read on leginfo, courts.ca.gov or OEHHA on 2026-11-25
* `verified_mirror`: title 27 regulations read on Cornell LII's mirror, not the official CCR host
* `unverified`: not read; listed so the gap is visible (the engine's checks use none of these, and
  a test enforces that)

`rules/safe_harbor_levels.csv` is a 43-row subset of the OEHHA list dated July 31, 2026 with
listing dates and NSRL / MADL values. A chemical outside the subset returns "not in table"; the
engine does not guess. `rules/product_classes.json` holds the keyword rules that group products.

`docs/REPORT_CORRECTIONS.md` lists twelve points where the research report is wrong or incomplete,
starting with the cure penalty ($610 since April 1, 2024, not $500).

## How duplicates are handled

The export has one row per notice per attached report, so one settlement appears several times.
`ingest.resolutions` reduces 11,003 settlement and judgment rows to 7,761 payment events with
three rules:

1. A judgment on the same notice with the same docket and amounts as a settlement is the court
   entering that settlement. Counted once.
2. Reports from the same noticing party with identical amounts and docket text, and report IDs
   within 3 of each other, on different notices, are one settlement reported per notice.
3. Events of $250,000 or more from the same noticing party with the same docket number and total
   are one global settlement.

These are heuristics. Rule 2 can merge two real settlements with identical standard terms filed
back to back, and can miss a duplicate filed later. Medians are stable under either error; sums
are not, so the tool reports percentiles and shares, not totals.

## Limits

* Amounts are self-reported by settling parties and not audited. "Other payments" is not broken
  down in the export.
* Settlements are reported months after the notice. About 79% of 2026 notices have nothing on
  file yet, so recent years understate outcomes.
* Product class is keyword matching on a free-text field; 15% of notices fall in "other".
* Firm names are grouped by a normalized key. Different spellings beyond punctuation, entity
  suffixes and middle initials are not merged.
* The dose check is arithmetic on the inputs given. Averaging over time, naturally occurring
  allowances, and intake assumptions are legal and scientific questions it does not answer.
* The 60-day clock rolls weekends only. Court holidays are not encoded.
* The label check matches safe harbor wording. A label that fails it may still be clear and
  reasonable (27 CCR § 25600(f)), and tailored warnings under § 25607 et seq. are not covered.
* The record check reads text files with page breaks. Real charts and policies are PDFs and scans;
  an OCR or layout step (the report suggests Azure AI Document Intelligence) would sit in front,
  and its errors would surface here as failed matches.
* The endorsement check recognizes one pattern ("Exclusion x. ... is replaced / deleted").
* The record check confirms that words and numbers are on the page. It does not decide whether
  the draft characterizes them fairly.

## Data

`data/oag_60day_notices_2020-01-01_2026-11-24.csv.gz` is the Attorney General's export, fetched on
2026-11-24 in 166 half-month windows with `scripts/fetch_oag.py` and concatenated with exact
duplicate rows removed. Source: https://oag.ca.gov/prop65/60-day-notice-search

## Layout

```
prop65/        ingest, analytics, triage, labelcheck, verifier, ledger, report, CLI
rules/         rules as data, safe harbor levels, product class keywords
sample/        synthetic record, drafts and case files
tests/         26 tests, including answer keys for the planted errors
docs/          corrections to the research report
output/        generated workbook, HTML page and JSON results
```
