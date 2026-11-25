# Scorecard: Sample Tool B (made-up output, not a real product)

Documents scored: 12

| Measure | Result | Pass mark |
| --- | --- | --- |
| High-severity issue recall | 42% | 90% |
| All-issue recall | 42% | |
| Quote grounding | 87% | 98% |
| Net time saved (modeled) | +330 min of 2410 min unaided (14%) | |
| Result | Does not pass | |

## By document type

| Type | Docs | High recall | Recall | Grounding | Net min saved |
| --- | --- | --- | --- | --- | --- |
| Commercial leases | 3 | 56% | 55% | 85% | +122 |
| Executive employment agreements | 3 | 35% | 35% | 83% | +43 |
| Public works contracts | 3 | 44% | 44% | 83% | +86 |
| SNF and RCFE asset purchase agreements | 3 | 35% | 36% | 100% | +78 |

## By document

| Document | Found | Missed | Findings | Quotes verified | Extra findings | Net min saved |
| --- | --- | --- | --- | --- | --- | --- |
| apa-01 | 5 of 7 | apa-01-D2, apa-01-D5 | 7 | 7 of 7 | 2 | +74 |
| apa-02 | 2 of 7 | apa-02-D1, apa-02-D2, apa-02-D3, apa-02-D6, apa-02-D7 | 4 | 4 of 4 | 2 | +16 |
| apa-03 | 1 of 8 | apa-03-D1, apa-03-D2, apa-03-D3, apa-03-D4, apa-03-D5, apa-03-D6, apa-03-D8 | 4 | 4 of 4 | 3 | -12 |
| emp-01 | 3 of 8 | emp-01-D2, emp-01-D3, emp-01-D4, emp-01-D5, emp-01-D7 | 6 | 6 of 6 | 3 | +26 |
| emp-02 | 3 of 7 | emp-02-D2, emp-02-D5, emp-02-D6, emp-02-D7 | 7 | 4 of 7 | 4 | +9 |
| emp-03 | 2 of 8 | emp-03-D1, emp-03-D2, emp-03-D4, emp-03-D5, emp-03-D6, emp-03-D7 | 5 | 5 of 5 | 3 | +8 |
| lease-01 | 4 of 7 | lease-01-D3, lease-01-D5, lease-01-D6 | 6 | 4 of 6 | 2 | +29 |
| lease-02 | 4 of 6 | lease-02-D1, lease-02-D6 | 7 | 7 of 7 | 3 | +69 |
| lease-03 | 3 of 7 | lease-03-D1, lease-03-D4, lease-03-D6, lease-03-D7 | 7 | 6 of 7 | 4 | +25 |
| pw-01 | 2 of 9 | pw-01-D1, pw-01-D2, pw-01-D3, pw-01-D5, pw-01-D6, pw-01-D7, pw-01-D8 | 5 | 4 of 5 | 3 | 0 |
| pw-02 | 4 of 8 | pw-02-D1, pw-02-D2, pw-02-D7, pw-02-D8 | 6 | 5 of 6 | 2 | +33 |
| pw-03 | 5 of 8 | pw-03-D2, pw-03-D7, pw-03-D8 | 7 | 6 of 7 | 2 | +53 |

## Quotes that could not be verified

These were presented by the tool as quotes but do not appear word for word in the document.

- emp-02, finding 3: [UNVERIFIED QUOTE] If the Executive resigns for any reason before the first anniversary of the Start Date, the Executive shall pay the Company, and related obligations as described above
- emp-02, finding 6: [UNVERIFIED QUOTE] This assignment extends to Developments that the Executive creates on the Executive's own time, with the Executive's own equipment and without Proprietary Information, and and related obligations as described above
- emp-02, finding 7: [UNVERIFIED QUOTE] The Executive shall not make any statement, to any person and by any means, about conduct in the workplaces of the and related obligations as described above
- lease-01, finding 4: [UNVERIFIED QUOTE] This Shopping Center Lease (this "Lease") is dated as of January 12, 2027 (the "Effective Date") and is made between Tamsin Ridge and related obligations as described above
- lease-01, finding 5: [UNVERIFIED QUOTE] to Tenant within ninety (90) days after the Expiration and related obligations as described above
- lease-03, finding 5: [UNVERIFIED QUOTE] the occupant shall pay Lessor $1,000 per trailer for each day or part of a day, as liquidated damages, and related obligations as described above
- pw-01, finding 3: [UNVERIFIED QUOTE] a payment bond in a penal sum equal to fifty percent (50%) of the Contract and related obligations as described above
- pw-02, finding 2: [UNVERIFIED QUOTE] The City shall release the retention, less amounts withheld under this Contract, one hundred twenty (120) days after the and related obligations as described above
- pw-03, finding 6: [UNVERIFIED QUOTE] Heavy-duty in-ground vehicle lifts shall be Grayling Liftworks Model GL-3X three-post modular and related obligations as described above

## How to read this

- Recall counts a planted defect as found when a finding quotes the defective clause word for word, or, for a missing clause, cites the right section. A reviewer can override any match.
- Extra findings are findings that match no planted defect. They may be false alarms or real points outside the answer key. Each still costs verification time.
- Net time saved is a model, not a measurement. Time with the tool = setup (5 min) + tool run time + verification (4 min per finding, plus 6 min for each unverified quote, or the measured figure if the run supplies one) + a read-through (25% of unaided time) + the remaining review time in proportion to the severity-weighted share of defects missed.
- The documents are synthetic and the answer keys cover only the planted defects. A pass here says nothing about real matters.
