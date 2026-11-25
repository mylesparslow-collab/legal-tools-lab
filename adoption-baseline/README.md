# Adoption baseline

Personal portfolio demo. All data is synthetic. Not legal advice.

A small tool that answers one question for a law firm rolling out approved AI assistants: who
uses what, how often and for what, by practice and role. It is built to be run once as a
baseline and then repeated each quarter.

It reads three things:

- a **roster** (who works here, their role, practice, office, licences, start date and leave),
- **usage exports** from two assistants, called "Assistant A" (a general AI assistant) and
  "Assistant B" (a productivity-suite assistant) in the sample data,
- a short anonymous **survey**.

It writes one HTML report a partner can read in two minutes, plus `baseline.json` and CSVs.
The only yardstick is the firm's own targets in `data/targets.json`. Nothing here compares the
firm with anyone else.

## Run it

```
python run_demo.py
```

Python 3 standard library only. No network. This rebuilds everything in `output/` from
`sample_data/`. Then open `output/baseline_report.html`.

The same steps one at a time:

```
python -m baseline ingest                      # load exports, write output/data_quality.json
python -m baseline report                      # metrics, baseline.json, CSVs, HTML report
python -m baseline report --period-end 2026-10-18 --prefix checkpoint
python -m baseline compare output/checkpoint.json output/baseline.json
python -m baseline survey                      # re-render survey.html and SURVEY.md from survey.json
python generate_synthetic.py                   # regenerate sample_data/ and ANSWER_KEY.md (seeded)
python -m pytest                               # run the tests
```

`report` and `ingest` take `--roster`, `--source export.csv=mapping.json` (repeatable),
`--period-start`, `--period-end` and `--out-dir`. `report` also takes `--survey`, `--targets`
and `--min-group`. Defaults come from `data/config.json`.

## What is in the folder

| Path | What it is |
|---|---|
| `baseline/ingest.py` | Mapping-driven loader from any CSV export to the canonical day table |
| `baseline/roster.py` | Roster loader and the denominator rule |
| `baseline/metrics.py` | The measures. Written definitions are in `METRICS.md` |
| `baseline/suppress.py` | Small-group and complementary suppression |
| `baseline/survey.py` | Survey validation, tallies, survey-versus-log gap |
| `baseline/targets.py` | Pass, not yet, or cannot tell |
| `baseline/compare.py` | Change between two baselines |
| `baseline/summary.py`, `report.py`, `outputs.py` | Summary sentences, HTML report, CSVs |
| `mappings/` | Two example column mappings |
| `data/config.json`, `data/targets.json` | Period, thresholds, file paths; the firm's targets and pilot gate |
| `survey/` | `survey.json` (source), `survey.html` (fillable form, saves a JSON file), `SURVEY.md` (printable, with design notes and known biases) |
| `sample_data/` | Synthetic roster, two exports, survey responses, `answer_key.json` |
| `ANSWER_KEY.md` | What the generator planted in the sample data |
| `output/` | Sample outputs, committed |

## Export formats: read this before using real files

**This tool is not compatible with any vendor's usage export out of the box, and does not claim
to be.** I have not seen the real column layouts of any vendor's export. The two sample exports
are shapes I made up:

- `assistant_a_events.csv`: one row per interaction, ISO timestamp with a UTC offset, user by email.
- `assistant_b_daily.csv`: one row per user per day, semicolon-separated, day/month/year dates in
  two styles, one count column per feature, user by display name.

Ingestion is driven by a JSON mapping per source (`mappings/*.json`). To use a real export you
must write a mapping for it and check it against the real file: which column is the user, how
dates are written, what one "interaction" means in that export, what the duplicate key is.
Then read the data-quality output before trusting any rate. If a mapping names a column that is
not in the file, ingestion stops and says which.

Everything lands in one canonical table: `person_id, date, tool, feature, interactions`.

## Choices worth knowing about

- **Denominators come from the roster.** People with no usage count as zero. People on leave
  for every weekday of a week, not yet started, or left are outside that week's denominator.
  The rule is in `METRICS.md` and tested.
- **Nothing is dropped silently.** Every dropped, repaired or flagged row is counted by reason,
  and rows read always equals rows kept plus rows dropped.
- **Small groups are not shown.** Any figure describing fewer than 5 people is withheld, and a
  further figure is withheld where a total would reveal it. This is a privacy choice. The
  threshold is configurable.
- **Individual-level output is off by default.** `baseline.json`, the CSVs and the report hold
  no person ids, names or emails. `--include-individuals` and `--write-events` exist and say
  what they are doing.
- **Medians before means.** A few heavy users dominate volume, so intensity is reported as
  quartiles with the mean alongside.
- **"Cannot tell" is a real answer.** A target for a group that is too small, or built on an
  export that is missing or mostly unmatched, is not given a pass or a fail.
- **A change is only called for groups of 30 or more that move 5 points or more.** No p-values.
- **Every number in the report summary is computed** from `baseline.json`. A test checks it.

## What is tested

`python -m pytest` runs 141 tests. They cover:

- Ingestion: both export shapes, several date formats, time zones as given and converted,
  exact and conflicting duplicates, users missing from the roster, case and spacing repair for
  emails and names, ambiguous names, bad and zero counts, rows outside the period, unmapped
  features, use without a licence, invalid mappings, and row reconciliation.
- Roster and denominators: start dates, leave covering a whole week or part of one, leavers,
  practice changes, unreadable roster rows, roster people with no usage counting as zero.
- Metrics: weekly active, regular use, per-tool denominators, unused licences, quartiles,
  intensity, breadth, and that every per-tool figure counts licence holders only.
- Suppression: primary and complementary rules, configurable threshold, and a sweep of
  `baseline.json` for any published cell under the threshold.
- Targets and compare: each status, each call, and the refusal to call small groups.
- Survey: question count and coverage, the form is self-contained, responses validate,
  free text is never reproduced.
- Planted truths: the analyser recovers every item in `ANSWER_KEY.md` from the messy exports,
  including exact weekly numerators and denominators for all 13 weeks.
- Report: summary sentences match `baseline.json`, percentages carry numerator and
  denominator, no scripts or external resources, light and dark styles present, and committed
  outputs equal a fresh run.

## What is not done

- **No real export has been ingested.** See above. Only CSV is read; no spreadsheets, JSON or APIs.
- **Time zones** are fixed UTC offsets only. No named zones, no daylight-saving rules.
- **Identity matching** is exact after ignoring case and spacing. No fuzzy matching: a changed
  surname or a nickname shows up as "not on the roster" and is counted, not fixed.
- **Suppression is per table and per column.** It does not protect against comparing tables
  with each other or across quarters, and it does not hide a group of 5 or more where the rate
  is 0% or 100%. Denominators can differ slightly between columns of the same row. Before real
  use this needs review by whoever owns privacy at the firm.
- **The survey gap cannot separate over-claiming from non-response.** There is no weighting,
  and no check for someone answering twice, because responses are anonymous.
- **Leave is whole days on weekdays.** No public holidays, part-time patterns or secondments.
- **Licences are a snapshot.** There is no licence history, so a licence granted last week
  looks the same as one held all quarter.
- **Interactions are not comparable between tools.** A chat message and a daily prompt count
  are different units.
- **No practice-by-role cross table.** It would need two-way suppression.
- **The change rule is a threshold, not a test.** The demo comparison uses an earlier cut-off
  of the same 13 weeks to stand in for a previous quarter.
- **The report has no scripts.** Hover text on charts uses the browser's own tooltips, which do
  not appear on touch screens; the table under each chart has the same numbers. It was checked
  by eye in one headless browser only, and has had no screen-reader testing.
- **Logs only cover the approved tools.** Use of anything else is visible only through one
  survey option.
- The practice and office lists in `survey.json` are the synthetic ones and must be edited.
