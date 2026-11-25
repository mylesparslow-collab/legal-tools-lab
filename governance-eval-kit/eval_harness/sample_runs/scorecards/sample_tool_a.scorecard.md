# Scorecard: Sample Tool A (made-up output, not a real product)

Documents scored: 12

| Measure | Result | Pass mark |
| --- | --- | --- |
| High-severity issue recall | 96% | 90% |
| All-issue recall | 97% | |
| Quote grounding | 100% | 98% |
| Net time saved (modeled) | +1264 min of 2410 min unaided (52%) | |
| Result | Pass | |

## By document type

| Type | Docs | High recall | Recall | Grounding | Net min saved |
| --- | --- | --- | --- | --- | --- |
| Commercial leases | 3 | 100% | 100% | 100% | +314 |
| Executive employment agreements | 3 | 91% | 91% | 100% | +294 |
| Public works contracts | 3 | 96% | 96% | 100% | +299 |
| SNF and RCFE asset purchase agreements | 3 | 100% | 100% | 100% | +356 |

## By document

| Document | Found | Missed | Findings | Quotes verified | Extra findings | Net min saved |
| --- | --- | --- | --- | --- | --- | --- |
| apa-01 | 7 of 7 | none | 7 | 7 of 7 | 0 | +122 |
| apa-02 | 7 of 7 | none | 7 | 7 of 7 | 0 | +99 |
| apa-03 | 8 of 8 | none | 9 | 9 of 9 | 1 | +136 |
| emp-01 | 6 of 8 | emp-01-D4, emp-01-D7 | 7 | 7 of 7 | 1 | +81 |
| emp-02 | 7 of 7 | none | 7 | 7 of 7 | 0 | +109 |
| emp-03 | 8 of 8 | none | 9 | 9 of 9 | 1 | +104 |
| lease-01 | 7 of 7 | none | 7 | 7 of 7 | 0 | +99 |
| lease-02 | 6 of 6 | none | 7 | 7 of 7 | 1 | +111 |
| lease-03 | 7 of 7 | none | 7 | 7 of 7 | 0 | +104 |
| pw-01 | 9 of 9 | none | 10 | 10 of 10 | 1 | +106 |
| pw-02 | 7 of 8 | pw-02-D3 | 8 | 8 of 8 | 1 | +86 |
| pw-03 | 8 of 8 | none | 8 | 8 of 8 | 0 | +107 |

## How to read this

- Recall counts a planted defect as found when a finding quotes the defective clause word for word, or, for a missing clause, cites the right section. A reviewer can override any match.
- Extra findings are findings that match no planted defect. They may be false alarms or real points outside the answer key. Each still costs verification time.
- Net time saved is a model, not a measurement. Time with the tool = setup (5 min) + tool run time + verification (4 min per finding, plus 6 min for each unverified quote, or the measured figure if the run supplies one) + a read-through (25% of unaided time) + the remaining review time in proportion to the severity-weighted share of defects missed.
- The documents are synthetic and the answer keys cover only the planted defects. A pass here says nothing about real matters.
