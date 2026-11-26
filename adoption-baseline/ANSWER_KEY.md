# Answer key

Planted truths in the synthetic data. Written by `generate_synthetic.py` (seed 20261207) from its own
clean data, before any mess is injected into the exports. The tests in
`tests/test_planted_truths.py` check that the analyser recovers each one from the messy files.
The machine-readable copy is `sample_data/answer_key.json`.

All people, practices, offices and numbers are invented.

## Structure planted on purpose

1. A few heavy users. Eight associates log roughly ten times the typical volume in Assistant A:
   SYN-0016, SYN-0143, SYN-0164, SYN-0208, SYN-0210, SYN-0284, SYN-0287, SYN-0320. They are the top eight people by interactions.
2. Many licensed non-users. Assistant A: 195 licensed, 99 activated, 97 unused in the last 30 days.
   Assistant B: 286 licensed, 76 activated, 211 unused in the last 30 days.
3. One practice high on survey and low in logs. In Real estate most non-users say they used an approved
   tool in the last 7 days. It has the largest survey-minus-log gap of any practice.
4. A new office with low use. Everyone in Lakeshore starts on 2026-10-05, so they are not in the
   denominator before then, and adoption there is low. It is the lowest office that is not suppressed.
5. A holiday week dip. 2026-W44 has the lowest weekly active rate of the period, even after people on
   leave for the whole week are removed from the denominator.
6. Rising adoption. About 45% of eventual users start part-way through the period, so the last four
   weeks are higher than the first six. The demo comparison should call this an increase.
7. Survey non-response bias. People with logged use respond at about 72%, others at about 45%.
   The firm-wide survey figure is therefore higher than the log figure even without over-claiming.
8. Small groups. Competition has 4 lawyers and Midvale has 4 lawyers. Both must be suppressed, and
   one further group in each table must be suppressed so the total does not reveal them.

## Weekly active lawyers, any approved tool (true values)

| ISO week | Active of eligible |
|---|---|
| 2026-W37 | 54 of 180 (30%) |
| 2026-W38 | 61 of 183 (33%) |
| 2026-W39 | 62 of 178 (35%) |
| 2026-W40 | 56 of 177 (32%) |
| 2026-W41 | 72 of 194 (37%) |
| 2026-W42 | 65 of 194 (34%) |
| 2026-W43 | 73 of 195 (37%) |
| 2026-W44 | 30 of 170 (18%) |
| 2026-W45 | 70 of 197 (36%) |
| 2026-W46 | 76 of 196 (39%) |
| 2026-W47 | 85 of 193 (44%) |
| 2026-W48 | 89 of 195 (46%) |
| 2026-W49 | 87 of 193 (45%) |

## Mess injected into the exports (exact counts)

| Item | Assistant A export | Assistant B export |
|---|---|---|
| Rows in file | 9434 | 1781 |
| Rows that are real usage (should be kept) | 9347 | 1716 |
| Exact duplicate rows | 40 | 10 |
| Conflicting duplicate rows | 0 | 5 |
| Rows for users not on the roster | 25 | 12 |
| Rows with an unreadable date | 6 | 5 |
| Rows with no user | 4 | 0 |
| Rows with an unreadable count | 0 | 3 |
| Rows with zero interactions | 0 | 30 |
| Rows outside the period | 12 | 0 |
| Kept rows whose email or name needed case or spacing repair | 1108 | 330 |
| Kept rows with a feature not in the mapping | 187 | 0 |
| Kept rows for a user without a licence | 39 | 0 |
| Kept rows in the second date format | 0 | 180 |

Conflicting duplicates are placed directly after the true row, so the documented rule (keep the
first row for a key) keeps the true value. A real export gives no such guarantee.

## Other planted roster facts

- 3 people changed practice on 2026-10-19: SYN-0061, SYN-0310, SYN-0314.
- 2 lawyers without an Assistant A licence have Assistant A usage: SYN-0203, SYN-0249.
- 5 person-weeks have usage logged during a week of full leave. They are excluded from both the
  numerator and the denominator for that week.
- 173 of 320 people on the roster have no usage at all. They count as zero, not as missing.
- The most common survey blocker is `unsure_allowed`; 160 responses were generated.
