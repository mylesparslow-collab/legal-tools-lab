# Billing-guideline check

Personal portfolio demo. All data is fictional. Not legal or billing advice.

Compares a draft bill to that client's billing rules before it goes out, so the billing attorney can fix problems before the client's e-billing system rejects or cuts them. The checks are fixed rules in code. A person decides every change. The tool never edits an invoice, never rewrites a narrative and never guesses what a timekeeper did.

Billing-guideline rules are treated as contract terms between a client and its outside counsel, held as data. That includes the AI-related terms one sample client has. Nothing here states or applies any law or professional rule.

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
| Invoice readers | `billcheck/readers.py` | LEDES-1998B-style reader and a plain CSV reader into one model. Checks line and invoice arithmetic. See `FORMAT_NOTES.md`. |
| Check engine | `billcheck/engine.py`, `billcheck/blockbilling.py` | Runs confirmed rules. Each finding has a severity, the entry, the rule id, the quoted sentence, an explanation, a suggested fix and an amount at risk. |
| Waivers | `billcheck/waivers.py`, `data/waivers.json` | Records a client-approved exception: who, when, reference, expiry. A matching finding is shown as waived and not counted. |
| Outputs | `billcheck/report.py` | Pre-bill review report (HTML, JSON, CSV), a summary paragraph, a note per timekeeper, and a comparison table across clients. |
| Synthetic data | `generate_data.py`, `data/` | Five fictional clients, seven draft invoices, planted violations and `data/ANSWER_KEY.json`. |

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
| `staffing_event_limit` | timekeepers attending the same deposition, hearing or mediation | entries of the attendees over the limit (the check keeps the highest rates; that is an assumption) |
| `unapproved_timekeeper` | timekeeper not on the matter's approved list | whole entry |
| `rate_above_card` | rate above the approved rate | the difference |
| `rate_increase_notice` | rate above the last billed rate before the notice period has run | the difference |
| `non_billable_task` | listed phrases for clerical work, training, conflicts checks, invoice preparation | whole entry |
| `internal_conference_limit` | internal conference entries over a limit | hours over the limit |
| `research_approval` | cumulative research hours on the invoice over a limit, unless approved | hours over the limit |
| `travel_time` | travel billed above a percentage of the rate, or without approval | the difference, or the whole entry |
| `expense_overhead` | expense codes and phrases the client treats as overhead | whole expense |
| `expense_receipt_threshold` | expense at or over a threshold with no receipt | whole expense |
| `expense_per_diem` | meal and lodging unit costs over a cap | amount over the cap |
| `expense_markup` | expense billed above recorded cost | the difference |
| `vague_description` | listed vague phrases, bare phrases with no object, very short narratives | whole entry |
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
2. A comma or "and" starts a new task only if the text after it begins with a task word, the task before it already has an object, and the two task words are different kinds of activity. "Review and revise the order" and "Meet with client and discuss settlement" are each one task.
3. Text after a colon is a list and is not split.

`analyze()` returns the tasks it found and a note for each decision. The finding lists the detected tasks as a prompt and says the tool does not know how the time divides.

Known limits of the heuristic: "Draft motion and draft proposed order" joined by "and" counts as one task (same kind of activity); "Prepare for hearing, review briefing" counts as two; a list item that starts with a task word and is not followed by a document noun can be miscounted. It only knows the words in its lexicon.

### Amount at risk, without double counting

- Per entry: the largest single reduction among its open findings, capped at the entry amount.
- Invoice-level findings (budget, phase, total mismatch) overlap with entry reductions, because cutting entries also lowers the bill. The invoice figure is the larger of the per-entry sum and the largest invoice-level amount, capped at the sum of the lines.
- Waived findings count for nothing.

The amounts are estimates of exposure from stated assumptions, not predictions of what a client will pay.

### Intake and confirmation

`python -m billcheck intake` writes a guideline file in which every rule has status `proposed`. The engine skips proposed rules and lists them in the report as not enforced. To enforce one, a person checks the parameters against the quoted sentence, then sets `status` to `confirmed` and fills `confirmed_by` and `confirmed_on`. The sample Pellwick file keeps one rule (`PBS-LATE-01`) unconfirmed to show this.

## Sample data

Five fictional clients with differently written documents: a strict insurer (Quillfeather Mutual Indemnity), a public agency with a not-to-exceed budget (Brackenmoor Regional Water Agency), an hourly corporate client (Ostervane Industrial Holdings), a client with an AI clause (Luminqa Data Systems) and a minimal one-page letter (Pellwick Bakery Supply). Seven draft invoices, four LEDES-style and three CSV, 177 lines in total. One invoice is a clean control.

Result on the sample data (also in `output/answer_key_score.json`):

- Planted violations found: 64 of 64 (63 open, 1 correctly shown as waived).
- Findings not in the answer key (false positives): 0.
- Lines with no planted violation: 120. Flagged: 0.

Read these numbers with care. The same person wrote the rules, the detectors and the test data, so the detectors fit the data. The numbers show the engine does what it was built to do on this data. They say nothing about accuracy on real invoices.

## What is tested

`python -m pytest -q` runs 203 test cases (135 test functions, some parametrized), all passing:

- Readers: field list, round trips for both formats, malformed files (first line, header, field count, dates, terminator, numbers), multi-invoice files, line and total arithmetic including the one-cent tolerance.
- Decimal rule: a source scan that fails on any float literal or `float()` call in the package, the generator and the demo script; every numeric field and every result value is `Decimal`; JSON is read without floats.
- Block billing: the hard cases (one task with semicolons, lists of documents, "and" inside one task, initials and decimals) and real block-billed entries; per-client hour thresholds; the finding does not rewrite the narrative or allocate time.
- Guideline model: schema and parameter validation, every quote is verbatim in its document, every section and page reference resolves.
- Intake: proposals are never enforced; confirming one rule enforces only that rule; number extraction; three reworded sentences the patterns are known to miss.
- Every rule type on small hand-built invoices, including boundaries (day 60 against day 61, exact cap, inclusive against exclusive threshold) and the "not checked" paths.
- Amount at risk: no double counting, caps, invoice-level overlap.
- Waivers: match, scope by timekeeper, invoice, line and date, expiry, required fields.
- Answer key: every planted violation found, zero findings outside the key, the generator is deterministic and matches `data/`, and a fresh demo run matches the committed `output/` and `index.html`.
- Outputs and CLI: self-contained HTML with no external references, escaping, summary numbers, timekeeper notes, CSV, JSON, comparison table, and the three commands.

## What is not done

- **LEDES**: the reader is implemented from memory and has not been checked against the published specification. Only LEDES 1998B is attempted. It has only read files this project wrote. See `FORMAT_NOTES.md`.
- **UTBMS codes**: `data/utbms_sample_codes.json` is a sample subset, unverified against the published code set.
- **Intake**: pattern matching only. The patterns were written alongside the five sample documents and find all 61 sample rules in them, which is a regression check and not a measure of recall. Reworded sentences are missed (three examples are in the tests). Proposed parameters and severities need checking; on the sample documents three of 61 proposals differ from the confirmed rule. A person still has to read the whole document. No PDF or Word input.
- **Detection is keyword and pattern based.** Travel, research, internal conferences, clerical work, attendance at events and AI use are recognised by listed phrases, codes or flags. Work described in other words is missed. Undisclosed AI use cannot be seen from an invoice unless the time system flags it.
- **No history across invoices.** Research limits, staffing limits and duplicates are checked within one invoice. Budget checks rely on a billed-to-date figure supplied in the matter record.
- **Receipts, cost and AI flags** exist only in the CSV layout. For LEDES files those checks report "not checked".
- **Amounts at risk are estimates** from the stated rules. Staffing and rounding findings are not quantified.
- No connection to any billing or e-billing system, no user accounts, no audit trail beyond the files, no editing of invoices.
- One rule of each type per client. Currency is not modelled; amounts are plain decimals.
- Not reviewed by anyone who administers real billing guidelines.

## Files

```
billcheck/          package: model, readers, writers, guidelines, intake, blockbilling, engine, waivers, report, scoring, cli
data/               guideline documents and JSON, schema, matters, waivers, sample codes, invoices, ANSWER_KEY.json
output/             sample outputs written by run_demo.py
tests/              pytest suite
generate_data.py    seeded synthetic data generator
run_demo.py         one-command demo
index.html          static demo page written by run_demo.py
FORMAT_NOTES.md     assumptions about LEDES 1998B, the CSV layout and UTBMS codes
```
