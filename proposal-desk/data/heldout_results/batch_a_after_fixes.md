# Held-out batch A, after general fixes made from its misses

The RFPs and keys were written by an independent author who had not read the parser.
Scoring rules are in desk/heldout_score.py. Items the parser marked "check" count like
any other item. Addendum handling is its own line and is not part of the overall figure.

## All RFPs in the batch together

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 19 | 0 | 0 | 1.000 | 1.000 |
| requirements | 36 | 0 | 0 | 1.000 | 1.000 |
| forms | 15 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 15 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 12 | 0 | 0 | 1.000 | 1.000 |
| insurance | 12 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 32 | 1 | 0 | 0.970 | 1.000 |
| parties | 33 | 0 | 0 | 1.000 | 1.000 |
| overall | 174 | 1 | 0 | 0.994 | 1.000 |

- Submission deadline (date and time in force) right on 3 of 3 RFPs.
- Page limit in force right on 3 of 3 RFPs.
- Addendum handling: 14 of 14 checks passed.
- Question type right on 36 of the 36 requirements found (36 in the keys).

## coverage_counsel_kestrel_ridge_jpia

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 6 | 0 | 0 | 1.000 | 1.000 |
| requirements | 9 | 0 | 0 | 1.000 | 1.000 |
| forms | 5 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 4 | 0 | 0 | 1.000 | 1.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 12 | 0 | 0 | 1.000 | 1.000 |
| parties | 8 | 0 | 0 | 1.000 | 1.000 |
| overall | 53 | 0 | 0 | 1.000 | 1.000 |

- Requirements: numbered 9 of 9, unnumbered 0 of 0.
- Submission deadline: key 2027-02-10 14:00, parsed 2027-02-10 14:00.
- Page limit: key 30, parsed [30].
- Addendum handling: 14 of 14.
  - ok: questions_due: date as issued (2027-01-07) still shown
  - ok: questions_due in force 2027-01-11
  - ok: answers_issued: date as issued (2027-01-12) still shown
  - ok: answers_issued in force 2027-01-15
  - ok: submission_due: date as issued (2027-01-27) still shown
  - ok: submission_due in force 2027-02-10 14:00
  - ok: page limit in force 30
  - ok: form added: Addenda Acknowledgment Form
  - ok: requirement 3.7 deleted
  - ok: criterion removed: Training program
  - ok: weight of Coverage experience now 45
  - ok: interview: date as issued (2027-02-18) still shown
  - ok: interview in force 2027-02-25
  - ok: insurance Cyber liability now $2,000,000

No differences from the key.

## general_counsel_ashdown_valley_ccd

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 7 | 0 | 0 | 1.000 | 1.000 |
| requirements | 13 | 0 | 0 | 1.000 | 1.000 |
| forms | 6 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 4 | 0 | 0 | 1.000 | 1.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 12 | 0 | 0 | 1.000 | 1.000 |
| parties | 12 | 0 | 0 | 1.000 | 1.000 |
| overall | 63 | 0 | 0 | 1.000 | 1.000 |

- Requirements: numbered 11 of 11, unnumbered 2 of 2.
- Submission deadline: key 2027-01-21 15:00, parsed 2027-01-21 15:00.
- Page limit: key 20, parsed [20].
- Addendum handling: 0 of 0.
- Deadline kind outside the existing keys (start_of_services 2027-04-01): date found; not counted either way.

No differences from the key.

## litigation_counsel_lantern_bay_port

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 6 | 0 | 0 | 1.000 | 1.000 |
| requirements | 14 | 0 | 0 | 1.000 | 1.000 |
| forms | 4 | 0 | 0 | 1.000 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 4 | 0 | 0 | 1.000 | 1.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 8 | 1 | 0 | 0.889 | 1.000 |
| parties | 13 | 0 | 0 | 1.000 | 1.000 |
| overall | 58 | 1 | 0 | 0.983 | 1.000 |

- Requirements: numbered 10 of 10, unnumbered 4 of 4.
- Submission deadline: key 2027-01-15 16:30, parsed 2027-01-15 16:30.
- Page limit: key 18, parsed [18].
- Addendum handling: 0 of 0.

- extra mechanics: ('kind', 'copies')
