# Protest tabulation and objection gate

Marlow Creek Water District (fictional). Fictional data. Portfolio demo, not legal advice.

## Protest tally (art. XIII D § 6)

**No majority protest, even if every item in review were counted.**

| | |
|---|---|
| Identified parcels | 400 |
| Protests needed for a majority | 201 |
| Parcels with a counted protest | 147 |
| Items in review that could add a parcel | 13 |
| Most protests possible | 160 |
| Submissions received | 222 |

Dispositions, one line per submission per parcel: COUNTED 147, DUPLICATE 31, INVALID 18, NOT_COUNTED 4, REVIEW 14, WITHDRAWAL_APPLIED 5, WITHDRAWN 5.

## Calendar and notice checks

| Check | Result | Detail | Source |
|---|---|---|---|
| hearing_gap | pass | Hearing is 64 days after the notice was mailed; at least 45 required. | Cal. Const. art. XIII D, § 6(a)(2) |
| ab2257_scope | pass | Service type 'water' is within the § 53759.1 definition of fee or assessment. | Gov. Code § 53759.1(a)(2) |
| fee_available | pass | Proposed fee was public 49 days before the objection deadline; at least 45 required. | Gov. Code § 53759.1(c)(1) |
| objection_window | pass | Objection deadline is 49 days after notice; at least 45 required. | Gov. Code § 53759.1(c)(4) |
| deadline_before_hearing | pass | Objection deadline 2026-09-21 is on or before the hearing date 2026-10-06. | Gov. Code § 53759.1(c)(7) |
| written_basis_posted | pass | Written basis posted on the website and linked in the mailed notice. | Gov. Code § 53759.1(c)(2) |
| notice_statement | pass | Notice carries the prominent failure-to-object statement and the requirements for objecting. | Gov. Code § 53759.1(c)(6)(A)-(B) |
| mail_on_request | pass | 2 request(s) for a mailed copy of the written basis; 0 not yet mailed. | Gov. Code § 53759.1(c)(3) |
| sol_statement | pass | Notice states the 120-day statute of limitations. | Gov. Code § 53759(d) |

## Objection gate (Gov. Code § 53759.1(c)(5))

**Gate: BLOCKED.** 9 timely objections, 7 answered, 2 open, 2 untimely, 2 protest letters awaiting triage.

| Objection | Received | Tags | Exhibit | Status | Problems |
|---|---|---|---|---|---|
| OBJ-001 | 2026-09-02T14:30:00 | tiered rates; proportionality | Res. 2026-14, Exh. C-1 | ANSWERED |  |
| OBJ-002 | 2026-09-04T14:30:00 | hydrant costs (§ 53750.5) | Res. 2026-14, Exh. C-2 | ANSWERED |  |
| OBJ-003 | 2026-09-06T14:30:00 | peaking factors (§ 53750.6) | Res. 2026-14, Exh. C-3 | ANSWERED |  |
| OBJ-004 | 2026-09-08T14:30:00 | reserve funding | Res. 2026-14, Exh. C-4 | ANSWERED |  |
| OBJ-005 | 2026-09-10T14:30:00 | tiered rates; conservation pricing | Res. 2026-14, Exh. C-5 | ANSWERED |  |
| OBJ-006 | 2026-09-12T14:30:00 | notice content | Res. 2026-14, Exh. C-6 | ANSWERED | objection states no grounds; respond anyway and note it (does not block) |
| OBJ-007 | 2026-09-14T14:30:00 | capital plan costs |  | OPEN | no written response |
| OBJ-008 | 2026-09-16T14:30:00 | customer class allocation | Res. 2026-14, Exh. C-8 | ANSWERED |  |
| OBJ-009 | 2026-09-18T14:30:00 | drought surcharge | Res. 2026-14, Exh. C-9 | OPEN | response not dated before the close of the hearing; objection and response not presented to the governing body before or during the hearing |
| OBJ-010 | 2026-09-25T11:00:00 | tiered rates |  | UNTIMELY | received after the objection deadline; no response is required by § 53759.1(c)(5) |
| OBJ-011 | 2026-09-26T11:00:00 | meter charge |  | UNTIMELY | received after the objection deadline; no response is required by § 53759.1(c)(5) |

Protest letters with objection-like wording that nobody has triaged yet:

- S-0007 (received 2026-09-10T09:00:00): tier, subsid
- S-0009 (received 2026-08-30T16:15:00): article xiii d, methodology

## Statute of limitations (Gov. Code § 53759)

Runs from 2027-01-01. Raw 120th day: 2027-05-01 (a weekend). Weekend and holiday roll-forward rules were not checked; an attorney must confirm.

## Record of proceedings index (Gov. Code § 53759.2(b)(1))

| | Category | Documents |
|---|---|---|
| A | Cost-of-service or rate study, engineer's report, staff reports, related documents | 2026 Water Cost-of-Service Study; Staff report, Oct. 6, 2026 |
| B | Transcripts or minutes of proceedings before the decisionmaking body and advisory bodies | Minutes, Finance Committee, July 14, 2026 |
| C | All notices issued | Prop 218 notice mailed Aug. 3, 2026 |
| D | Timely written objections and agency responses | Objections OBJ-001 to OBJ-011 and responses |
| E | Written evidence or correspondence submitted to or sent from the agency before the hearing was completed | **none listed** |
| F | Documentation of the final decision (ordinance, resolution, minutes) | Draft Resolution 2026-14 |
| G | Protests, ballots, and tabulation records | Protest audit log and tabulation |
| H | Written evidence supporting the fee in the agency's files before the hearing was completed | Capital improvement plan 2027-2031 |

Rules read against primary text on 2026-11-25. See rules.json for each source and status.
