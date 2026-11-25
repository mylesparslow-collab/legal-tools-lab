# Buy America bill-of-materials auditor

Checks a transit bill of materials against two federal domestic-content rules that work differently:

- **FTA Buy America** (49 U.S.C. 5323(j), 49 CFR Parts 661 and 663) for rolling stock, steel and iron, and manufactured products.
- **Build America, Buy America** (2 CFR Part 184) for construction materials, and for manufactured products and steel when the funding program uses Part 184's standard.

It is a personal portfolio demo. I am not an attorney. The sample agency, suppliers, parts and prices are made up. The output is a worksheet for a qualified reviewer, not a compliance determination and not legal advice.

## What it does

**Rolling stock.** For each vehicle it reads components and subcomponents and applies 49 CFR 661.11:

- A subcomponent is domestic if it is manufactured in the US.
- A US-manufactured component counts in full if more than the required share of its subcomponents, by cost, is domestic.
- A US-manufactured component that misses that share counts its domestic subcomponents plus the cost of manufacturing the component (661.11(l)).
- A foreign-manufactured component counts nothing, except US subcomponents that re-enter under the tariff exemption (661.11(i), (j)).
- Waived items are treated as domestic (661.7(f)).
- US steel in a foreign frame or car shell counts when the average vehicle costs more than $300,000 (5323(j)(5)).

The vehicle passes if domestic cost is more than the required share of all component cost and final assembly is in the US. The required share comes from the statute's schedule by fiscal year of delivery: 60%, then 65%, then 70% from FY2020.

**Depot and facility items.** Each item carries a category. Steel and iron are tested on where the manufacturing processes took place. Construction materials are tested against the 2 CFR 184.6 standard for that material. Manufactured products get both tests, FTA's (every component US-manufactured) and BABA's (more than 55% US component cost), shown side by side. The result that counts is the one that matches the funding source.

**Documents.** Bidder certificates under 661.6 and 661.12, and the pre-award and post-delivery audit certifications under Part 663, checked against the project's stage. Includes the resident inspector exceptions.

**Buy Clean California.** Off unless the awarding authority is a state agency, UC or CSU. No GWP limits are loaded.

## What it does not do

- It does not classify items. Whether something is a component, a subcomponent, a construction material or its own end product is an input, and often a judgment call. Unclassified items come back as REVIEW.
- There is no language-model layer. The report described one for reading supplier documents; this build is the deterministic part only.
- It does not fetch waivers. A waiver reference on a line is taken as given and flagged for confirmation.
- Spare parts (Appendix A to 661.11), options, piggyback contracts and pre-2016 contracts are not modeled.

## Run it

```
pip install openpyxl pytest
python generate_synthetic.py     # rewrites sample_data/
python run_audit.py              # writes output/
python -m pytest tests -q
```

`output/Buy_America_BOM_Audit.xlsx` has live formulas. Change a country or a cost in a yellow cell and the percentages and results recalculate. `output/findings.md` is the same audit as a memo.

To use your own data, copy the column layout of `sample_data/bom.csv` and the fields in `sample_data/case.json`, then run `python run_audit.py --case your.json --bom your.csv --out your_dir`.

## Sample results

| Project | Result | Why |
|---|---|---|
| 30 battery electric buses | Vehicle passes at 71.83% (needs more than 70%). Project is REVIEW. | Post-delivery audit documents are not due yet. Three US-made components get partial credit under 661.11(l). |
| 12 light rail vehicles | FAIL at 66.67% | About $105,000 per car short. The foreign car shell earns $140,000 of US steel credit. |
| Depot charging upgrade | FAIL | The chargers pass BABA's 55% test (82.1%) but fail FTA's all-components test because of two foreign components. Rebar coated abroad and fiber drawn abroad also fail. |

## Rules are data

Every threshold is in `buy_america/rules.json` with its source, a status (`verified`, `partially_verified` or `not_loaded`), the date it was checked and how. `engine.py` contains no thresholds, and a test enforces that. The workbook's formulas point at the Rules sheet.

"Verified" means I read the text at that source on that date. It does not mean a lawyer has confirmed how the rule applies.

## Files

- `buy_america/engine.py`: the rules logic.
- `buy_america/rules.json`: thresholds and sources.
- `buy_america/workbook.py`: the live-formula workbook.
- `buy_america/report.py`: the findings memo.
- `generate_synthetic.py`, `sample_data/`: the made-up agency and bills of materials.
- `tests/`: 40 tests, including one that recalculates the workbook in LibreOffice and compares it to the engine.
- `CORRECTIONS.md`: where the research report this came from was wrong.
