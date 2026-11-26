# Held-out test material: billing-guideline check

Fictional data. Not legal or billing advice. Written on 2026-11-26 by an independent test author
who did not read the detector, parser or intake code, and did not run the tool on any of this.

The tool's own accuracy figures are self-fit: one author wrote the sample data and the detectors.
This folder holds fresh material to measure the tool honestly.

## The sealed-batch rule

- `batch_a/` is the working batch. Run it, read the misses, fix weaknesses.
- `batch_b/` is sealed. Do not open its invoices, documents, keys or builder file while working
  on the tool. Run it once, at the very end, and report that single result as the final score.
  If anything in batch B is looked at or run before then, say so next to the score.

The two batches are the same size and difficulty and use different clients, people and wording.

## What is in each batch

| | batch_a | batch_b |
|---|---|---|
| Clients | Harrowgate Casualty Exchange (insurer), Marrowfen Sanitary District (public agency), Pindlecroft Robotics (company with an AI clause) | Bramblewick Freight Cooperative (company with an AI clause), Coldwater Fen Hospital Authority (public agency), Nettlecombe Home Lending (lender) |
| Guideline document styles | terse two-column table; long narrative contract exhibit; informal numbered email | one-page numbered grid with a consequences column; lettered clauses in dense legal prose; chatty unnumbered email |
| Confirmed rules | 20 + 15 + 14, and 1 left proposed | 18 + 15 + 14, and 1 left proposed |
| Invoices | 6 CSV, 1 LEDES-style | 6 CSV, 1 LEDES-style |
| Invoice lines | 206 | 196 |
| Planted violations | 88 (46 easy, 23 medium, 19 hard); 1 expected as waived | 86 (49 easy, 17 medium, 20 hard); 1 expected as waived |
| Lines that must not be flagged | 124 | 116 |
| Hard negatives described one by one | 46 | 47 |

Every rule type in the tool's README is planted at least once in each batch, plus `ARITH-LINE`
and `ARITH-TOTAL`.

Files in each batch:

```
guideline_docs/<client>.txt   the client's document (plain text)
guidelines/<client>.json      confirmed structured rules, in the tool's schema
invoices/                     draft invoices (CSV layout; one LEDES-style file per batch)
matters.json                  approved timekeepers, rate cards, approvals, budgets
waivers.json                  one client-approved exception
ANSWER_KEY.json               planted violations, lines that must not be flagged
INTAKE_KEY.json               ground truth for the intake helper
builder/                      the script that wrote the files from the hand annotations
```

Example run (not run by the test author):

```
python -m billcheck check heldout/batch_a/invoices/INV-HCE-7001.csv \
    --guidelines heldout/batch_a/guidelines/harrowgate.json \
    --matters heldout/batch_a/matters.json --waivers heldout/batch_a/waivers.json --out-dir out/
python -m billcheck intake heldout/batch_a/guideline_docs/harrowgate.txt --client-id harrowgate -o proposed.json
```

`ANSWER_KEY.json` maps each invoice to its file and its guideline file (`invoice_files`,
`invoice_guidelines`).

## How the answer keys were made

By hand, before any tool run. Each invoice line was typed with its date, timekeeper, hours, codes
and narrative, and each planted violation was typed next to its line with the rule type, a note
and a difficulty. The builder script only multiplied hours by rate, summed totals, numbered the
lines and wrote the files and the key from those annotations. It also printed plain sums (hours
per person per day, age of each line in days, research hours, share of round entries, fees per
phase) so the author could check that clean lines really are clean. It does not import or call
any part of the tool.

`ANSWER_KEY.json` uses the same layout as `data/ANSWER_KEY.json`: `planted` entries with
`invoice_id`, `line_no` (null for invoice-level findings), `timekeeper_id`, `rule_type`,
`rule_id`, `expected_status` (`open` or `waived`) and `note`; `not_enforced`; `hard_cases_clean`;
`invoice_line_counts`. Extra fields, each named in the key's `extra_fields`:

- `difficulty` on each planted violation (easy, medium, hard).
- `must_not_flag`: every line with no planted violation. A finding on one of these is a false
  positive.
- `alternate_lines`: for attendance limits the document does not say which attendee is cut, so
  a finding of that rule on any of the listed lines counts as the planted one.
- `invoice_files`, `invoice_guidelines`.
- `schema_limit: true` on one batch B hard negative (a paralegal at a hearing where the document
  limits attorneys). The rule parameters may not be able to express it. Report it separately.
- `not_checkable_in_ledes`: receipt, cost and AI-flag checks cannot run on the LEDES-style file.

Arithmetic is exact on every line and total except the planted `ARITH-LINE` and `ARITH-TOTAL`
cases (one of each per batch).

### Judgement calls to know about

- **Research limit.** The planted finding sits on the line where the running total of legal
  research crosses the limit. Some research lines do not use the word "research" and some carry
  activity code A104 instead of A102. If the tool flags a different research line of the same
  invoice for the same rule, count it as found.
- **Daily cap.** The planted finding sits on the last entry of the day. A finding of that rule on
  another entry of the same person and day counts as found.
- **Boundary values** (exactly at a limit) are clean or violating according to the document's
  wording ("more than", "or more", "exceeding"). Each one is explained in its note.
- **Rules a client does not have.** Several clean lines would be violations for another client
  (a 12-hour day where the document sets no daily limit, a one-word narrative where there is no
  rule on vague descriptions, a second lawyer at a hearing where there is no attendance limit).
- **Other findings on a planted line.** If the tool raises a second, different rule on a line
  that has a planted violation, treat it as unjudged unless it is plainly wrong.

## Guideline JSON and the intake key

`guidelines/<client>.json` was written from each document: rule type, numeric parameters,
severity, the quoted sentence (checked to be verbatim in the document) and its place. Rules a
reader would not confirm (a stated preference) are left `proposed`, and a line that would break
them is listed in the key's `not_enforced`.

Keyword parameters are a special case. The rule types `vague_description`, `non_billable_task`,
`expense_overhead`, `ai_disclosure_required` and `ai_nonpayable_task` take phrase lists, and no
client document supplies such lists. For these the JSON carries the standard lists that appear
in every sample client file under `data/guidelines/`, copied as they are, plus the words the
client's own document uses (for example "follow up", "filing", "digest"). The invoice narratives
were written in ordinary varied wording without fitting them to those lists; some use a listed
word (marked easy) and many do not (marked medium or hard). Misses on the hard cases are the
point of the test. If a later step widens the lists, do it from batch A misses only.

`INTAKE_KEY.json` is the ground truth for `billcheck intake`: per client, the rules a person
would confirm (`type`, `key_params`, `source_quote`), the one rule a person would leave proposed,
and `sentences_that_are_not_rules` (for example "the District does not impose a ceiling on the
number of hours", a 30-day invoicing deadline that is not a late-time limit, a fee estimate that
is not a budget cap). Keyword lists are left out of `key_params`. Severity is the author's
judgement from the document's wording and should be reported separately.

## What the schema could not express

- A per-page copy rate, invoice timing, payment terms, purchase-order thresholds and reporting
  duties appear in the documents and have no rule type. They are listed as sentences that are
  not rules.
- "Not more than one attorney" at an event: the rule has a head count and no role filter.
- "Two related tasks is fine, three or more in an entry over an hour is not" is written as
  `max_tasks: 2, min_hours: 1.0`.
- A whole-hour rounding pattern is written as `block: 1.0`.
- A meal for two people is entered as 2 units at the per-person price, because the CSV layout
  has no head-count column.

## What the test author read

Read: this tool's `README.md`, `FORMAT_NOTES.md`, `data/guidelines/schema.json`, the five sample
guideline JSON files and four of the sample guideline documents, the first lines of the sample
invoices, `data/matters.json`, `data/waivers.json` and `data/ANSWER_KEY.json`. The sample
guideline JSON files contain the tool's standard phrase lists, which is how those lists are known.

Not read: anything under `billcheck/`, `tests/`, `generate_data.py`, `run_demo.py`, `output/`,
`data/utbms_sample_codes.json`. Task, activity and expense codes were written from general
knowledge of the UTBMS litigation code set and may include codes the sample table lacks.

The tool was not run on this material.
