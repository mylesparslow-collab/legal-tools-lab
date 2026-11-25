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
| forms | 18 | 1 | 0 | 0.947 | 1.000 |
| evaluation | 20 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 13 | 0 | 0 | 1.000 | 1.000 |
| insurance | 12 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 37 | 0 | 0 | 1.000 | 1.000 |
| parties | 33 | 0 | 0 | 1.000 | 1.000 |
| overall | 199 | 1 | 0 | 0.995 | 1.000 |

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
| forms | 4 | 1 | 0 | 0.800 | 1.000 |
| evaluation | 5 | 0 | 0 | 1.000 | 1.000 |
| min_quals | 3 | 0 | 0 | 1.000 | 1.000 |
| insurance | 3 | 0 | 0 | 1.000 | 1.000 |
| mechanics | 10 | 0 | 0 | 1.000 | 1.000 |
| parties | 7 | 0 | 0 | 1.000 | 1.000 |
| overall | 50 | 1 | 0 | 0.980 | 1.000 |

- extra forms: Exhibit 2 (named in section SECTION V)

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
## Held-out document: bond_counsel_gullwing_harbor.txt

A fifth RFP in a layout the parser was not written for. It is not one of the four sample RFPs.

First run, before any change to the parser: precision 0.667, recall 0.136 (6 correct, 3 extra, 38 missed).
The parser did not recognise the 'Article 1.  Title' headings (mixed case), so it found no sections. It reported 7 items for a person to check, including 'no submission deadline found' and 'no numbered proposal requirements found'.

After six general fixes prompted by that run (mixed-case 'Article' headings, 'Tab N' labels, three more
heading keywords, weight-first criteria, 'longer than N pages'): precision 0.825, recall 0.750
(33 correct, 7 extra, 11 missed). This second figure is no longer held out. The remaining
misses were left unfixed on purpose and are listed here:

- extra deadlines: unknown 2027-01-12 None
- missed deadlines: {'kind': 'interview', 'date': '2026-12-14', 'time': None}
- missed deadlines: {'kind': 'award', 'date': '2027-01-12', 'time': None}
- extra forms: Form 10 (named in section Article 5)
- extra forms: Form 11 (named in section Article 5)
- missed forms: Proposer's Affidavit
- missed forms: Statement of Insurance
- missed forms: Acknowledgment of any addenda
- extra insurance: The District does not require other coverage for this engage
- missed mechanics: ('kind', 'not_accepted')
- missed mechanics: ('kind', 'page_exclusions')
- missed mechanics: ('kind', 'font')
- missed mechanics: ('font', 11)
- extra parties: Clementine Radcliffe (staff)
- extra parties: Jasper Thibodeaux (staff)
- extra parties: Lowtide Advisory Partners (staff)
- missed parties: {'name': 'Clementine Radcliffe', 'category': 'board'}
- missed parties: {'name': 'Jasper Thibodeaux', 'category': 'board'}
- question type: Tab 2: other, key says firm_overview
- question type: Tab 3: other, key says team
- question type: Tab 4: other, key says experience
- question type: Tab 5: other, key says approach

The first-run figure is the better guide to what happens on an RFP layout nobody has tuned for.
