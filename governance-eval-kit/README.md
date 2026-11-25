# Governance and eval kit

Four small pieces for running AI tools in a California law practice with some discipline: a registry of what is in use, a way to score tools on documents with known answers, a set of checklist agents, and a court-deadline calculator that shows its work.

This is a personal portfolio demo. All names, parties, documents and results in it are fictional. It is not legal advice, it was not written or reviewed by an attorney, and it is not deployed anywhere. Statutes were read on November 25, 2026; see `VERIFICATION.md` and `CORRECTIONS.md`.

## What is here

| Folder | What it does |
| --- | --- |
| `registry/` | A one-page AI Tool Registry: owner, data boundary, outside counsel guideline check, golden-set score and SB 574 verification log for each tool. Blank template, JSON schema, a checker that flags gaps, and a one-page HTML, Markdown and CSV view. |
| `eval_harness/` | Scores an AI review tool on 12 synthetic California documents with planted defects. Reports issue recall, quote grounding and modeled net time saved. |
| `copilot_agents/` | Five Microsoft 365 Copilot declarative agent packages built from checklists whose every item cites a section that was read: `brown-act-check`, `cpra-intake`, `public-works-check`, `arbitration-check`, `fair-hearing-map`. |
| `deadlines/` | A deterministic California civil deadlines helper: court-day and calendar-day counting, motion and summary judgment schedules, service extensions, 2026 and 2027 court holidays. |
| `verified_authorities.json` | The 153 statute and regulation sections the kit cites, with the date each was read. Tests fail if anything cites a section not in this file. |

Requires Python 3.11 or later. The code uses the standard library only; tests use `pytest`.

## Registry

```
cd registry
python3 registry.py check  registry.example.json
python3 registry.py render registry.example.json --out example_output
```

Start from `AI_Tool_Registry_Template.md` (paper) or `registry.blank.json` (data). `example_output/registry.html` shows the rendered page for a fictional firm with three tools, one of which has four flags.

## Eval harness

```
cd eval_harness
python3 -m harness check                     # validate the corpus and answer keys
python3 -m harness prompt lease-01           # the standard prompt plus one document
python3 -m harness score sample_runs/sample_tool_a.json --out sample_runs/scorecards
python3 -m harness compare sample_runs/sample_tool_a.json sample_runs/sample_tool_b.json
```

The corpus is three commercial leases, three skilled nursing and residential care asset purchase agreements, three public works contracts and three executive employment agreements, 6,200 to 9,500 words each, with 6 to 9 planted defects per document (90 in all) and one near miss per document that looks wrong but is not. `corpus/DEFECT_CATALOG.md` lists each rule and its source.

How the three measures work:

- **Issue recall.** A planted defect counts as found when a finding quotes the defective clause word for word, or, for a missing clause, cites the right section. High-severity recall is reported separately. A reviewer can override any match in the run file.
- **Quote grounding.** The share of quotes that appear in the document word for word. Only whitespace, curly quotes, dashes and a bracketed ellipsis are forgiven.
- **Net time saved.** A model, not a measurement: unaided review time minus setup, tool run time, time to verify each finding, a read-through, and the review left over for what the tool missed. The assumptions are in `harness/config.py` and can be replaced with `--config`. If a run records measured verification minutes, those are used instead.

To test a real tool, give it the output of `harness prompt DOC_ID` for each document, save its JSON answers in a run file shaped like the samples, and score it. `PROMPT.md` has the details.

The two sample runs are made-up output generated from the answer keys by `make_sample_runs.py`. They are not results from any product. A pass on this corpus says nothing about real matters: the documents are synthetic and the keys cover only the planted defects.

## Copilot agent pack

```
cd copilot_agents
python3 build_agents.py --zip
```

Each checklist in `checklists/` is a JSON file of items with the authority for each. The build script turns each one into `agents/<id>/` (declarative agent manifest v1.9, app manifest, instructions, icons) and a zip in `dist/`. The instructions tell the agent to work only from the document it is given, quote the text behind each answer, mark each item Met, Not met, Not stated or Needs attorney judgment, leave deadline arithmetic to a calculator, and say that an attorney must verify every item.

The packages pass local structure tests (schema fields, length limits, every authority in the register). They have not been loaded into a Microsoft 365 tenant, so behavior in Copilot is untested.

## Deadlines helper

```
cd deadlines
python3 -m ca_deadlines motion  --hearing 2026-12-04 --service mail
python3 -m ca_deadlines msj     --hearing 2027-03-12 --service electronic
python3 -m ca_deadlines respond --served 2026-11-02 --rule demurrer --service mail
python3 -m ca_deadlines holidays --year 2027
```

Every result lists each step with the section it rests on, names any holiday or weekend skipped, and gives a "safe date" where the statute can be read two ways. Holidays for 2026 and 2027 come from the Judicial Council's published schedules. Other years are computed from Code Civ. Proc. § 135 and Gov. Code § 6700 and flagged as computed.

It covers a handful of rules (Code Civ. Proc. §§ 12, 12a, 12c, 1005(b), 1010.6, 1013, 437c and four response deadlines). It does not know local rules, department-specific orders, stipulations or tolling. Check every date against the statute and the court's calendar.

## Tests

```
(cd deadlines && python3 -m pytest -q)        # 23
(cd copilot_agents && python3 -m pytest -q)   # 23
(cd eval_harness && python3 -m pytest -q)     # 52
(cd registry && python3 -m pytest -q)         # 7
```

## Limits

- The statute reading was done by an AI assistant. It confirms that a section exists and says what the checklist says. It is not an opinion on how the law applies, and it does not cover case law.
- The corpus documents were drafted by an AI assistant to carry specific planted defects. They are test fixtures, not forms.
- One holiday needs a second look: the published 2027 schedule puts Farmworkers Day on Friday, April 9, 2027. See `CORRECTIONS.md`.
