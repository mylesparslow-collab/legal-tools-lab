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
3. Shows a distribution, not a point: P25, P50, P75, P90 overall and per phase, with seeded bootstrap
   intervals, n on every figure, and plain warnings for small or skewed samples. No regression models.
4. Tests fee structures against the comps: fixed, capped, phased fixed, and fixed with a collar. For each:
   how many comps would have come in at or under the fee, mean margin against cost rates you supply,
   the margin in the P90 case, and the fee needed for a target share of comps with no loss.
5. Writes scope assumptions and exclusions from the comp evidence, for example which phase drove the
   expensive comps, each with the counts and amounts behind it.
6. Applies optional per-phase hours reductions that the user types in, with a before/after table,
   labelled as the user's assumptions. Default is zero. The tool predicts nothing about AI.
7. Back-tests itself: walks forward through history, models each past matter only from matters that
   closed before it opened, and reports how often the actual cost fell inside the predicted bands and
   how often it ran over the P75 and P90 figures.
8. Puts that back-test result on every memo, next to the quantiles, and beside each in-sample share
   of comps under a proposed fee shows what the walk-forward test found at the nearest band.

## Run it

```
python run_demo.py
```

That regenerates the synthetic data (seeded), profiles both export shapes, runs the back-test, writes
five pricing memos to `output/` and rebuilds `index.html`. Python 3 standard library only. No network.

Open `index.html` for the demo page, or `output/memo_P-001.html` for a memo.

```
python -m feemodel profile data/export_b --mapping data/mappings/export_b.json
python -m feemodel backtest --out output
python -m feemodel comps --proposal data/proposals/P-001.json
python -m feemodel price --proposal data/proposals/P-001.json
python -m feemodel drift-sensitivity --out output    # about a minute; not part of run_demo.py
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

| Matter type | Tested | Inside P25 to P75 (nominal 50%) | At or under P75 (75%) | At or under P90 (90%) |
|---|---|---|---|---|
| administrative_licensing_appeal | 27 | 13 (48%) | 22 (81%) | 26 (96%) |
| commercial_lease_review | 38 | 11 (29%) | 27 (71%) | 30 (79%) |
| contract_dispute_arbitration | 19 | 7 (37%) | 17 (89%) | 19 (100%) |
| election_law_advisory | 0 | n/a | n/a | n/a |
| employment_single_plaintiff_defense | 41 | 16 (39%) | 26 (63%) | 31 (76%) |
| facility_change_of_ownership | 37 | 16 (43%) | 27 (73%) | 29 (78%) |
| internal_investigation | 31 | 9 (29%) | 13 (42%) | 22 (71%) |
| ordinance_drafting | 41 | 16 (39%) | 27 (66%) | 34 (83%) |
| paga_response | 35 | 18 (51%) | 20 (57%) | 28 (80%) |
| public_records_litigation | 53 | 28 (53%) | 38 (72%) | 44 (83%) |
| public_works_bid_protest | 41 | 16 (39%) | 32 (78%) | 37 (90%) |
| regulatory_compliance_audit | 22 | 12 (55%) | 19 (86%) | 21 (95%) |
| All types | 385 | 162 (42%) | 268 (70%) | 321 (83%) |

The verdict on the upper bands is one-sided, because more overruns than a band implies is the
direction that loses money on a fixed or capped fee. Each type's result states the overrun counts in
words, and a band that was exceeded materially more often than it implies is never reported as fine.

| Matter type | Cost more than P75 (band implies) | Cost more than P90 (band implies) | Verdict on the upper bands |
|---|---|---|---|
| administrative_licensing_appeal | 5 of 27 (about 7) | 1 of 27 (about 3) | Within what chance would explain |
| commercial_lease_review | 11 of 38 (about 10) | 8 of 38 (about 4) | Understates overruns at P90 |
| contract_dispute_arbitration | 2 of 19 (about 5) | 0 of 19 (about 2) | Within what chance would explain |
| election_law_advisory | n/a | n/a | Not back-tested |
| employment_single_plaintiff_defense | 15 of 41 (about 10) | 10 of 41 (about 4) | Understates overruns at P90 |
| facility_change_of_ownership | 10 of 37 (about 9) | 8 of 37 (about 4) | Understates overruns at P90 |
| internal_investigation | 18 of 31 (about 8) | 9 of 31 (about 3) | Costs shifted over time; bands from older matters missed |
| ordinance_drafting | 14 of 41 (about 10) | 7 of 41 (about 4) | Within what chance would explain |
| paga_response | 15 of 35 (about 9) | 7 of 35 (about 4) | Understates overruns at P75 |
| public_records_litigation | 15 of 53 (about 13) | 9 of 53 (about 5) | Within what chance would explain |
| public_works_bid_protest | 9 of 41 (about 10) | 4 of 41 (about 4) | Within what chance would explain |
| regulatory_compliance_audit | 3 of 22 (about 6) | 1 of 22 (about 2) | Within what chance would explain |
| All types | 117 of 385 (about 96) | 64 of 385 (about 39) | Understates overruns at P75 and P90 |

What to read from this. Across all types the bands understate overruns: 64 of 385 back-tested matters
cost more than their predicted P90, where the band implies about 39. Part of that is built in:
quantiles taken from a few dozen matters or fewer are narrower than the spread of the next matter,
and the back-test starts predicting from as few as 8. Four types with nothing planted are flagged for
it. "Within what chance would explain" is not a pass: at n=41, 7 overruns against an implied 4 is not
enough to call, and the counts are printed so the reader can judge. `internal_investigation` misses
badly because its costs were planted to double partway through; the tool flags it.
`election_law_advisory` has 5 closed matters and is refused.

The rule for "understates": an exact one-sided binomial check. A band is said to understate overruns
when seeing that many matters above it, or more, would happen less than 1 time in 20 if the band were
right. It was chosen over a fixed tolerance because a fixed 15 points means very different things at
different bands and sample sizes: at P90 it lets up to 25% of matters overrun a band that implies 10%
and still pass. The binomial check scales with n and with the band. The 1-in-20 line is a setting of
this tool. With about a dozen types and two bands each, an occasional flag by chance is expected.
Fewer overruns than implied is only a mild note, and the middle band (P25 to P75) keeps a plain
15-point note. At least 10 back-tested matters are needed before any judgement is made.

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
  on the same comps the bands came from, so it flatters the fee. The memo labels it "in sample" and
  puts the walk-forward result for the nearest band beside it, labelled "out of sample". The
  walk-forward test matches on matter type only, so it is evidence about the type, not about the
  proposal's narrower comp set. If the type was not back-tested, or has fewer than 10 back-tested
  matters, the memo says that instead of a figure.
- A type is flagged as shifted in the back-test only when the later half of closes differs from the
  earlier half by 1.3x or more, a seeded shuffle test on ranks says that is unlikely to be noise, and
  coverage at P75 is more than 15 points off nominal with at least 10 tested matters. These thresholds
  are settings of this tool. They are not industry figures.
- The bootstrap interval says how much a quantile would move with a different draw of comps. It is not
  a forecast range for the next matter.

## What is tested

126 tests, all passing (`python -m pytest -q`):

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
  type and the flag on the drifting type; the generator reproduces the committed files byte for byte.
- Overruns and memo: the exact binomial check by hand; more overruns than implied is never reported as
  fine; the same overrun wording reaches every output; the memo carries its type's back-test and labels
  in-sample and out-of-sample figures; not-back-tested and under-10 cases say so.
- Drift sensitivity: the measured flag rate at the shipped 2.0x step is pinned (14 of 20 seeds).
- Outputs: memo is self-contained and accessible, lists every comp and rule, shows no cents; JSON holds
  no floats; committed outputs match a fresh run; the demo page's embedded data matches the Python figures.

## What is not done

- Not run on any real time-and-billing data. No compatibility with any named product is claimed. The
  two mappings are examples for two invented export shapes.
- Comparable selection filters; it does not adjust. A comp with five parties is either in or out. There
  is no model of how cost scales with an attribute, by design.
- Bands are plain empirical quantiles and under-cover on small samples, as the back-test shows. No
  small-sample correction is applied.
- The back-test uses matter type only. It does not replay each proposal's attribute rules.
- Fees only. Expenses and disbursements, taxes, discounts, alternative staffing and multiple currencies
  are out of scope.
- Normalization is by level against one current rate card. Timekeeper-specific rates, client rate
  agreements and a changing mix of who does the work are not modeled.
- Collected amounts are per matter, not per phase.
- The target-probability fee is computed for a single fixed fee only.
- The date-window fallback is crude and cannot find a hearing without a hearing date.
- The drift flag is a heuristic with fixed thresholds, and it is not sensitive. It can miss slow change
  and can fire by chance. Measured on regenerated synthetic firms (seeds 1 to 20 at each planted step,
  everything else as shipped, thresholds untouched; `python -m feemodel drift-sensitivity`,
  results in `output/drift_sensitivity.txt`):

  | Planted step in the drifting type | Flagged | Median observed later/earlier ratio |
  |---|---|---|
  | none (1.0x) | 0 of 20 | 1.06x |
  | 1.3x | 1 of 20 | 1.17x |
  | 1.5x | 6 of 20 | 1.39x |
  | 1.7x | 11 of 20 | 1.61x |
  | 2.0x | 14 of 20 | 1.84x |

  So a 1.5x shift in a type with about 40 clean closed matters is missed most of the time, a 1.7x shift
  about half the time, and even a doubling is missed in 6 draws of 20. The shipped data plants 2.0x. An
  earlier 1.7x plant was not flagged on the shipped seed, so the plant was enlarged; the detector was
  not tuned to it. On the shipped seed the 2.0x step is flagged with little room to spare (8 of 1,000
  shuffles as lopsided against a limit of 20). Types with no planted shift were flagged in 2 of 200
  type-runs at the 2.0x setting and 1 of 200 with no shift planted anywhere. The same seeds are reused
  across steps, so those are not independent samples. Do not read "not flagged" as "stable". The
  per-type overrun counts are the more dependable signal.
- The one-sided overrun check treats back-tested matters as independent draws. They are not quite:
  neighbouring matters share most of their comps. Treat a flag as a prompt to look, not a test result.
- The out-of-sample figure shown beside a fee is for the nearest of four bands (P25, P50, P75, P90), not
  for the fee itself, and comes from a type-only back-test.
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
  backtest.py   walk-forward back-test, overrun check, drift check, modelability table
  sensitivity.py  how big a planted shift the drift flag catches
  engine.py     one proposal end to end; JSON conversion
  memo.py       HTML memo, refusal memo, modelability page
  site.py       index.html
  synth.py      seeded synthetic generator
  cli.py        python -m feemodel profile|comps|price|backtest|generate
data/           synthetic exports, mappings, rate card, cost rates, task codes, proposals
output/         sample outputs from run_demo.py
tests/          pytest suite
```
