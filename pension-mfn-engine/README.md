# Public-pension side-letter gate and MFN election engine (report Tool 9)

A small Python engine with two jobs:

1. **Statutory gate.** Screens a draft side letter for a California public retirement system against rules stored as data, and reports each hit with the exact sentence from the draft.
2. **MFN election filter.** Reads an MFN compendium, works out which provisions the investor can elect from its commitment tier, legal status and the fund agreement's carve-outs, and writes a Word election memo with page numbers and verbatim text.

Personal portfolio demo. All data is invented (fund, investors, people, clauses, registry). I am not an attorney and nothing here is legal advice. See `CORRECTIONS.md` for where the source research report did not match the statutes.

## Run
```
python3 generate_synthetic.py                       # writes sample_data/
python3 -m sideletter.cli --model-output sample_data/model_output.json -o output/state
python3 -m sideletter.cli --investor sample_data/investor_county.json -o output/county
python3 -m pytest -q tests                          # 29 tests
```
Needs Python 3.10+ and `python-docx`.

Each run writes `Election_Memo.docx`, `Election_Memo.md`, `results.json` and `MFN_Election_Deadline.ics`.

## What is deterministic
* **Which rules apply.** State system or local system, fund type, contract date. For example the contingent-fee bar (§ 86205(f)) and lobbyist registration (§ 7513.86) apply to the state sample and return "not applicable" for the county sample.
* **Coverage checks.** The nine disclosable items in § 7928.710(c) and the four disclosure items in § 7514.7(a)(1)-(4) are checked by name.
* **Registry cross-check.** Named placement agents against a registry snapshot (synthetic CSV here).
* **MFN eligibility.** Commitment threshold from each provision's lead-in against the investor's commitment (plus affiliates if the fund file says to aggregate), status conditions, initial-closing and GP-affiliate grants, and carved-out categories.
* **Deadline.** Delivery date plus the window in the fund file, calendar or business days, optional weekend roll-forward. There is no holiday calendar.

## What is a screening heuristic
The red-flag patterns ("without incremental expense", "prior written consent", "payable upon admission" and so on) are regular expressions I wrote. A hit means "read this sentence". No hit returns `ADDRESSED`, which means a clause was found and nothing matched; it does not mean the clause complies.

## Quote verification
* Every finding and every eligibility reason carries a quote, and the run stops if any quote is not found verbatim in its source (whitespace aside).
* Anything the parser cannot read (no "Granted to" lead-in, an unrecognised qualifier, a stray dollar figure) is returned as `REVIEW` rather than guessed.
* **Model layer.** No model is called in this build. `--model-output` takes a JSON file of proposed items (provision, page, category, quote). An item is used only if the provision exists, the page matches, the category is in the fixed list and the quote is verbatim in that provision. A model can change a provision's category label; it cannot change tier or status arithmetic, and moving a provision out of a carved-out category sends it to `REVIEW`. The sample file has two good items and three bad ones; the bad ones are rejected and listed in the memo.

## Rules as data
`rules/statutory_rules.json` holds each rule with its citation, leginfo URL, a verbatim quote, a verification status, the report's claim and the correction.

| Status | Meaning | Rules |
|---|---|---|
| verified_primary_text | Section read on leginfo Nov. 25, 2026 | §§ 7514.7, 7928.710, 7513.85, 7513.86, 7513.87, 7513.9, 86205(f) with 82039(a)(2), 82047.3, 82002(a)(2) |
| interpretive_attorney_review | Text read, application is an interpretation | Cal. Const. art. XVI § 6 (indemnity) |
| unverified | No authority confirmed | Immunity, forum and jury waivers |

## Sample results
| | State system ($85M + $40M affiliate) | County system ($60M) |
|---|---|---|
| Gate flags / gaps / missing / review | 13 / 2 / 1 / 3 | 10 / 2 / 1 / 3 |
| MFN: electable / review / not electable (of 36) | 21 / 2 / 13 | 16 / 2 / 18 |
| Deadline (20 calendar days from Nov. 16, 2026; Dec. 6 is a Sunday) | Dec. 7, 2026 | Dec. 7, 2026 |

## Limits
* Plain-text inputs only. Reading a real LPA or compendium from Word or PDF, with real page numbers, is not built.
* The compendium parser expects "Provision N." numbering and a "Granted to ..." lead-in. Real compendia vary; unreadable items go to review.
* A status list in a lead-in is treated as "any of". 
* No live Cal-Access lookup and no local lobbying registries.
* The category keywords and the status vocabulary are mine and need a practitioner's review.
