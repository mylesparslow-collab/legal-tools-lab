# Held-out batch A, first run (before any change to the parser)

The RFPs and keys were written by an independent author who had not read the parser.
Scoring rules are in desk/heldout_score.py. Items the parser marked "check" count like
any other item. Addendum handling is its own line and is not part of the overall figure.

## All RFPs in the batch together

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 0 | 2 | 19 | 0.000 | 0.000 |
| requirements | 0 | 0 | 36 | 1.000 | 0.000 |
| forms | 0 | 2 | 15 | 0.000 | 0.000 |
| evaluation | 0 | 0 | 15 | 1.000 | 0.000 |
| min_quals | 0 | 0 | 12 | 1.000 | 0.000 |
| insurance | 0 | 0 | 12 | 1.000 | 0.000 |
| mechanics | 0 | 0 | 32 | 1.000 | 0.000 |
| parties | 23 | 20 | 10 | 0.535 | 0.697 |
| overall | 23 | 24 | 151 | 0.489 | 0.132 |

- Submission deadline (date and time in force) right on 0 of 3 RFPs.
- Page limit in force right on 0 of 3 RFPs.
- Addendum handling: 2 of 11 checks passed.
- Question type right on 0 of the 0 requirements found (36 in the keys).

## coverage_counsel_kestrel_ridge_jpia

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 0 | 2 | 6 | 0.000 | 0.000 |
| requirements | 0 | 0 | 9 | 1.000 | 0.000 |
| forms | 0 | 2 | 5 | 0.000 | 0.000 |
| evaluation | 0 | 0 | 5 | 1.000 | 0.000 |
| min_quals | 0 | 0 | 4 | 1.000 | 0.000 |
| insurance | 0 | 0 | 4 | 1.000 | 0.000 |
| mechanics | 0 | 0 | 12 | 1.000 | 0.000 |
| parties | 4 | 5 | 4 | 0.444 | 0.500 |
| overall | 4 | 9 | 49 | 0.308 | 0.075 |

- Requirements: numbered 0 of 9, unnumbered 0 of 0.
- Submission deadline: key 2027-02-10 14:00, parsed 2027-02-03 16:00.
- Page limit: key 30, parsed none.
- Addendum handling: 2 of 11.
  - FAILED: questions_due in force 2027-01-11
  - FAILED: answers_issued: date as issued (2027-01-12) still shown
  - ok: answers_issued in force 2027-01-15
  - FAILED: submission_due in force 2027-02-10 14:00
  - FAILED: page limit in force 30
  - FAILED: form added: Addenda Acknowledgment Form
  - ok: requirement 3.7 deleted
  - FAILED: criterion removed: Training program
  - FAILED: weight of Coverage experience now 45
  - FAILED: interview in force 2027-02-25
  - FAILED: insurance Cyber liability now $2,000,000

- extra deadlines: answers_issued 2027-01-15 12:00
- extra deadlines: submission_due 2027-02-03 16:00
- missed deadlines: issued 2026-12-14 None
- missed deadlines: questions_due 2027-01-11 12:00
- missed deadlines: answers_issued 2027-01-15 None
- missed deadlines: submission_due 2027-02-10 14:00
- missed deadlines: interview 2027-02-25 None
- missed deadlines: award 2027-03-11 None
- missed requirements: 3.1 | Letter of Interest. A signed letter stating the firm's interest, the n
- missed requirements: 3.2 | The Firm. The firm's size, structure and offices, the number of attorn
- missed requirements: 3.3 | Personnel. The names and qualifications of the lead coverage counsel a
- missed requirements: 3.4 | Coverage Experience. A description of the firm's work in the last five
- missed requirements: 3.5 | Method of Service. How the firm would deliver coverage opinions within
- missed requirements: 3.6 | Client References. Three references from risk pools or insurers, with 
- missed requirements: 3.8 | Conflicts. A list of every member of the Authority that the firm has r
- missed requirements: 3.9 | Pricing. Hourly rates by attorney and paralegal; a proposed flat fee p
- missed requirements: 3.10 | Additional Information. Anything else the firm wishes the Authority to
- extra forms: Appendix A (named in section PART THREE)
- extra forms: Appendix B (named in section PART FIVE)
- missed forms: Proposal Cover Sheet
- missed forms: Certification of Non-Collusion
- missed forms: Conflict of Interest Questionnaire
- missed forms: Certificate of Insurance (or broker's letter)
- missed forms: Addenda Acknowledgment Form
- missed evaluation: Coverage experience 45
- missed evaluation: Personnel 20
- missed evaluation: Method of service 15
- missed evaluation: Pricing 15
- missed evaluation: Client references 5
- missed min_quals: Lead coverage counsel has been licensed to practice law for  | years_admitted 12
- missed min_quals: Lead coverage counsel has given coverage advice | not_checkable None
- missed min_quals: The firm has three (3) or more attorneys | attorney_count 3
- missed min_quals: Neither the firm nor any proposed attorney is defending | not_checkable None
- missed insurance: Professional liability $2,000,000
- missed insurance: Commercial general liability $1,000,000
- missed insurance: Workers' compensation None
- missed insurance: Cyber liability $2,000,000
- missed mechanics: ('kind', 'copies')
- missed mechanics: ('kind', 'format')
- missed mechanics: ('kind', 'packaging')
- missed mechanics: ('kind', 'delivery')
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_limit')
- missed mechanics: ('kind', 'page_exclusions')
- missed mechanics: ('kind', 'font')
- missed mechanics: ('kind', 'margins')
- missed mechanics: ('page_limit', 30)
- missed mechanics: ('font', 11)
- missed mechanics: ('margins', 1.0)
- extra parties: Its Claims (board)
- extra parties: Tobias Ferreira (board)
- extra parties: Treasurer Lucius Pemberton (board)
- extra parties: Stonebridge Claims (board)
- extra parties: Marlin Reach Reinsurance Company (adverse)
- missed parties: Tobias Ferreira (staff)
- missed parties: Lucius Pemberton (board)
- missed parties: Stonebridge Claims Services, Inc. (other_organisation)
- missed parties: Marlin Reach Reinsurance Company (other_organisation)

## general_counsel_ashdown_valley_ccd

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 0 | 0 | 7 | 1.000 | 0.000 |
| requirements | 0 | 0 | 13 | 1.000 | 0.000 |
| forms | 0 | 0 | 6 | 1.000 | 0.000 |
| evaluation | 0 | 0 | 5 | 1.000 | 0.000 |
| min_quals | 0 | 0 | 4 | 1.000 | 0.000 |
| insurance | 0 | 0 | 4 | 1.000 | 0.000 |
| mechanics | 0 | 0 | 12 | 1.000 | 0.000 |
| parties | 10 | 10 | 2 | 0.500 | 0.833 |
| overall | 10 | 10 | 53 | 0.500 | 0.159 |

- Requirements: numbered 0 of 11, unnumbered 0 of 2.
- Submission deadline: key 2027-01-21 15:00, parsed none.
- Page limit: key 20, parsed none.
- Addendum handling: 0 of 0.
- Deadline kind outside the existing keys (start_of_services 2027-04-01): not found; not counted either way.

- missed deadlines: issued 2026-12-07 None
- missed deadlines: conference 2026-12-15 10:30
- missed deadlines: questions_due 2026-12-18 17:00
- missed deadlines: answers_issued 2027-01-06 None
- missed deadlines: submission_due 2027-01-21 15:00
- missed deadlines: interview 2027-02-08 None
- missed deadlines: award 2027-03-09 None
- missed requirements: E(i) | Transmittal Letter. Provide a letter of no more than two pages, signed
- missed requirements: E(ii) | Firm Description. Describe the firm's history, ownership, size and off
- missed requirements: E(iii) | Proposed Attorneys. Identify the lead counsel, the backup counsel and 
- missed requirements: E(iv) | Education Law Experience. Describe the firm's experience over the last
- missed requirements: E(v) | Service Approach. Explain how the firm would handle day-to-day request
- missed requirements: E(vi) | How would the firm staff two urgent matters arising in the same week, 
- missed requirements: E(vii) | References. Give the name, title, telephone number and email address o
- missed requirements: E(viii) | Conflicts of Interest. Disclose any present or past representation of 
- missed requirements: E(ix) | Fee Proposal. State the hourly rate for each attorney and paralegal, a
- missed requirements: E(x) | Transition Plan. Describe the steps the firm would take in its first n
- missed requirements: E(xi) | Claims and Discipline. Has the firm, or any attorney named in the prop
- missed requirements: E-unnumbered-1 | In addition to the numbered items, every proposal must include a one-p
- missed requirements: E-unnumbered-2 | A proposer that takes exception to any term of the District's standard
- missed forms: Proposal Certification and Signature Page
- missed forms: Non-Collusion Declaration
- missed forms: Disclosure of Relationships with District Officials
- missed forms: Acknowledgment of Addenda
- missed forms: taxpayer identification form (Form W-9)
- missed forms: evidence of insurance
- missed evaluation: demonstrated experience in community college and education law 40
- missed evaluation: qualifications and availability of the proposed attorneys 25
- missed evaluation: service approach and responsiveness 15
- missed evaluation: fees 15
- missed evaluation: references 5
- missed min_quals: The attorney proposed as lead counsel shall have been a memb | years_admitted 10
- missed min_quals: The firm shall employ at least five | attorney_count 5
- missed min_quals: The firm shall have served as general counsel to at least th | not_checkable None
- missed min_quals: The firm shall maintain a staffed office within Calloway Cou | office_location Calloway County
- missed insurance: professional liability insurance $3,000,000
- missed insurance: commercial general liability insurance $1,000,000
- missed insurance: workers' compensation insurance None
- missed insurance: automobile liability insurance $1,000,000
- missed mechanics: ('kind', 'copies')
- missed mechanics: ('kind', 'format')
- missed mechanics: ('kind', 'packaging')
- missed mechanics: ('kind', 'delivery')
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_limit')
- missed mechanics: ('kind', 'page_exclusions')
- missed mechanics: ('kind', 'font')
- missed mechanics: ('kind', 'margins')
- missed mechanics: ('page_limit', 20)
- missed mechanics: ('font', 12)
- missed mechanics: ('margins', 1.0)
- extra parties: Sorrel Canyon (board)
- extra parties: Alaric Fenwick (board)
- extra parties: Marguerite Solberg (board)
- extra parties: Firm Description (staff)
- extra parties: Proposed Attorneys (staff)
- extra parties: Education Law Experience (staff)
- extra parties: Service Approach (staff)
- extra parties: Faculty Association (staff)
- extra parties: Classified Employees Union (staff)
- extra parties: Transition Plan (staff)
- missed parties: Alaric Fenwick (staff)
- missed parties: Marguerite Solberg (staff)

## litigation_counsel_lantern_bay_port

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 0 | 0 | 6 | 1.000 | 0.000 |
| requirements | 0 | 0 | 14 | 1.000 | 0.000 |
| forms | 0 | 0 | 4 | 1.000 | 0.000 |
| evaluation | 0 | 0 | 5 | 1.000 | 0.000 |
| min_quals | 0 | 0 | 4 | 1.000 | 0.000 |
| insurance | 0 | 0 | 4 | 1.000 | 0.000 |
| mechanics | 0 | 0 | 8 | 1.000 | 0.000 |
| parties | 9 | 5 | 4 | 0.643 | 0.692 |
| overall | 9 | 5 | 49 | 0.643 | 0.155 |

- Requirements: numbered 0 of 10, unnumbered 0 of 4.
- Submission deadline: key 2027-01-15 16:30, parsed none.
- Page limit: key 18, parsed none.
- Addendum handling: 0 of 0.

- missed deadlines: issued 2026-12-01 None
- missed deadlines: questions_due 2026-12-15 16:00
- missed deadlines: answers_issued 2026-12-22 None
- missed deadlines: submission_due 2027-01-15 16:30
- missed deadlines: interview 2027-02-02 None
- missed deadlines: award 2027-02-23 None
- missed requirements: 6-unnumbered-1 | The cover letter must be signed by a partner, must identify the attorn
- missed requirements: 6-unnumbered-2 | Separately from the questionnaire answers, provide one writing sample:
- missed requirements: B-1 | Describe the firm: when it was founded, how many attorneys it has, whe
- missed requirements: B-2 | Who would lead the trial team, and who else would be on it? For each p
- missed requirements: B-3 | Describe up to six construction disputes the firm has litigated or arb
- missed requirements: B-4 | Describe the firm's experience in environmental litigation, including 
- missed requirements: B-5 | How would the firm approach the first ninety days of the three matters
- missed requirements: B-6 | How does the firm control litigation cost? Describe the firm's budgeti
- missed requirements: B-7 | Provide four references from public agency clients for litigation hand
- missed requirements: B-8 | Identify every matter in the last five years in which the firm represe
- missed requirements: B-9 | State the hourly rate of each person named in B-2, the rates of parale
- missed requirements: B-10 | If the firm is chosen, how would it take over the Carrowmore matter fr
- missed requirements: B-unnumbered-1 | whether any attorney named in B-2 has been sanctioned by a court in th
- missed requirements: B-unnumbered-2 | whether the firm is a certified small business or is owned by a reside
- missed forms: Proposer's Declaration
- missed forms: Declaration of Non-Collusion
- missed forms: Statement of Economic Interests and Campaign Contributions
- missed forms: Insurance Acknowledgment
- missed evaluation: Experience in comparable litigation 35
- missed evaluation: the proposed trial team 30
- missed evaluation: approach and case management 15
- missed evaluation: cost 15
- missed evaluation: the writing sample 5
- missed min_quals: the attorney who will lead the trial team must have been adm | years_admitted 15
- missed min_quals: that attorney must have tried at least five civil cases | not_checkable None
- missed min_quals: the firm must have no fewer than eight | attorney_count 8
- missed min_quals: the firm must not currently represent any party named in par | not_checkable None
- missed insurance: professional liability insurance $5,000,000
- missed insurance: commercial general liability insurance $2,000,000
- missed insurance: automobile liability insurance $1,000,000
- missed insurance: workers' compensation insurance None
- missed mechanics: ('kind', 'format')
- missed mechanics: ('kind', 'delivery')
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_limit')
- missed mechanics: ('kind', 'page_exclusions')
- missed mechanics: ('kind', 'font')
- missed mechanics: ('page_limit', 18)
- missed mechanics: ('font', 11)
- extra parties: Seren Oyelowo (staff)
- extra parties: Beatrix Halloran (staff)
- extra parties: Carrowmore Marine Constructors (staff)
- extra parties: North Channel (staff)
- extra parties: Seagrass Coalition (staff)
- missed parties: Hollis Trevanion (staff)
- missed parties: Seren Oyelowo (board)
- missed parties: Beatrix Halloran (board)
- missed parties: Seagrass Coalition of Lantern Bay (adverse)
