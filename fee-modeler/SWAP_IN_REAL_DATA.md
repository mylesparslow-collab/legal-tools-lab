# Swapping in real data

This demo has only ever seen synthetic data. Nothing here claims to read any particular billing
product's export. What it reads is a canonical schema, reached through a mapping file you write for
whatever export the firm can produce. Expect the first real run to surface problems this document
does not anticipate.

Do the steps in order. Do not look at a pricing memo until the back-test has run.

1. Get the export approved and placed somewhere appropriate for client-confidential data. Not this repo.
2. Write a mapping file.
3. `python -m feemodel profile <export> --mapping <mapping.json> --rate-card <rates.json> --cost-rates <costs.json> --task-codes <codes.json>`
4. Fix what it reports. Repeat until it says ready, and read every warning.
5. `python -m feemodel backtest --data <export> --mapping <mapping.json> ...` and read, for each matter
   type, how many back-tested matters cost more than the P75 and P90 figures against what the bands imply.
6. Only then price a proposal, and only for matter types the back-test supports.

## 1. Fields needed

Four tables. `required` means the tool cannot run without it. `optional` fields each unlock something;
the profiler says what is lost when one is missing.

### matters

| Field | Type | Required | Why |
|---|---|---|---|
| matter_id | text | required | Joins everything |
| matter_type | text | required | Comps are matched on it. It must mean the same thing across years |
| status | open / closed | required | Open matters are never comps |
| open_date | date | required | Back-test ordering; date-window phases |
| close_date | date | required for closed matters | A closed matter without one cannot be a comp |
| close_reason | completed / settled_early / transferred / other | optional | Without it, matters that ended early pull every figure down, unflagged |
| forum | text | optional | Selection rule |
| num_parties | whole number | optional | Selection rule; scope assumption |
| amount_band | text | optional | Selection rule. Supply the band order in the proposal's `band_order` |
| num_units | whole number | optional | Facilities, contracts or similar; selection rule; scope assumption |
| hearing_occurred | yes / no | optional | Selection rule |
| hearing_date | date | optional | Lets the date-window fallback place hearing time |
| client_id | text | optional | Not used in modeling. Leave it out if you can |

### time_entries

| Field | Type | Required | Why |
|---|---|---|---|
| entry_id | text | required | Duplicate detection |
| matter_id | text | required | |
| timekeeper_id | text | required | Level lookup |
| work_date | date | required | Date worked, not date posted or billed |
| hours_worked | number | required | Hours as recorded, before any write-down |
| rate | number | required | The hourly rate applied at the time |
| hours_billed | number | optional | Without it write-downs are invisible and billed is assumed equal to worked |
| level | text | optional | Level at the time of the entry. If absent, the timekeepers table is required |
| task_code | text | optional | Without it every phase figure uses date windows and is low confidence |

### timekeepers (not needed if every entry carries its level)

| Field | Type | Required | Why |
|---|---|---|---|
| timekeeper_id | text | required | |
| level | text | required | Must match a level in the rate card and the cost rate file |
| effective_from | date | optional | One row per level held. Without it a promoted timekeeper's old hours are valued at the new level |

### invoices

| Field | Type | Required | Why |
|---|---|---|---|
| invoice_id | text | required | |
| matter_id | text | required | |
| invoice_date | date | required | |
| amount_billed | number | required | Fees only, if fees can be separated from expenses |
| amount_collected | number | required | Cash applied to fees |
| amount_written_off | number | optional | Without it, write-offs cannot be told apart from unpaid balances |

### Three small input files

- Rate card: `{"current_label": "...", "current": {"<level>": "<rate>", ...}}`. One current standard rate per level.
- Cost rates: `{"cost_per_hour": {"<level>": "<cost>", ...}}`. From finance. The demo values are placeholders.
- Task codes: `{"prefixes": {"<prefix>": "<phase>"}, "exact": {"<code>": "<phase>"}}`. Phases are
  assessment, drafting, discovery, hearing, closing.

Write money as quoted strings, for example `"410.00"`. The loader refuses floats in these files.

## 2. The mapping file

See `data/mappings/export_a.json` and `data/mappings/export_b.json`. Per table:

| Key | Meaning |
|---|---|
| `file` | File name inside the export folder |
| `delimiter` | Default `,` |
| `encoding` | Default `utf-8-sig` |
| `date_format` | Python `strptime` format, default `%Y-%m-%d` |
| `columns` | canonical field -> column header in the file |
| `value_maps` | canonical field -> {value in file: canonical value}, for coded fields such as status |
| `scale` | canonical field -> `{"divide_by": "60"}` or `{"multiply_by": "..."}`, for example minutes to hours |
| `true_values`, `false_values` | Text that means yes and no |
| `null_values` | Text that means blank, in upper case |

Numbers may carry `$`, thousands commas and parentheses for negatives. Run
`python -m feemodel profile <export>` with no mapping to list the files and column headers found.

Not handled by the mapping, so prepare these before loading: one file per table (join or split first),
reversal and negative entries (net them), time in units other than hours or a fixed multiple of hours,
several currencies, and fees mixed with expenses on one invoice line.

## 3. Minimum history

These are the tool's own settings, chosen to stop it speaking too soon. They are not benchmarks.

| To do this | The matter type needs |
|---|---|
| Show any figure | 8 clean closed comps after the selection rules (`min_comps`). Clean means closed, with a close date, completed normally |
| Read the P90 as more than one or two matters | 20 or more comps. Below 20 the memo carries a small-sample warning |
| Have its bands judged by the back-test | 10 or more back-tested matters. A matter can only be back-tested if 8 same-type matters had closed before it opened, so this takes well over 18 clean closed matters spread over time. On the synthetic data, types with 32 to 69 clean closed matters over six years produced 19 to 53 back-tested matters |
| Have its planning bands adjusted from past outcomes | 12 or more back-tested matters of the type that closed before the proposal date. With fewer, the bands are the finite-sample step alone and the memo says "not adjusted" |
| Place a P90 at all | 9 or more comps. With 8 the planning P90 is the largest comp and the memo calls it a floor |
| Detect a change in cost over time | 16 or more clean closed matters (8 each side of the change), and the change has to be large: on the synthetic firms a 1.7x step was caught in 13 of 20 and a 12% a year drift in 10 of 20 |
| Get a recent-only version when a change is flagged | 8 clean closed comps opened since the estimated change date (`min_comps`). With fewer, the default uses the whole history and warns; `drift_action: recent_only` refuses |

Also needed: time entries covering each comp's whole life (a matter opened before the export window
starts will look cheap), and several years of history so later matters have earlier ones to be modeled from.

## 4. Data-quality checks to run first

`profile` runs these and prints what it finds. A failed check blocks; a warning needs a decision.

| Check | Why it matters |
|---|---|
| Every table present, every required field mapped | Nothing runs otherwise |
| Rows that fail to parse (dates, numbers, coded values) | More than 1% of rows dropped is treated as blocking |
| Duplicate ids; entries or invoices pointing at unknown matters | Double counting; lost time |
| Negative hours or rates | Reversals not netted |
| Closed matters with no close date, or closing before opening | Cannot be comps |
| Closed matters with no time | They would look free |
| Time dated before open or after close | Late time; matters reopened; wrong dates |
| Billed hours above worked hours | Write-ups, or columns swapped |
| Zero-rate entries | Raw value understated |
| Share of hours with a task code that maps to a phase; codes not in the map | Phase confidence |
| Every level in the data has a rate and a cost rate | Normalization would fail |
| Timekeepers with time at more than one level | Confirms level history is working |
| Close reasons present | Abnormal closes cannot be excluded otherwise |
| Closed matters with fees neither collected nor written off | Collected figures not final |
| Invoiced fees against billed time, per closed matter | Invoices may include expenses, flat fees or discounts |
| Clean closed matters per matter type | Which types can be modeled at all |

Checks the profiler does not do, to do by hand:

- Read 20 random matters end to end against what the responsible lawyer remembers of them.
- Confirm matter types were assigned consistently over the years, and whether codes were merged or renamed.
- Look for one matter number used for several pieces of work, and one piece of work split across numbers.
- Look for matters that were already fixed or capped fee. Their hours may have been recorded differently.
- Look for time recorded in bulk at month end, which breaks date-window phases.
- Check whether non-billable and written-off time is in the export at all.

## 5. Questions for finance

1. Is hours worked the hours as first recorded, or after pre-bill edits? Can both be exported?
2. Is the rate on a time entry the standard rate, the client's agreed rate, or the rate after discount?
3. Where do write-downs happen (pre-bill, on the invoice, after the invoice), and which export field shows each?
4. Do invoice amounts include expenses and taxes? Can fees be separated?
5. How are write-offs recorded, and how are they told apart from balances still owed?
6. Is collected cash applied to specific invoices and split between fees and expenses?
7. Is non-billable time on client matters in the export? Is time on matters that were never billed?
8. What closes a matter in the system, and how late does time and cash arrive after that?
9. Is there a field for how a matter ended? If not, who could classify the abnormal ones?
10. How consistent are matter-type codes across offices, groups and years? What changed, and when?
11. Which matters were on fixed, capped or other non-hourly arrangements, and can they be identified?
12. What task or phase codes exist, since when, and how reliably are they used by practice group?
13. What levels exist, how do they map to the current rate card, and is level history kept with dates?
14. What cost per hour by level should be used for margin, what does it include, and as of when?
15. Which scoping facts are recorded per matter (forum, parties, amounts, units, hearings)? Where do the others live?
16. How far back is the data reliable? Were there system changes or migrations inside that window?
17. Who must approve use of this data for pricing analysis, and what must be removed or masked first?

## 6. What to expect

- The first profile will fail. That is its job.
- Matter types will be the hard part. If a type mixes very different work, no rule will rescue it.
- Price from the planning figures, not the comp quantiles. On the synthetic data the plain comp
  quantiles understated overruns for several types and the planning figures did not, but the planning
  figures are wider: expect a planning P90 well above the largest fee anyone has in mind.
- The synthetic result does not carry over. Run `python -m feemodel backtest` on the real export and
  read the planning columns for each matter type before using any band in a quote. Decide in advance
  how many overruns at the planning P90 are acceptable, and which types fall short.
- The planning bands were chosen and measured on generated data with one kind of cost distribution.
  Real matter costs may have heavier tails or change in ways the generator does not produce.
- The change check is a prompt to look, not drift detection. On the synthetic firms it caught a 1.7x
  step in 13 of 20, a 12% a year drift in 10 of 20, and flagged between about 1 in 15 and 1 in 37
  type-checks where nothing was planted (15 of 220 and 6 of 220 on two sets of seeds).
- When it flags a matter type, the memo shows two versions, recent comps only and the whole history,
  and prices from the higher at each band. A flag can raise a figure and never lower one. Ask the
  practice group what happened around the estimated date; the date is rough.
- If the flag says costs fell and the group confirms a real change (new staffing, a narrower kind of
  work), set `"drift_action": "recent_only"` in the proposal to use the recent comps only. Before
  doing so, rule out the usual false cause: of matters opened recently, only the quick ones have
  closed yet, so the recent end of any history looks cheap.
- If the group knows of no change, set `"drift_action": "ignore"` for that proposal.
- When it does not flag a type, that is not evidence of stability. Look at the overrun counts and ask
  the practice group.
- Some of the most-requested matter types will not have enough clean history. The tool will say so.
