# Held-out test material: proposal desk (RFP parser)

Fictional data. Not legal advice. Written on 2026-11-26 by an independent test author who did
not read the parser or any other code under `desk/`, did not read the tests or the committed
outputs, and did not run the tool on any of this. Every agency, person and organisation is
invented. The firm, where named, is "Example Firm LLP". There are no citations to any statute,
regulation or case.

The parser figures in the tool's README are self-fit on four samples, plus one earlier hold-out
that has since been used for fixes. This folder holds six fresh RFPs with hand-written keys.

## The sealed-batch rule

- `batch_a/` is the working batch. Run it, read the misses, make general fixes.
- `batch_b/` is sealed. Do not open its RFPs, keys or builder file while working on the parser.
  Run it once, at the very end, and report that single result as the final score. If anything in
  batch B is looked at or run before then, say so next to the score.

## What is in each batch

Each batch has three RFPs of about four to five pages of plain text (186 to 246 lines), each in
a layout unlike the samples and unlike the others, with one two-addendum RFP per batch.

| Batch | File (`rfps/`) | Layout | Addenda | Requirements in key |
|---|---|---|---|---|
| A | `general_counsel_ashdown_valley_ccd.txt` | Lettered sections A to J; roman-numeral sub-items; schedule as "7 December 2026"; weights in running prose ("forty percent (40%)") | none | 11 numbered, 2 unnumbered |
| A | `litigation_counsel_lantern_bay_port.txt` | Notice in numbered paragraphs; dates inside sentences as MM/DD/YYYY; scope exhibit in running prose; requirements split between the body and a questionnaire attachment; qualifications as "First, Second, ..." sentences | none | 10 numbered, 4 unnumbered |
| A | `coverage_counsel_kestrel_ridge_jpia.txt` | Table of contents; "Part" headings; decimal paragraphs; page header at each page break; dates as "Wed., Jan. 27, 2027" | two: the second moves the due date again (and its time), deletes a requirement, changes scoring, moves interviews, corrects an insurance amount | 9 in force, 1 deleted |
| B | `labor_counsel_wexcombe_library.txt` | Questions and answers; dates inside sentences as "Thursday, the 10th of December 2026" and "January 14th, 2027"; requirements marked #1 to #10 | none | 10 numbered, 2 unnumbered |
| B | `water_rights_counsel_saltbrook_muc.txt` | Data sheet of "label ....: value" lines with ISO and DD-MON-YYYY dates; schedules; tick-box checklist R1 to R10; unnumbered supplemental questions; weights as fractions of 1.00; amounts as "USD 5,000,000" | none | 10 numbered, 3 unnumbered |
| B | `general_counsel_dunmarrow_housing.txt` | Addenda placed first, newest on top, dates as M/D/YY; then the RFP as issued with three-level decimal numbers | two: the second moves the due date again (and its time), deletes a requirement, changes scoring, moves interviews and award, removes a form | 10 in force, 1 deleted |

Every RFP has: a schedule, submission mechanics (copies, format, delivery, what is not accepted,
page limit and exclusions, font, sometimes margins), numbered and unnumbered requirements,
some worded as questions, mandatory forms, evaluation criteria with weights that add to 100,
minimum qualifications, insurance statements and named parties. Each also has text that looks
like these things and is not: scope-of-services lists, general conditions with day counts
(protest periods, validity periods), contract start dates, addendum issue dates, a table of
contents, page headers, and statements that something is not required.

Keys are in `answer_keys/`, one JSON file per RFP with the same base name.

## How the answer keys were made

By hand, from reading the RFP text, before any tool run. The dates, times, labels, question
types, form names, criteria, weights, qualification values, insurance amounts, mechanics and
parties were typed by the author. For the exact text of each requirement and the source line of
each deadline, the author typed the first words and the words that follow the item, and a small
script (`builder/`) copied the text between those markers out of the RFP file and checked that
every quoted string is really in the document. The script does not import or call the tool.

## Key format

The keys use the same fields as `data/answer_keys/*.json`: `rfp`, `note`, `agency`,
`deadlines` (`kind`, `date`, `time`), `addendum_changes`, `requirements` (`label`, `qtype`),
`forms`, `evaluation` (`name`, `weight`), `min_quals` (`starts`, `check_kind`, `value`),
`insurance` (`contains`, `amount`), `mechanics` (`page_limit`, `font_pt`, `margin_in`, `kinds`)
and `parties` (`name`, `category`). All values are those in force after the last addendum.

Extra fields, also listed in each key under `extra_fields`:

- `deadlines[].source_line`, `source_line_no`: the stripped line of the file that states the
  date in force and its 1-based line number. `original_source_line` is the line in the body when
  an addendum changed the date.
- `requirements[].section`, `numbered`, `text`: section, whether the RFP labels the item, and the
  exact text with runs of white space collapsed to single spaces (label left out).
- `requirements[].alt_labels`, `alt_qtypes`, `is_question`.
- `deleted_requirements`: removed by addendum; they must not be in the parsed list.
- `evaluation_as_issued`, `forms_as_issued`, `before_addenda`, `after_addendum_1`.
- `addendum_changes[].addendum` (1 or 2), `time_from`, `time_to`, and the added kinds
  `requirement_deleted`, `criterion_removed`, `weight_changed`, `insurance_changed`,
  `form_removed`.
- `insurance[].amount_value`: whole dollars.
- `dates_that_are_not_deadlines`, `not_requirements`: things a parser must not pick up.
- `kind_not_in_existing_keys` on one deadline ("start of services") in the Ashdown key.

### Judgement calls to know about

- **Requirement labels.** The label is the one printed ("3.4", "B-7", "#5", "R6", "4.3.10").
  Roman sub-items are keyed as "E(i)" with `alt_labels` "(i)", "i", "E.i". Unnumbered
  requirements have made-up labels ending in `-unnumbered-N`; match those on text, not label.
- **What counts as a requirement.** As in the existing keys: the items the proposal must contain
  or answer. Scope items, qualifications, forms and conditions are not requirements.
- **Question types** are the author's judgement. Where two readings are fair, `alt_qtypes`
  lists the others. Score them separately from finding the requirement.
- **Interviews on two days or "week of"**: the first day is keyed.
- **Unions and other named organisations**: `adverse` where the RFP says to treat them as
  adverse or the firm would sit across from them; otherwise `other_organisation`. Accept either
  where `party_notes` says so.
- **Weights printed as fractions** (0.30) are keyed as percentages (30), with `printed_as`.
- **`min_quals`**: `years_admitted` and `attorney_count` only where the sentence is a plain
  count; everything else is `not_checkable`. One threshold has `alt_check_kind`.

### What the existing key format could not express

Exact requirement text, source lines, unnumbered requirements, a requirement deleted by
addendum, a second change to the same date, a change to the time of day, changes to weights,
insurance and forms by addendum, and negatives. Each is covered by an extra field above.

## What the test author read

Read: `README.md`, `SWAP_IN_REAL_DATA.md` (first part), one full sample RFP
(`general_counsel_redwood_flats.txt`), the Tannery Creek sample RFP, the earlier hold-out RFP
`data/holdout/bond_counsel_gullwing_harbor.txt` and its key, and the four keys in
`data/answer_keys/`.

Not read: anything under `desk/`, `drafting/`, `tests/`, `output/` or `data/library/`,
`data/generate_data.py`, `run_demo.py`, `data/holdout/first_run_result.json`.

The tool was not run on this material.
