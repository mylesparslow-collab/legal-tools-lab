# Held-out batch B, single final run (sealed until this run)

The RFPs and keys were written by an independent author who had not read the parser.
Scoring rules are in desk/heldout_score.py. Items the parser marked "check" count like
any other item. Addendum handling is its own line and is not part of the overall figure.

## All RFPs in the batch together

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 9 | 3 | 10 | 0.750 | 0.474 |
| requirements | 20 | 6 | 15 | 0.769 | 0.571 |
| forms | 3 | 0 | 12 | 1.000 | 0.200 |
| evaluation | 10 | 4 | 6 | 0.714 | 0.625 |
| min_quals | 0 | 0 | 13 | 1.000 | 0.000 |
| insurance | 5 | 3 | 6 | 0.625 | 0.455 |
| mechanics | 17 | 1 | 14 | 0.944 | 0.548 |
| parties | 23 | 5 | 7 | 0.821 | 0.767 |
| overall | 87 | 22 | 83 | 0.798 | 0.512 |

- Submission deadline (date and time in force) right on 1 of 3 RFPs.
- Page limit in force right on 2 of 3 RFPs.
- Addendum handling: 5 of 11 checks passed.
- Question type right on 20 of the 20 requirements found (35 in the keys).

## general_counsel_dunmarrow_housing

Agency name correct: no

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 4 | 3 | 3 | 0.571 | 0.571 |
| requirements | 10 | 6 | 0 | 0.625 | 1.000 |
| forms | 1 | 0 | 5 | 1.000 | 0.167 |
| evaluation | 4 | 1 | 1 | 0.800 | 0.800 |
| min_quals | 0 | 0 | 4 | 1.000 | 0.000 |
| insurance | 4 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 10 | 0 | 2 | 1.000 | 0.833 |
| parties | 6 | 2 | 3 | 0.750 | 0.667 |
| overall | 39 | 12 | 18 | 0.765 | 0.684 |

- Requirements: numbered 10 of 10, unnumbered 0 of 0.
- Submission deadline: key 2027-02-05 12:00, parsed 2027-02-05 12:00.
- Page limit: key 24, parsed [24].
- Addendum handling: 5 of 11.
  - ok: submission_due: date as issued (2027-01-20) still shown
  - ok: submission_due in force 2027-02-05 12:00
  - FAILED: answers_issued in force 2027-01-11
  - ok: page limit in force 24
  - FAILED: form added: Acknowledgment of Addenda
  - FAILED: interview in force 2027-02-18
  - FAILED: award in force 2027-03-10
  - ok: requirement 4.3.6 deleted
  - FAILED: criterion removed: Resident services and relocation experience
  - FAILED: weight of Development and finance experience now 30
  - ok: form removed: Local Hiring Certification

- extra deadlines: answers_issued 2027-01-29 None
- extra deadlines: interview 2027-03-10 None
- extra deadlines: award 2027-02-24 None
- missed deadlines: answers_issued 2027-01-11 None
- missed deadlines: interview 2027-02-18 None
- missed deadlines: award 2027-03-10 None
- extra requirements: 4.1.1 | The firm's proposed lead general counsel must have at least ten (10) y
- extra requirements: 4.1.2 | A firm proposing for development counsel must have closed, as counsel 
- extra requirements: 4.1.3 | The firm must be able to attend Board meetings in person in the City o
- extra requirements: 4.1.4 | The firm must not be debarred or suspended from contracting with any p
- extra requirements: 4.2 | Organization. Proposals must follow the order of Section 4.3 and use i
- extra requirements: 4.3 | Narrative.
- missed forms: Proposer Profile and Certification
- missed forms: Non-Collusive Affidavit
- missed forms: Certification Regarding Debarment and Suspension
- missed forms: Conflict of Interest Disclosure
- missed forms: Acknowledgment of Addenda
- extra evaluation: Resident services and relocation experience 5
- missed evaluation: Development and finance experience 30
- missed min_quals: The firm's proposed lead general counsel must have at least  | years_admitted 10
- missed min_quals: A firm proposing for development counsel must have closed | not_checkable None
- missed min_quals: The firm must be able to attend Board meetings in person | not_checkable None
- missed min_quals: The firm must not be debarred or suspended | not_checkable None
- missed mechanics: ('kind', 'format')
- missed mechanics: ('kind', 'not_accepted')
- extra parties: County of Dunmarrow (agency)
- extra parties: Rook Construction Co. (adverse)
- missed parties: Housing Authority of the County of Dunmarrow (agency)
- missed parties: Cormac Adebayo (staff)
- missed parties: Tallis & Rook Construction Co. (adverse)

## labor_counsel_wexcombe_library

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 0 | 0 | 6 | 1.000 | 0.000 |
| requirements | 0 | 0 | 12 | 1.000 | 0.000 |
| forms | 0 | 0 | 4 | 1.000 | 0.000 |
| evaluation | 0 | 0 | 5 | 1.000 | 0.000 |
| min_quals | 0 | 0 | 5 | 1.000 | 0.000 |
| insurance | 0 | 0 | 3 | 1.000 | 0.000 |
| mechanics | 0 | 0 | 9 | 1.000 | 0.000 |
| parties | 7 | 2 | 3 | 0.778 | 0.700 |
| overall | 7 | 2 | 47 | 0.778 | 0.130 |

- Requirements: numbered 0 of 10, unnumbered 0 of 2.
- Submission deadline: key 2027-01-14 14:00, parsed none.
- Page limit: key 15, parsed none.
- Addendum handling: 0 of 0.

- missed deadlines: issued 2026-12-10 None
- missed deadlines: questions_due 2027-01-04 17:00
- missed deadlines: answers_issued 2027-01-08 None
- missed deadlines: submission_due 2027-01-14 14:00
- missed deadlines: interview 2027-01-26 None
- missed deadlines: award 2027-02-17 None
- missed requirements: #1 | Introduction letter. Tell us who you are and who will sign the contrac
- missed requirements: #2 | About your firm. How big is it, where are its offices, how long has it
- missed requirements: #3 | Your people. Who will be chief negotiator? Who will back that person u
- missed requirements: #4 | Bargaining record. List the public sector negotiations your proposed c
- missed requirements: #5 | How you would run our negotiations. Describe how you would prepare, ho
- missed requirements: #6 | Hearings and advice. Describe your experience in grievance arbitration
- missed requirements: #7 | References. Give us four public employer references. At least two must
- missed requirements: #8 | Conflicts. Have you or anyone at your firm ever represented the Wexcom
- missed requirements: #9 | Price. Give hourly rates for every person named in #3. Offer a fixed m
- missed requirements: #10 | Taking over. Our current counsel is retiring. How would you get up to 
- missed requirements: 5-unnumbered-1 | A statement, signed by the proposed chief negotiator, that he or she w
- missed requirements: 5-unnumbered-2 | A list of every lawsuit or labor board charge filed against your firm 
- missed forms: Proposal Signature Form
- missed forms: Non-Collusion Statement
- missed forms: Disclosure of Gifts and Relationships
- missed forms: proof of your professional liability insurance
- missed evaluation: Bargaining experience and record 35
- missed evaluation: The chief negotiator and team 25
- missed evaluation: Plan for our negotiations 20
- missed evaluation: Price 15
- missed evaluation: References 5
- missed min_quals: Your proposed chief negotiator has practiced law for at leas | years_admitted 8
- missed min_quals: Your proposed chief negotiator has been chief negotiator for | not_checkable None
- missed min_quals: Your firm has at least four (4) attorneys | attorney_count 4
- missed min_quals: Your firm does not represent any labor union | not_checkable None
- missed min_quals: Your chief negotiator can attend bargaining sessions in pers | not_checkable None
- missed insurance: professional liability insurance of at least $2,000,000
- missed insurance: general liability insurance of at least $1,000,000
- missed insurance: workers' compensation insurance None
- missed mechanics: ('kind', 'copies')
- missed mechanics: ('kind', 'format')
- missed mechanics: ('kind', 'delivery')
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_limit')
- missed mechanics: ('kind', 'page_exclusions')
- missed mechanics: ('kind', 'font')
- missed mechanics: ('page_limit', 15)
- missed mechanics: ('font', 11)
- extra parties: Wexcombe Library Workers Guild (other_organisation)
- extra parties: Calder Whitlock (board)
- missed parties: Calder Whitlock (staff)
- missed parties: Wexcombe Library Workers Guild (adverse)
- missed parties: Service Employees Local 4410 (adverse)

## water_rights_counsel_saltbrook_muc

Agency name correct: yes

| Category | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| deadlines | 5 | 0 | 1 | 1.000 | 0.833 |
| requirements | 10 | 0 | 3 | 1.000 | 0.769 |
| forms | 2 | 0 | 3 | 1.000 | 0.400 |
| evaluation | 6 | 3 | 0 | 0.667 | 1.000 |
| min_quals | 0 | 0 | 4 | 1.000 | 0.000 |
| insurance | 1 | 3 | 3 | 0.250 | 0.250 |
| mechanics | 7 | 1 | 3 | 0.875 | 0.700 |
| parties | 10 | 1 | 1 | 0.909 | 0.909 |
| overall | 41 | 8 | 18 | 0.837 | 0.695 |

- Requirements: numbered 10 of 10, unnumbered 0 of 3.
- Submission deadline: key 2027-01-19 14:00, parsed none.
- Page limit: key 20, parsed [20].
- Addendum handling: 0 of 0.

- missed deadlines: submission_due 2027-01-19 14:00
- missed requirements: S4-unnumbered-1 | What is the firm's view of the main risks to the Commission's 1954 rig
- missed requirements: S4-unnumbered-2 | If the lead attorney became unavailable for a month during the hearing
- missed requirements: S4-unnumbered-3 | Describe one matter in which the firm negotiated a long-term water pur
- missed forms: Non-Collusion Affidavit
- missed forms: Campaign Contribution Disclosure
- missed forms: Insurance Commitment Letter
- extra evaluation:  None
- extra evaluation:  None
- extra evaluation: 1.00 None
- missed min_quals: Lead attorney: admitted to practice 12 years or longer | years_admitted 12
- missed min_quals: Lead attorney: has appeared as counsel of record | not_checkable None
- missed min_quals: Firm: at least 2 attorneys other than the lead attorney | not_checkable None
- missed min_quals: Firm: no current client relationship with either adverse par | not_checkable None
- extra insurance: Professional liability: USD 5,000,000 per claim
- extra insurance: Commercial general liability: USD 2,000,000 per occurrence
- extra insurance: Automobile liability: USD 1,000,000 combined single limit
- missed insurance: Professional liability USD 5,000,000
- missed insurance: Commercial general liability USD 2,000,000
- missed insurance: Automobile liability USD 1,000,000
- extra mechanics: ('kind', 'copies')
- missed mechanics: ('kind', 'delivery')
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_exclusions')
- extra parties: Senior Contracts (staff)
- missed parties: Upper Tamsel Irrigation District (adverse)
