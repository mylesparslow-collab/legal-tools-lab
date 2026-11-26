# Fee modeler

Personal portfolio demo. All data is synthetic: every client, matter, timekeeper and rate is invented.
Not financial, pricing or legal advice. Never run this demo on real matter data; read
`SWAP_IN_REAL_DATA.md` before any trial at a firm.

## What it does

It models fixed and capped fees from past matters of the same type. The user is a pricing or practice
lead deciding what to quote. The tool shows the evidence and the risk. A person decides the price.

For a proposed matter it:

1. Picks comparable closed matters by matter type and scoping attributes (forum, parties, amount band,
   units, hearing, recency). The rules are printed with every result and can be changed. Open matters
   are never comps. Matters that closed abnormally are excluded by default and flagged if included.
   With fewer than 8 comps (configurable) it refuses to give any figure and says what is missing.
2. Builds each comp's cost: hours by phase and by timekeeper level; worked, billed and collected side by
   side so write-downs and write-offs are visible; raw amounts and amounts normalized to today's rate card.
3. Shows a distribution, not a point. Two sets of figures, labelled apart:
   - Planning figures (P25, P50, P75, P90): the ones to price from. They are built to hold up on the
     next matter, and the back-test below measures whether they do.
   - Of the comps (descriptive): plain quantiles of the comps, with seeded bootstrap intervals. They
     describe the comps and are kept for comparison. In the back-test they understate overruns.
   n is on every figure, with plain warnings for small or skewed samples. No regression models.
4. Tests fee structures: fixed, capped, phased fixed, and fixed with a collar. For each it says where
   the fee sits among the planning figures, how those figures held up in the back-test, the margin if
   the matter comes in at planning P50, P75 or P90, and the in-sample counts on the comps. It also
   gives the planning fee for a target chance of staying within the fee.
5. Writes scope assumptions and exclusions from the comp evidence, for example which phase drove the
   expensive comps, each with the counts and amounts behind it.
6. Applies optional per-phase hours reductions that the user types in, with a before/after table,
   labelled as the user's assumptions. Default is zero. The tool predicts nothing about AI.
7. Runs a change check on each matter type: a prompt to look, not drift detection. It asks whether
   costs differ before and after some date, without being told the date. On a flag it builds two
   versions, recent comps only and the whole history, shows both, and sets every planning figure to
   the higher of the two. A flag can therefore raise a quote but never lower it. A person who has
   confirmed a real change can set `"drift_action": "recent_only"` in the proposal (this may lower the
   figures); `"drift_action": "ignore"` drops the check.
8. Back-tests itself: walks forward through history, models each past matter only from what was known
   the day it opened (comps, change check and band adjustment alike), and reports how often the
   actual cost ran over the planning P75 and P90, beside the same counts for the plain comp quantiles.
   That result is on every memo.

## Run it

```
python run_demo.py
```

That regenerates the synthetic data (seeded), profiles both export shapes, runs the back-test, writes
seven pricing memos to `output/` and rebuilds `index.html`. The two studies are separate commands. Python 3 standard library only. No network.

Open `index.html` for the demo page, or `output/memo_P-001.html` for a memo.

```
python -m feemodel profile data/export_b --mapping data/mappings/export_b.json
python -m feemodel backtest --out output
python -m feemodel comps --proposal data/proposals/P-001.json
python -m feemodel price --proposal data/proposals/P-001.json
python -m feemodel calibration-study --out output    # planning bands on 20 other generated firms; under a minute
python -m feemodel drift-sensitivity --out output    # change check, old rule beside new; about ten minutes
python -m pytest -q
```

`profile` exits 2 when an export is not ready. `price` and `comps` exit 3 when the tool refuses.

## Terms

| Term | Meaning |
|---|---|
| Raw worked value | Hours worked x the rate in force when the work was done |
| Normalized value | Hours worked x today's rate card for each level. This is "cost" in the distribution |
| Billed | Hours billed x rate, after write-downs |
| Collected | Cash against invoices. Billed minus collected is write-offs or unpaid |
| Internal cost | Hours worked x cost per hour by level, from `data/cost_rates.placeholder.json` |
| At or under the fee | The comp's normalized value is no more than the fee |
| No loss | The fee arrangement would have paid at least the comp's internal cost |
| Margin in the P90 case | 9 in 10 comps would have done better than this |

The cost rates file holds placeholder values. They are an input, not a finding. Replace them.

## Inputs

- `data/export_a`, `data/export_b`: the same synthetic firm in two differently shaped exports.
- `data/mappings/*.json`: column mappings from each shape to the canonical schema (`feemodel/schema.py`).
- `data/rate_card.json`: current standard rate per level, used for normalization.
- `data/cost_rates.placeholder.json`: internal cost per hour by level. Placeholder.
- `data/task_code_phases.json`: task code to phase map.
- `data/proposals/*.json`: proposed matters, with selection rules, scenarios and hours-reduction assumptions.

## What the back-test says on the synthetic data

Every number in this section comes from a command. `python -m feemodel backtest` prints the first
table (also in `output/backtest.txt`). The two studies are `python -m feemodel calibration-study` and
`python -m feemodel drift-sensitivity`; their committed results are in `output/calibration_study.txt`
and `output/drift_sensitivity.txt`.

### Two weaknesses that were measured, and what was done

An earlier version priced from plain quantiles of the comps and had a drift rule that compared the
later half of closes with the earlier half. Both were measured and found weak:

- The plain quantiles understated overruns. On the shipped data 60 of 385 back-tested matters cost
  more than their predicted P90, where the band implies about 39.
- The drift rule missed a 1.7x step in about half of generated firms, and a doubling in 6 of 20.

The first is fixed: planning bands, below. The second is improved but not fixed: the new change
check catches more, still misses a lot, and raises false flags. So it is treated as a prompt to
look, and the tool is built so that a wrong flag cannot lower a quote. The old figures stay in the
outputs for comparison.

### Planning bands against the plain comp quantiles (shipped data, seed 20260)

Matters that cost more than the band, with the count the band implies. "Understates" means more
overruns than chance would explain (exact one-sided binomial check, 1 in 20).

| Matter type | Old: over comp P75 | Old: over comp P90 | Old verdict | New: over planning P75 | New: over planning P90 | New verdict |
|---|---|---|---|---|---|---|
| administrative_licensing_appeal | 5 of 27 (about 7) | 1 of 27 (about 3) | within chance | 3 of 27 (about 7) | 1 of 27 (about 3) | within chance |
| commercial_lease_review | 11 of 38 (about 10) | 7 of 38 (about 4) | within chance | 11 of 38 (about 10) | 4 of 38 (about 4) | within chance |
| contract_dispute_arbitration | 2 of 19 (about 5) | 0 of 19 (about 2) | within chance | 1 of 19 (about 5) | 0 of 19 (about 2) | within chance |
| election_law_advisory | n/a | n/a | not back-tested | n/a | n/a | not back-tested |
| employment_single_plaintiff_defense | 15 of 41 (about 10) | 10 of 41 (about 4) | understates | 13 of 41 (about 10) | 7 of 41 (about 4) | within chance |
| facility_change_of_ownership | 9 of 37 (about 9) | 8 of 37 (about 4) | understates | 9 of 37 (about 9) | 3 of 37 (about 4) | within chance |
| internal_investigation | 13 of 31 (about 8) | 9 of 31 (about 3) | understates | 10 of 31 (about 8) | 5 of 31 (about 3) | within chance |
| ordinance_drafting | 16 of 41 (about 10) | 5 of 41 (about 4) | understates | 9 of 41 (about 10) | 3 of 41 (about 4) | within chance |
| paga_response | 15 of 35 (about 9) | 7 of 35 (about 4) | understates | 9 of 35 (about 9) | 3 of 35 (about 4) | within chance |
| public_records_litigation | 16 of 53 (about 13) | 9 of 53 (about 5) | within chance | 13 of 53 (about 13) | 4 of 53 (about 5) | within chance |
| public_works_bid_protest | 10 of 41 (about 10) | 3 of 41 (about 4) | within chance | 8 of 41 (about 10) | 2 of 41 (about 4) | within chance |
| regulatory_compliance_audit | 2 of 22 (about 6) | 1 of 22 (about 2) | within chance | 2 of 22 (about 6) | 0 of 22 (about 2) | within chance |
| All types | 114 of 385 (about 96) | 60 of 385 (about 39) | understates | 88 of 385 (about 96) | 32 of 385 (about 39) | within chance |

The old columns differ slightly from the previous README (which showed 117 and 64 of 385) because the
shipped data now plants a 1.7x step in `internal_investigation`, not 2.0x. See `ANSWER_KEY.md`.

"Within chance" is not a pass. `internal_investigation` and `employment_single_plaintiff_defense`
still show more overruns than implied (5 of 31 and 7 of 41 over the planning P90); the counts are
too small to call either way. They are printed so the reader can judge.

### How the planning bands are made

1. Finite-sample quantile. With n comps, the q band is the comp at position ceil((n + 1) x q) in sorted
   order. The interpolated quantile sits lower and under-covers on small samples.
2. Upward adjustment from the type's own past. For earlier matters of the same type whose cost is
   already known, take actual cost over the step-1 band as it would have been set the day each one
   opened. The factor is the ceil((m + 1) x q)-th of those m ratios, never below 1. It needs at least
   12 such outcomes. With fewer, the band is step 1 alone, the memo labels it "not adjusted" and warns.
3. With fewer than 9 comps the P90 position is past the largest comp. The largest comp is used and the
   memo says the figure is a floor.

This differs from the suggested design in two ways, both chosen on generator seeds 101 to 110 before
looking at any other seeds. The adjustment only raises a band, because a band that is too low is the
costly error; letting it lower bands brought the overall rate closer to nominal but left more matter
types understating. And it uses the same matter type only; pooling ratios across types when a type
had little history was tried and was worse per type. Those two variants are not shipped, so no
numbers are quoted for them. The one alternative still reachable by command is the amount of
history required: `--min-history 20` on seeds 101 to 110 gives 291 of 3,737 over P90 against 254 of
3,737 for the shipped 12 (`output/tuning/`).

### Planning bands on 20 other generated firms

Seeds 1 to 20, generator as shipped. These seeds were not looked at until the method was fixed.
`python -m feemodel calibration-study`.

| | Over P75 (implied 25%) | Over P90 (implied 10%) | Type-runs judged to understate at P75, at P90 (of 220) |
|---|---|---|---|
| Comp quantiles (old) | 2,220 of 7,490 (29.6%) | 1,096 of 7,490 (14.6%) | 41, 51 |
| Finite-sample step alone | 1,883 of 7,490 (25.1%) | 682 of 7,490 (9.1%) | 15, 16 |
| Planning bands (new) | 1,678 of 7,490 (22.4%) | 552 of 7,490 (7.4%) | 2, 2 |

Overall share of back-tested matters over the planning P90, seed by seed (old comp-quantile rate in
brackets):

| Seed | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Over planning P90 | 8.4% | 6.2% | 7.2% | 6.7% | 6.8% | 7.5% | 7.3% | 6.1% | 5.8% | 7.7% |
| (old) | (14.1%) | (13.8%) | (15.0%) | (12.4%) | (14.6%) | (14.4%) | (13.7%) | (13.3%) | (12.0%) | (15.6%) |

| Seed | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|
| Over planning P90 | 9.1% | 6.4% | 10.0% | 8.2% | 6.5% | 6.7% | 9.7% | 6.4% | 7.1% | 8.0% |
| (old) | (16.6%) | (14.9%) | (17.3%) | (15.6%) | (12.9%) | (14.2%) | (18.1%) | (12.5%) | (15.0%) | (17.2%) |

Every seed is at or under 10% (5.8% to 10.0%). Where the planning bands still understate, by the
same check: seed 13 `paga_response` at P75 (11 of 26), seed 15 `internal_investigation` at P90 (8 of
29), seed 17 `facility_change_of_ownership` at P90 (8 of 41), seed 20 `internal_investigation` at P75
(13 of 32). Two of the four are the type with the planted change: until the change check fires, its
bands come from the cheaper period. Four flags in 440 checks is fewer than the 1 in 20 the check
allows by chance.

A flag never lowers a figure. Across seeds 1 to 20 the change check was flagging an unplanted matter
type at the moment of 384 back-test predictions, 139 of them saying costs had fallen. The planning P90
was below the whole-history planning P90 in 0 of them (any band: 0). It was raised above it in 212.
`tests/test_bands_and_drift.py` asserts the zero.

What it costs. The bands are wider and err on the safe side: 7.4% over P90 against an implied 10%,
and the planning P90 is 1.28x the comp P90 for the median back-tested matter. A fee set at a
planning figure is a higher fee than the same label on the old figures. False flags that say costs
rose add to that: they raise figures that did not need raising.

### The change check: a prompt to look

This is not working drift detection. On 20 evaluation firms it caught a planted 1.7x step in 13 of
20, a 2.0x step in 19 of 20 and a 12% a year drift in 10 of 20, and with nothing planted it flagged
15 of 220 type-runs (6.8%). Use a flag as a reason to ask the practice group what happened, and no
flag as no information.

Matters of a type are put in order of opening. Every split with at least 8 matters on each side is
tried, and the one that separates the costs most cleanly (by rank) is the estimated change point. A
type is flagged when no more than 1 in 20 of 1,000 seeded reshuffles of the same costs split as
cleanly, and the medians either side differ by 1.25x or more. No date is supplied.

Thresholds were chosen on seeds 101 to 120 and then left alone. On those seeds
(`python -m feemodel drift-sensitivity --seeds 101-120 --alpha 1/N`, results in `output/tuning/`):

| Reshuffle limit | Flagged at 1.7x | Flagged at 2.0x | Unplanted types flagged, nothing planted |
|---|---|---|---|
| 1 in 50 | 12 of 20 | 19 of 20 | 2 of 220 (0.9%) |
| 1 in 20 (shipped) | 16 of 20 | 19 of 20 | 6 of 220 (2.7%) |
| 1 in 10 | 18 of 20 | 20 of 20 | 14 of 220 (6.4%) |

The aim was 18 of 20 at both 1.7x and 2.0x with unplanted flags at or under 5%. 1 in 10 reaches 18 of
20 at 1.7x but only by letting false flags past the limit, so 1 in 20 was kept and the search
stopped. The smallest-segment and median-ratio settings (8 and 1.25x) were also tried at nearby
values on those seeds and made little difference; they have no command-line switch.

On the evaluation seeds, 1 to 20 (`python -m feemodel drift-sensitivity`):

| Planted in `internal_investigation` | Old rule flagged | New check flagged | New: unplanted types flagged |
|---|---|---|---|
| nothing (1.0x) | 0 of 20 | 0 of 20 | 15 of 200 (7.5%) |
| 1.3x step | 1 of 20 | 5 of 20 | 16 of 200 (8.0%) |
| 1.5x step | 6 of 20 | 11 of 20 | 15 of 200 (7.5%) |
| 1.7x step | 11 of 20 | 13 of 20 | 16 of 200 (8.0%) |
| 2.0x step | 14 of 20 | 19 of 20 | 16 of 200 (8.0%) |
| gradual, 12% a year | 4 of 20 | 10 of 20 | 15 of 200 (7.5%) |

Read plainly:

- 2.0x: 19 of 20, aim met.
- 1.7x: 13 of 20, aim missed. It was 16 of 20 on the threshold seeds.
- Unplanted flag rate: 15 of 220 type-runs (6.8%) with nothing planted, above the 5% aim. It was 6 of
  220 (2.7%) on the threshold seeds. Across both sets that is 21 of 440 (4.8%). The threshold was not
  moved after seeing the evaluation seeds. The old rule flagged 1 of 220.
- Gradual drift of 12% a year: caught in 10 of 20. A step detector is the wrong shape for a slope.
- The estimated date is rough: the median error is 24 to 65 days late at 1.5x to 2.0x, single runs
  range from 191 days early to 407 days late at 2.0x, and at 1.3x the median is 400 days early.

What the default rule does for a type whose costs really changed. Back-tested matters of the planted
type, pooled over the 20 evaluation seeds (582 matters), that cost more than their P90:

| Planted | Over comp P90 (old) | Over planning P90 (new, higher of two on a flag) |
|---|---|---|
| nothing | 84 (14.4%) | 36 (6.2%) |
| 1.3x step | 117 (20.1%) | 55 (9.5%) |
| 1.5x step | 146 (25.1%) | 62 (10.7%) |
| 1.7x step | 170 (29.2%) | 71 (12.2%) |
| 2.0x step | 184 (31.6%) | 79 (13.6%) |
| gradual, 12% a year | 145 (24.9%) | 69 (11.9%) |

At 1.7x that is 12.2% against 29.2%, with the check itself firing in only 13 of 20 firms; the upward
adjustment does part of the work where the check stays silent. It is still above the 10% the band
implies: between the change and its detection, bands come from the cheaper period.

On the shipped data the check flags `internal_investigation` (planted; estimated from 2022-04-12
against a planted 2023-01-01, 1.78x against a planted 1.7x) and also
`employment_single_plaintiff_defense` (nothing planted; it says costs fell to 0.63x from 2024-01-11).
The second is a false alarm and is left visible: memo P-005 shows the recent-only version (planning
P90 $138,000) beside the whole history ($616,100) and prices from the higher.

The rule for "understates": an exact one-sided binomial check. A band is said to understate overruns
when seeing that many matters above it, or more, would happen less than 1 time in 20 if the band were
right. The 1-in-20 line is a setting of this tool. With about a dozen types and two bands each, an
occasional flag by chance is expected. Fewer overruns than implied is only a mild note, and the
middle band (P25 to P75) keeps a plain 15-point note. At least 10 back-tested matters are needed
before any judgement is made.

## Design notes

- Money and hours are `decimal.Decimal` from the loader to the JSON. Quantiles and the bootstrap run on
  Decimal directly (the interpolation is Decimal arithmetic; resampling draws integer indexes), so no
  float conversion is needed for statistics. Floats appear in two places only: pixel positions in
  `memo.py`, and random draws inside the synthetic generator before values are written as exact tenths
  of an hour. JSON carries amounts as strings to the cent. Displayed amounts are rounded to the nearest
  100 from 10,000 up and the nearest 10 below.
- Phase comes from the task code when it maps to a phase. Otherwise a date-window fallback is used:
  the first 15% of the matter's life is assessment, to 45% drafting, to 80% discovery, the rest closing;
  time in the 21 days up to a recorded hearing date is hearing. A matter with more than 20% of hours
  placed this way is marked low confidence.
- Back-test leakage guards: a comp must have closed strictly before the tested matter opened; time and
  invoices dated on or after the open date are ignored even on comps that had closed; a check runs after
  every back-test and fails loudly if either is violated. Both sides are valued at today's rate card,
  which is a change of units and carries no information about outcomes.
- In sample and out of sample are kept apart. The share of comps at or under a proposed fee is counted
  on the same comps the figures came from, so it flatters the fee. The memo labels it "in sample". The
  planning columns come first: where the fee sits among the planning figures, and the walk-forward
  result at the bands either side. The walk-forward test matches on matter type only, so it is
  evidence about the type, not about the proposal's narrower comp set. If the type was not
  back-tested, or has fewer than 10 back-tested matters, the memo says that instead of a figure.
- The adjustment that raises the planning bands is learned only from the past. In the back-test, a
  matter's bands use ratios only from same-type matters that had closed before it opened, each ratio
  taken against the band that matter would have been given on its own opening day. The look-ahead
  check covers these matters as well as the comps.
- The change check runs inside the back-test too, as of each matter's opening day, with the same
  higher-of-two rule, so the back-test measures the tool as it now behaves, including false alarms
  and late detection.
- Why the higher of two. A flag is wrong often enough (6.8% of unplanted type-runs) that acting on it
  in both directions would sometimes cut comps to a cheap recent handful and lower a quote on noise.
  Taking the higher version at each band makes a wrong flag cost at most a higher figure. Lowering
  is left to a person, through `drift_action: recent_only`, after checking why costs fell.
- Margin at a planning figure uses the comps' total cost over their total standard value to turn the
  figure into a cost. The planning fee for a target chance uses the same two steps at the target
  probability, and is never set below a planning band for a lower probability.
- The old drift rule (later half of closes against earlier half) is still computed, only so the two
  can be compared. Nothing acts on it. All thresholds are settings of this tool, not industry figures.
- The bootstrap interval says how much a quantile would move with a different draw of comps. It is not
  a forecast range for the next matter.

## What is tested

151 tests, all passing (`python -m pytest -q`):

- Money: floats rejected, currency text parsed, display rounding.
- Loader: renaming, rescaling (minutes to hours), value maps, bad dates, missing columns and files,
  orphans, duplicates, negatives; both export shapes load to identical canonical data; no floats.
- Profile: clean exports pass; missing tables, columns and rate levels fail; optional gaps come with
  consequences; planted late time, unpaid balances and unmapped task codes are found; exit codes.
- Cost: task-code and date-window phases, confidence flag, raw vs normalized vs internal cost by hand,
  write-downs and uncollected, as-of filtering, hours reductions.
- Comps: every rule, strict as-of, abnormal closes, refusal message with what is needed.
- Statistics: quantiles by hand, order statistics, seeded bootstrap, warnings.
- Pricing: each scenario by hand, target fee meets its target and is the smallest that does,
  hours-reduction assumptions default to zero, scope assumptions cite their evidence.
- Back-test: bands by hand, no comp closed on or after the open date, the guard catches a tampered
  record, a later matter cannot change earlier predictions, late time is hidden, drift check.
- Answer key: the planted truths in `ANSWER_KEY.md` are recovered, including the refusal of the thin
  type and the flag, estimated date and ratio on the drifting type; the generator reproduces the committed files byte for byte.
- Overruns and memo: the exact binomial check by hand; more overruns than implied is never reported as
  fine; the same overrun wording reaches every output; the memo carries its type's back-test and labels
  in-sample and out-of-sample figures; not-back-tested and under-10 cases say so.
- Planning bands: positions by hand; the finite-sample band covers a left-out matter where the
  interpolated quantile does not; the adjustment needs 12 outcomes and never lowers a band; the
  unadjusted and too-few-comps-for-P90 cases warn; scenarios and the target fee use the planning bands.
- Change check: finds a clean step and its exact date unaided, flags falls as well as rises, leaves
  noise, small shifts and short histories alone; in the walk-forward it cannot fire before the change
  exists, takes the higher of the two versions once it does, and the look-ahead guard catches a
  tampered adjustment record.
- A flag can only raise: no planning band is ever below its whole-history version, in a hand-built
  history where costs halve, on every back-test record of the shipped data, on the 384 unplanted
  flagged predictions of the 20-seed study, and for every matter type priced with and without the
  check (bands, target fee and scenario margins).
- The three settings: default (higher of two, both versions shown), `recent_only` (26 of 41 comps,
  may lower, refuses when too few), `ignore` (whole history with a warning).
- Measurements are pinned: old against new overruns for every type on the shipped data; the committed
  drift study (including the miss at 1.7x) and calibration study; one live run of each reproduces
  its committed row.
- Outputs: memo is self-contained and accessible, lists every comp and rule, shows no cents; JSON holds
  no floats; committed outputs match a fresh run; the demo page's embedded data matches the Python figures.

## What is not done

- Not run on any real time-and-billing data. No compatibility with any named product is claimed. The
  two mappings are examples for two invented export shapes.
- Comparable selection filters; it does not adjust. A comp with five parties is either in or out. There
  is no model of how cost scales with an attribute, by design.
- The planning bands are conservative and wide. They over-cover overall (7.6% over P90 against 10%) and
  can sit well beyond the comps: for the shifted type the planning P90 is $409,400 where the comp P90
  is $144,800. They are a finite-sample rule plus a ratio learned from a few dozen matters at most, not
  a guarantee. Per-type results on other seeds still show the occasional type understating.
- The adjustment ratios come from type-only back-test predictions, while a proposal may use narrower
  comps. Phase-level figures and the phased-fee scenario have no planning bands; they are in sample.
- For a shifted type, the recent-only version's adjustment history includes matters that were modeled
  before the change was detected, so its factor is larger than it will be later. Combined with
  taking the higher of two versions, figures for a flagged type are deliberately on the high side.
- Matters known on a given day lean cheap at the recent end: of those opened recently, only the quick
  ones have closed. The change check orders by opening date and can read that as a fall in cost.
- The back-test uses matter type only. It does not replay each proposal's attribute rules.
- Fees only. Expenses and disbursements, taxes, discounts, alternative staffing and multiple currencies
  are out of scope.
- Normalization is by level against one current rate card. Timekeeper-specific rates, client rate
  agreements and a changing mix of who does the work are not modeled.
- Collected amounts are per matter, not per phase.
- The target-probability fee is computed for a single fixed fee only.
- The date-window fallback is crude and cannot find a hearing without a hearing date.
- The change check misses real changes and raises false alarms; the measured rates are in the section
  above. It did not reach the 18 of 20 aim at 1.7x (13 of 20 on the evaluation seeds), its unplanted
  flag rate there was 6.8% against a 5% aim, and it catches a 12% a year gradual drift only half the
  time. A false alarm that says costs rose raises the planning figures for no reason; one that says
  costs fell changes nothing. A real fall in cost is not acted on until a person sets `recent_only`.
  Do not read "not flagged" as "stable".
- When a type is flagged but fewer than the minimum number of comps opened since the estimated date,
  no recent-only version is built and the figures come from the whole history, with a warning. If
  costs really rose, those figures are too low.
- The estimated change date is rough, and early on (fewer than 8 closed matters since the change) the
  split cannot be placed at the true date at all.
- The one-sided overrun check treats back-tested matters as independent draws. They are not quite:
  neighbouring matters share most of their comps. Treat a flag as a prompt to look, not a test result.
- The out-of-sample figures shown beside a fee are for the planning bands either side of it (of P25, P50,
  P75, P90), not for the fee itself, and come from a type-only back-test.
- The loader reads delimited text files only and expects reversals to be netted before loading.
- The fee explorer on `index.html` is JavaScript and is checked only for data parity with Python.
- On screen the memo is one page plus a comp appendix; printed, the body runs to about two pages.

## Layout

```
feemodel/
  schema.py     canonical tables and fields
  loader.py     mapping-driven loader
  profile.py    export profiler
  cost.py       phases, per-matter cost, as-of cost book
  comps.py      comparable-matter selection and refusal
  stats.py      quantiles, bootstrap, warnings
  pricing.py    scenarios, target fee, hours-reduction table, scope assumptions
  bands.py      planning bands: finite-sample quantile and upward adjustment
  drift.py      change check: scan for a change point by opening date
  backtest.py   walk-forward back-test, overrun check, modelability table
  sensitivity.py  the drift study and the calibration study on other seeds
  engine.py     one proposal end to end; JSON conversion
  memo.py       HTML memo, refusal memo, modelability page
  site.py       index.html
  synth.py      seeded synthetic generator
  cli.py        python -m feemodel profile|comps|price|backtest|drift-sensitivity|calibration-study|generate
data/           synthetic exports, mappings, rate card, cost rates, task codes, proposals
output/         sample outputs from run_demo.py and the two studies; tuning/ holds the threshold-seed runs
tests/          pytest suite
```
