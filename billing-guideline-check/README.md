# Billing-guideline check

Personal portfolio demo. All data is fictional. Not legal or billing advice.

Compares a draft bill to that client's billing rules before it goes out, so the billing attorney can fix problems before the client's e-billing system rejects or cuts them. The checks are fixed rules in code. A person decides every change. The tool never edits an invoice, never rewrites a narrative and never guesses what a timekeeper did.

Billing-guideline rules are treated as contract terms between a client and its outside counsel, held as data. That includes the AI-related terms one sample client has. Nothing here states or applies any law or professional rule.

## How accurate is it

The number to trust is the last held-out run (Batch B, run once on 2026-11-26, after all changes were finished):

- **Engine, with rules a person wrote and confirmed: 74 of 84 planted violations found (88%), 1 false positive on 116 lines that must not be flagged.** Easy cases 48 of 48, medium 16 of 16, hard 10 of 20. All ten misses are work described in ordinary words with none of the usual terms.
- **Intake helper: 20 of 48 rules proposed with the right type and parameters (42%).** 5 more had the right type and a wrong parameter, 23 were missed, 2 proposals were wrong.
- **Engine, using only what intake proposed, with no person correcting it: 37 of 84 found (44%), 3 false positives on 116 lines.**

So the checks are usable when a person writes or corrects the rule file, they miss about half of the hard wording cases, and the intake helper is a rough first pass that misses about half the rules in a document it has not seen.

How the three test sets differ:

| Run | Intake helper: rules proposed with the right type and parameters | Engine with rules confirmed by hand: planted violations found | False positives on must-not-flag lines | Engine with intake proposals only: planted found | False positives on must-not-flag lines |
|---|---|---|---|---|---|
| Batch B, single final run (unseen) | 20 of 48 (5 more had the right type and a wrong parameter, 23 missed, 2 wrong proposals) | 74 of 84 (10 missed; 2 more items left out as not checkable in the LEDES layout) | 1 finding on 1 of 116 lines | 37 of 84 (47 missed) | 3 findings on 3 of 116 lines |
| Batch A, first run, before any change (unseen) | 7 of 50 (5 more had the right type and a wrong parameter, 38 missed, 0 wrong proposals) | 63 of 88 (25 missed) | 2 findings on 2 of 124 lines | 17 of 88 (71 missed) | 2 findings on 2 of 124 lines |
| Batch A, after fixes (fitted, not unseen) | 50 of 50 | 88 of 88 | 0 of 124 lines | 88 of 88 | 0 of 124 lines |
| Own sample data (in-sample) | 61 of 61 | 64 of 64 | 0 of 120 clean lines | not measured | not measured |

- **Held-out sets** (`heldout/`) were written by a separate author who did not read the checking code and did not run the tool. Each has three new clients, guideline documents in new layouts, hand-written rule files, invoices with planted violations, lines that must not be flagged, and a key.
- **Batch A first run** is the result on unseen data before any change. On the hard cases it found 2 of 19. That run is saved unchanged in `heldout_results/batch_a_first_run.json`.
- **Batch A after fixes** is not an accuracy figure. Batch A was read and used to improve the wording lists, the block-billing heuristic and the intake patterns, so the tool now fits it.
- **Batch B** was not opened until every change was finished, and was run once. Nothing in the tool was changed after that run. Its result is in `heldout_results/batch_b_final.json`. Two findings of a different rule on planted lines were not judged.
- **The own sample data** was written by the same person as the detectors. 64 of 64 shows the code and the sample data agree and nothing else.
- The held-out sets test new invoices and new guideline documents more than new phrase vocabulary. Their rule files reuse this tool's standard phrase lists for vague wording, clerical work, overhead and AI terms, so the lists themselves were not independently tested.
- The second engine column confirms every intake proposal unchanged, except proposals the intake helper itself marks as worded as a preference. No person corrected anything. It is a measure of the helper, not a way to use the tool: proposals are meant to be read and corrected first.
- Scoring conventions come from `heldout/README.md`: for an attendance limit, a finding on any attendee of the same event counts; for research and daily limits, a finding on another entry of the same group counts; a finding of a different rule on a planted line is not judged; items that the rule parameters cannot express, or that the LEDES layout cannot carry (receipt, cost, AI flag), are left out of recall and listed separately.
- One correction to the scorer was made after the Batch A first run: the key names non-billable categories without keyword lists, and the first scorer compared the lists. With the corrected comparison the first-run intake figure would be 8 of 50, not 7. The saved file has the original figure.

To repeat a measurement: `python score_heldout.py heldout/batch_a out.json`.

## Run it

Python 3 standard library only. No network access needed.

```
python run_demo.py
```

This checks the seven sample invoices and writes `output/` and `index.html`. Open `index.html` for the static demo page.

```
python -m pytest -q                      # tests (pytest is the only extra)
python generate_data.py                  # rebuild data/ from the seeded generator
```

Command line:

```
python -m billcheck intake data/guideline_docs/luminqa.txt --client-id luminqa -o proposed.json
python -m billcheck check data/invoices/INV-O-3001.csv --guidelines data/guidelines/ostervane.json \
    --matters data/matters.json --waivers data/waivers.json --out-dir out/
python -m billcheck compare data/guidelines --format text
```

## What is in it

| Part | Where | What it does |
|---|---|---|
| Guideline model | `data/guidelines/<client>.json`, `data/guidelines/schema.json`, `billcheck/guidelines.py` | Each rule has an id, type, parameters, severity, the quoted sentence from the client's document, and its section and page. Only rules with status `confirmed` are enforced. |
| Intake helper | `billcheck/intake.py` | Reads a plain-text guideline document and proposes candidate rules by fixed patterns. Each is marked "proposed, needs confirmation". |
| Invoice readers | `billcheck/readers.py` | LEDES 1998B reader and a plain CSV reader into one model. Checks line and invoice arithmetic. See `FORMAT_NOTES.md`. |
| Check engine | `billcheck/engine.py`, `billcheck/blockbilling.py`, `billcheck/lexicon.py` | Runs confirmed rules. Each finding has a severity, the entry, the rule id, the quoted sentence, an explanation, a suggested fix and an amount at risk. |
| Waivers | `billcheck/waivers.py`, `data/waivers.json` | Records a client-approved exception: who, when, reference, expiry. A matching finding is shown as waived and not counted. |
| Outputs | `billcheck/report.py` | Pre-bill review report (HTML, JSON, CSV), a summary paragraph, a note per timekeeper, and a comparison table across clients. |
| Synthetic data | `generate_data.py`, `data/` | Five fictional clients, seven draft invoices, planted violations and `data/ANSWER_KEY.json`. |
| Held-out test | `heldout/`, `score_heldout.py`, `heldout_results/` | Two test sets by a separate author, the scorer, and the saved results. |

### Inputs the engine needs

- The invoice file (LEDES-style or CSV).
- The client's guideline JSON.
- A matter record (`data/matters.json`): approved timekeepers, rate card, last billed rates, rate notice dates, approvals on record (research, travel, staffing) and budget. Rules that need it report "not checked" when it is missing.
- Waivers, if any.

### Rule types

| Type | What it looks at | Amount at risk |
|---|---|---|
| `block_billing` | more than `max_tasks` tasks in an entry over `min_hours` | whole entry |
| `minimum_increment` | hours not a multiple of the increment | whole entry |
| `rounding_pattern` | share of a timekeeper's entries that are multiples of a block (for example 0.5 h) | not quantified |
| `daily_hour_cap` | a timekeeper's hours in one day | hours over the cap |
| `staffing_matter_limit` | number of timekeepers on the invoice, unless approved | not quantified |
| `staffing_event_limit` | timekeepers attending the same deposition, hearing, mediation, arbitration or trial | entries of the attendees over the limit (the check keeps the highest rates; that is an assumption) |
| `unapproved_timekeeper` | timekeeper not on the matter's approved list | whole entry |
| `rate_above_card` | rate above the approved rate | the difference |
| `rate_increase_notice` | rate above the last billed rate before the notice period has run | the difference |
| `non_billable_task` | listed phrases, and wider wording, for clerical work, training, conflicts checks, invoice preparation | whole entry |
| `internal_conference_limit` | internal conference entries over a limit, including a meeting with a named timekeeper of the same matter and no outside party | hours over the limit |
| `research_approval` | cumulative research hours on the invoice over a limit, unless approved | hours over the limit |
| `travel_time` | travel billed above a percentage of the rate, or without approval | the difference, or the whole entry |
| `expense_overhead` | expense codes and phrases the client treats as overhead | whole expense |
| `expense_receipt_threshold` | expense at or over a threshold with no receipt | whole expense |
| `expense_per_diem` | meal and lodging unit costs over a cap | amount over the cap |
| `expense_markup` | expense billed above recorded cost | the difference |
| `vague_description` | listed vague phrases, bare phrases with no object, very short narratives, and narratives that are only a generic activity and a generic object | whole entry |
| `required_codes` | missing task, activity or expense codes | whole entry |
| `late_time` | work older than N days on the invoice date | whole entry |
| `budget_cap` | billed to date plus this invoice over the matter cap | the overage |
| `phase_cap` | the same, per task-code phase | the overage |
| `duplicate_entries` | same timekeeper, date, quantity and narrative | the later entry |
| `ai_disclosure_required` | entry flagged AI-assisted, or mentioning an AI tool, without the client's disclosure marker | whole entry |
| `ai_nonpayable_task` | AI-assisted entry describing a task the client's terms say it will not pay for | whole entry |

Arithmetic checks (`ARITH-LINE`, `ARITH-TOTAL`) always run and are not client rules: units x rate + adjustment must equal the line amount within one cent, and the lines must add up to the invoice total within one cent.

Severities: will likely be rejected, likely reduced, review. Severity is a field on each rule, so it can be set per client.

### How block billing is detected

The heuristic is in the docstring of `billcheck/blockbilling.py`. In short:

1. A semicolon, a full stop or a line break starts a new task only if the text after it begins with a task word (draft, review, telephone conference with, and so on). Otherwise it is a continuation. "Draft motion to compel; sections on relevance; proportionality" is one task.
2. A comma, "and" or "then" starts a new task only if the text after it begins with a task word and the task before it already has an object. Two task words of the same kind do not split when the kind is reviewing, researching, attending, travelling, or continuing a conversation (discuss, advise). "Review and revise the order" and "Meet with client and discuss settlement" are each one task. "Draft motion and draft proposed order" and "Prepare exhibit list and e-file with clerk" are each two.
3. Text after a colon is a list and is not split.

`analyze()` returns the tasks it found and a note for each decision. The finding lists the detected tasks as a prompt and says the tool does not know how the time divides.

Known limits of the heuristic: "Prepare for hearing, review briefing" counts as two; "Review the lease and review the title report" counts as one (same kind of activity); a list item that starts with a task word and is not followed by a document noun can be miscounted. It only knows the words in its lexicon.

### Wider wording

`billcheck/lexicon.py` holds wording that applies to every client, on top of each client's own phrase lists: travel ("drive to", "flight to", "return trip"), research ("review case law on"), internal conferences, attendance at an event, clerical work, training, conflicts checks, invoice preparation, overhead items, meals and lodging, AI use, and generic narratives. It also holds guards for words with a second meaning: "filing" a motion is not clerical filing, "training records" in a case are not staff training, a "travel policy" under review is not travel time. A finding that comes from this wider wording says so in its explanation.

### Rules that cannot be checked

When the data needed for a rule is missing, the report says "not checked" and gives the reason. It does not guess. Examples: AI use when the file has no AI flag and the narrative says nothing; receipts and cost in the LEDES layout; approved timekeepers, rates, budgets and approvals when there is no matter record.

### Amount at risk, without double counting

- Per entry: the largest single reduction among its open findings, capped at the entry amount.
- Invoice-level findings (budget, phase, total mismatch) overlap with entry reductions, because cutting entries also lowers the bill. The invoice figure is the larger of the per-entry sum and the largest invoice-level amount, capped at the sum of the lines.
- Waived findings count for nothing.

The amounts are estimates of exposure from stated assumptions, not predictions of what a client will pay.

### Intake and confirmation

The helper reads prose with numbered or lettered clauses, headings, page markers, table rows (label, requirement and further columns), and emails with or without numbered items. Numbers written as words are read ("four (4) hours", "half the rate", "six-minute units"). The quoted text is the original wording; for a table cell that wraps over several lines the quote is the cell text joined up. A sentence worded as a preference gets a note saying so.

`python -m billcheck intake` writes a guideline file in which every rule has status `proposed`. The engine skips proposed rules and lists them in the report as not enforced. To enforce one, a person checks the parameters against the quoted sentence, then sets `status` to `confirmed` and fills `confirmed_by` and `confirmed_on`. The sample Pellwick file keeps one rule (`PBS-LATE-01`) unconfirmed to show this.

## Sample data

Five fictional clients with differently written documents: a strict insurer (Quillfeather Mutual Indemnity), a public agency with a not-to-exceed budget (Brackenmoor Regional Water Agency), an hourly corporate client (Ostervane Industrial Holdings), a client with an AI clause (Luminqa Data Systems) and a minimal one-page letter (Pellwick Bakery Supply). Seven draft invoices, four LEDES-style and three CSV, 177 lines in total. One invoice is a clean control.

Result on the sample data, in-sample (also in `output/answer_key_score.json`):

- Planted violations found: 64 of 64 (63 open, 1 correctly shown as waived).
- Findings not in the answer key (false positives): 0.
- Lines with no planted violation: 120. Flagged: 0.

Read these numbers with care. The same person wrote the rules, the detectors and the test data, so the detectors fit the data. The numbers show the engine does what it was built to do on this data. They say nothing about accuracy on real invoices. See "How accurate is it" at the top for the held-out results.

## What is tested

`python -m pytest -q` runs 277 test cases (173 test functions, some parametrized), all passing:

- Readers: field list, round trips for both formats, malformed files (first line, header, field count, dates, terminator, numbers), multi-invoice files, line and total arithmetic including the one-cent tolerance.
- Decimal rule: a source scan that fails on any float literal or `float()` call in the package, the generator and the demo script; every numeric field and every result value is `Decimal`; JSON is read without floats.
- Block billing: the hard cases (one task with semicolons, lists of documents, "and" inside one task, initials and decimals) and real block-billed entries; per-client hour thresholds; the finding does not rewrite the narrative or allocate time.
- Guideline model: schema and parameter validation, every quote is verbatim in its document, every section and page reference resolves.
- Intake: proposals are never enforced; confirming one rule enforces only that rule; number extraction; three sentences the patterns are known to miss; three invented documents in other layouts (a grid with a consequences column, lettered clauses with numbers in words, an unnumbered email); sentences that must not become rules.
- Wider wording: travel, research, internal conferences, attendance, non-billable categories, overhead, lodging, AI use and generic narratives, each with cases that must not match; harder block-billing cases.
- Held-out scorer: alternate lines are honoured before must-not-flag, false positives are counted, excluded items are left out of recall and reported, and the first-run file is kept.
- Every rule type on small hand-built invoices, including boundaries (day 60 against day 61, exact cap, inclusive against exclusive threshold) and the "not checked" paths.
- Amount at risk: no double counting, caps, invoice-level overlap.
- Waivers: match, scope by timekeeper, invoice, line and date, expiry, required fields.
- Answer key: every planted violation found, zero findings outside the key, the generator is deterministic and matches `data/`, and a fresh demo run matches the committed `output/` and `index.html`.
- Outputs and CLI: self-contained HTML with no external references, escaping, summary numbers, timekeeper notes, CSV, JSON, comparison table, and the three commands.

## What is not done

- **LEDES**: the reader's structure (first line, 24 field names and order, delimiter, terminator, date format, line types, arithmetic) was checked on 2026-11-26 against the LEDES Oversight Committee's format page and sample file. Field types, lengths and required-field rules were not, because the specification spreadsheet could not be opened. Only LEDES 1998B is attempted. See `FORMAT_NOTES.md`.
- **UTBMS codes**: `data/utbms_sample_codes.json` holds the 1997 litigation, activity and expense codes. Names were checked against a secondary source and counts against the publisher's pages; the publisher's spreadsheets could not be opened.
- **Intake**: pattern matching only. On unseen documents the first version proposed 7 of 50 rules correctly. The patterns were then widened using Batch A; the Batch B row above is the only unseen figure for the current version. Sentences worded in ways the patterns do not cover are missed (three examples are in the tests). Proposed keyword lists and severities need checking; on the sample documents three of 61 proposals carry a different keyword list from the confirmed rule. A person still has to read the whole document. No PDF or Word input. Tables are read from plain text only.
- **Detection is keyword and pattern based.** Travel, research, internal conferences, clerical work, attendance at events and AI use are recognised by listed phrases, wider wording patterns, codes or flags. Work described in other words is still missed, and the wider patterns can flag work they should not. Undisclosed AI use cannot be seen from an invoice unless the time system flags it or the narrative mentions it.
- **The phrase lists have not been independently tested.** The held-out rule files reuse them.
- **Left after the final run (Batch B), not fixed:**
  - Engine misses, all hard cases (10): six non-billable entries described as what was done, with no usual word (two training, two clerical file handling, one conflicts check, one answer to a billing question); an in-firm meeting with no conference wording; a second attorney at a mediation where "attend" is not used; a database charge without the word subscription; a hotel night described as "a room".
  - Engine false positive (1): an AI-assisted entry to draft a motion for "summary adjudication" was read as an AI summary, because the client's non-payable list contains "summary".
  - Intake misses (23): short table cells that rely on the row label for meaning ("Paid once.", "Named on the matter staffing list only.", "8.0 h per person per day"); limits written without "more than" ("0.3 max per entry", "Eleven hours is the most"); formal wording not in the patterns ("ceiling amount", "composite entries", "written concurrence", "rates enumerated in the assignment order"); plain wording not in the patterns ("Don't bill us for clerical work", "Stick to the rates", "Double entries", "your people").
  - Intake wrong parameters (5): an hours threshold for block billing missed twice, an internal-conference limit, a rounding percentage, a travel percentage.
  - Intake wrong proposals (2): a travel sentence read as a timekeeper-approval rule; a daily-hours sentence read as a rounding rule.
  - With intake proposals only, 3 false positives: a zero-hour limit proposed where the document gave one, and two block-billing findings where the proposed rule lacked the document's minimum-hours threshold.
- **No history across invoices.** Research limits, staffing limits and duplicates are checked within one invoice. Budget checks rely on a billed-to-date figure supplied in the matter record.
- **Receipts, cost and AI flags** exist only in the CSV layout. For LEDES files those checks report "not checked".
- **Amounts at risk are estimates** from the stated rules. Staffing and rounding findings are not quantified.
- No connection to any billing or e-billing system, no user accounts, no audit trail beyond the files, no editing of invoices.
- One rule of each type per client. Currency is not modelled; amounts are plain decimals.
- Not reviewed by anyone who administers real billing guidelines.

## Files

```
billcheck/          package: model, readers, writers, guidelines, intake, blockbilling, lexicon, engine, waivers, report, scoring, cli
data/               guideline documents and JSON, schema, matters, waivers, sample codes, invoices, ANSWER_KEY.json
output/             sample outputs written by run_demo.py
tests/              pytest suite
heldout/            held-out test sets by a separate author (read heldout/README.md first)
heldout_results/    saved scores: batch_a_first_run.json, batch_a_after_fixes.json, batch_b_final.json
score_heldout.py    scorer for a held-out batch: intake, engine with confirmed rules, engine with intake proposals only
generate_data.py    seeded synthetic data generator
run_demo.py         one-command demo
index.html          static demo page written by run_demo.py
FORMAT_NOTES.md     assumptions about LEDES 1998B, the CSV layout and UTBMS codes
```
