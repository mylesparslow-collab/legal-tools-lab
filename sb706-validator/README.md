# SB 706 progressive design-build validator

Checks a procurement record against California Public Contract Code chapter 4.7
(§§ 22185–22185.11, added by SB 706, Stats. 2023, ch. 500) and the skilled and
trained workforce rules in chapter 2.9 (§§ 2600–2604). Output is an audit table:
one row per check, with a status, the section it rests on, and the numbers used.

This is a personal portfolio demo. All agencies, firms, and figures are
fictional. It was built by a non-attorney, has not been reviewed by a lawyer,
and is not legal advice.

## Run it

Needs Node 20 or later. No dependencies to install.

    npm test                                   # 32 tests
    node src/cli.js samples/compliant.json     # prints a Markdown audit
    node src/cli.js samples/flawed.json --rfq samples/flawed_rfq.txt --out output/flawed
    npm run build:demo                         # rebuilds demo/index.html and CORRECTIONS.md

The CLI exits 1 when any check fails. To get a Word table, convert the Markdown:
`pandoc output/flawed.md -o output/flawed_audit.docx` (a sample is in `output/`).

`demo/index.html` is a single page with the engine inlined. It is written as a
page fragment for hosting inside a wrapper; add `<!doctype html>` and a
`<meta charset="utf-8">` line at the top to open it directly from disk.

## What is checked

| Area | Checks | Source |
|---|---|---|
| Authority | Agency type, state-facility exclusion, more than $5,000,000, 10-project cap, repeal date, conflict-of-interest guidelines | §§ 22185, 22185.1, 22185.2, 22185.9, 22185.11 |
| RFQ | Eight required elements, seven template items, factor weights, price not the sole factor, workforce notice | §§ 22185(i), 22185.3(a), 2600(c) |
| Proposers | Safety record math, perjury certification, workforce commitment or project labor agreement exception, solicitation-services conflict flag | §§ 22185.2, 22185.3(a)(4)(G), (a)(5), (b) |
| Award and bonds | Public announcement and basis statement, payment bond at least the performance bond, admitted surety, errors and omissions insurance, standard bond form | §§ 22185.3(d), 22185.4 |
| Price and retention | Overrun and savings math, off-ramp steps, 5% retention cap, no phase 1 retention, subcontract retention | §§ 22185.5, 22185.7, 7201 |
| Subcontracts | 0.5% threshold on construction-allocable price when the contract is $10,000,000 or more; notice, criteria, best value award | § 22185.6(b) |
| Workforce months | 60% or 30% apprenticeship graduates by headcount or hours, 10-hour floor, small unlisted subcontract exemption, 150% withholding | §§ 2601(d), 2602 |
| Legislature report | December 31, 2028 due date and the ten required items | § 22185.8 |

Statuses: PASS, FAIL, REVIEW (statute silent or ambiguous, or input missing),
INFO (a computed number), N/A.

## Legal numbers are data

Every threshold, date, and percentage lives in `data/rules.json` with its
citation, the statutory wording, a source link, and a verification status.
`src/engine.js` contains no legal numbers. Status values:

- `primary-text`: read on leginfo.legislature.ca.gov on 2026-11-25.
- `not-verified`: cited by the research report but not read for this build
  (Gov. Code § 1090, Code Civ. Proc. § 860). No check applies a rule from these.

## Corrections to the source report

The research report this tool came from cites §§ 22170–22174 for SB 706. Those
sections are SB 991's water-agency chapter. See `CORRECTIONS.md` for all twelve
items (generated from `data/corrections.json`).

## Limits

- Input is a structured JSON record that a person fills in. Nothing here reads a
  contract for you. `src/rfq_scan.js` is a keyword screen that shows where
  related wording appears in a draft RFQ; a hit does not mean the clause is
  adequate. The report's "bounded LLM layer" is not built.
- Not modeled: the pre-1995 apprenticeship credit in § 2601(d)(3), the
  substantially-complex-project retention exception in § 7201(b)(4), the
  § 4100 subletting rules, and any local charter or ordinance.
- Open questions the engine sends to REVIEW instead of deciding: what counts as
  a "special district", which event uses one of the ten project slots, which
  cost figure is measured against $5,000,000, how the Labor Code § 3201.5
  alternative in the safety-record test is read, and what happens to contracts
  in progress when the chapter is repealed on January 1, 2030.
- Statutes change. Re-read the code before relying on any row.

## Layout

    data/rules.json         legal numbers with citations and status
    data/corrections.json   report-versus-statute corrections
    src/engine.js           checks (pure functions, no imports)
    src/rfq_scan.js         keyword screen for RFQ drafts
    src/report.js           Markdown audit table
    src/cli.js              command line
    samples/                two fictional records and one fictional RFQ draft
    tests/engine.test.js    32 tests, including boundary values
    scripts/build_demo.js   builds the single-file demo page
    demo/                   template and built page
    output/                 sample audits (JSON, Markdown, Word)
