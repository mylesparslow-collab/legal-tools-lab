# Parser check against hand-written answer keys

The keys were written by hand from the RFP text. The parser and the keys were written
by the same person for the same four documents, so these figures are in-sample.
They show that the parser does what it was built to do on these files. They do not
predict accuracy on other RFPs. Items the parser marked "check" are counted like any
other item.

## All four RFPs together

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 23 | 0 | 0 | 1.000 | 1.000 |
| addendum_changes | 5 | 0 | 0 | 1.000 | 1.000 |
| requirements | 38 | 0 | 0 | 1.000 | 1.000 |
| forms | 18 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 20 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 13 | 0 | 0 | 1.000 | 1.000 |
| insurance | 12 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 37 | 0 | 0 | 1.000 | 1.000 |
| parties | 33 | 0 | 0 | 1.000 | 1.000 |
| overall | 199 | 0 | 0 | 1.000 | 1.000 |

Question type correct on 38 of 38 requirements.

## city_attorney_marlow_ridge.txt

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 6 | 0 | 0 | 1.000 | 1.000 |
| addendum_changes | 0 | 0 | 0 | 1.000 | 1.000 |
| requirements | 11 | 0 | 0 | 1.000 | 1.000 |
| forms | 4 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 4 | 0 | 0 | 1.000 | 1.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 11 | 0 | 0 | 1.000 | 1.000 |
| parties | 8 | 0 | 0 | 1.000 | 1.000 |
| overall | 53 | 0 | 0 | 1.000 | 1.000 |

No differences from the key.

## general_counsel_redwood_flats.txt

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 6 | 0 | 0 | 1.000 | 1.000 |
| addendum_changes | 2 | 0 | 0 | 1.000 | 1.000 |
| requirements | 10 | 0 | 0 | 1.000 | 1.000 |
| forms | 4 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 3 | 0 | 0 | 1.000 | 1.000 |
| insurance | 3 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 10 | 0 | 0 | 1.000 | 1.000 |
| parties | 7 | 0 | 0 | 1.000 | 1.000 |
| overall | 50 | 0 | 0 | 1.000 | 1.000 |

No differences from the key.

## labor_negotiator_quillfeather_usd.txt

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 5 | 0 | 0 | 1.000 | 1.000 |
| addendum_changes | 0 | 0 | 0 | 1.000 | 1.000 |
| requirements | 8 | 0 | 0 | 1.000 | 1.000 |
| forms | 3 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 3 | 0 | 0 | 1.000 | 1.000 |
| insurance | 1 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 6 | 0 | 0 | 1.000 | 1.000 |
| parties | 10 | 0 | 0 | 1.000 | 1.000 |
| overall | 41 | 0 | 0 | 1.000 | 1.000 |

No differences from the key.

## special_counsel_tannery_creek_transit.txt

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 6 | 0 | 0 | 1.000 | 1.000 |
| addendum_changes | 3 | 0 | 0 | 1.000 | 1.000 |
| requirements | 9 | 0 | 0 | 1.000 | 1.000 |
| forms | 7 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 3 | 0 | 0 | 1.000 | 1.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 10 | 0 | 0 | 1.000 | 1.000 |
| parties | 8 | 0 | 0 | 1.000 | 1.000 |
| overall | 55 | 0 | 0 | 1.000 | 1.000 |

No differences from the key.
## Earlier hold-out: bond_counsel_gullwing_harbor.txt

A fifth RFP written by the parser's author in a layout the parser was not written for.

- First run, before any change to the parser (round 1): precision 0.667, recall 0.136 (6 correct, 3 extra, 38 missed).
  The parser did not recognise the 'Article 1.  Title' headings (mixed case), so it found no sections. It reported 7 items for a person to check, including 'no submission deadline found' and 'no numbered proposal requirements found'.
- After six general fixes prompted by that run (round 1): precision 0.825, recall 0.750 (33 correct, 7 extra, 11 missed). Recorded then; no longer held out.
- Today, after the round 2 rewrite: precision 1.000, recall 1.000 (44 correct, 0 extra, 0 missed). This document has been used for fixes, so this is an in-sample figure.


## Independent held-out batches

Six RFPs with keys written by an independent author who had not read the parser (heldout/README.md).
These are recorded results; full detail is in data/heldout_results/. The batch B row is the figure
to rely on.

| Run | Requirements P / R | All categories P / R | Submission deadline | Page limit | Addendum checks |
|---|---|---|---|---|---|
| Batch A, first run (parser as it stood after round 1) | 1.000 / 0.000 | 0.489 / 0.132 | 0 of 3 | 0 of 3 | 2 of 11 |
| Batch A, after general fixes made from its misses (not held out any more) | 1.000 / 1.000 | 0.994 / 1.000 | 3 of 3 | 3 of 3 | 14 of 14 |
| Batch B, run once at the end, sealed until then | 0.769 / 0.571 | 0.798 / 0.512 | 1 of 3 | 2 of 3 | 5 of 11 |

The batch B figure is the guide to what happens on an RFP layout nobody has tuned for.
