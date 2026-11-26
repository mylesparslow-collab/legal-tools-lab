# Matter clearance for AI

Personal portfolio demo. All clients, matters, lawyers, tools and contract terms are fictional. This is not legal
advice. It has not been reviewed by an attorney, and the author is not an attorney.

Every rule in this tool is a configurable firm policy default kept in `data/policy.json`. None of them is a
statement of law. Where a real legal question sits behind a default, the rule points to `OPEN_QUESTIONS.md`, which
marks it as an attorney decision.

## What it does

At matter intake it answers one question: which AI tools and features may be used on this matter. Three inputs
drive the answer.

1. The client's own AI terms, read from outside counsel guidelines and engagement letters, plus any insurer or
   co-counsel guidelines attached to the matter.
2. The matter's data flags: protected health information (yes, no, unknown) and sealed material.
3. Protective order terms, as entered by the intake team in four coded fields.

It returns one decision for each tool feature (ALLOWED, ALLOWED WITH CONDITIONS, NOT ALLOWED or HOLD FOR REVIEW),
the rule ids and quoted clause spans behind it, and a one-line banner for the matter, for example:

> AI: Suite B documents, Review D allowed with notice to Quenby, billing review, attorney review, PHI use logged,
> consent on file; no PHI in any tool except Suite B documents, Review D

The health-data lane is the second half: a feature may receive protected health information only if the lanes file
lists it for that class, a business associate agreement is confirmed to cover that feature, it does not train on
inputs, connectors and web access are off, and retention is known. `unknown` in any of those counts as no.

Everything else is off by default, and off means off for the matter. On a matter with protected health information,
a feature that is not in the lane is NOT ALLOWED on that matter at all. Nobody is asked to keep health information
out of, say, an email assistant by hand. The same holds for protective-order material and sealed material. See
"Roll-up options" below for the looser opt-in.

## Run it

```
python run_demo.py
```

Python 3 standard library only. No network. This rewrites `output/` and `index.html`. Open `index.html` for four
sample matters, or any memo under `output/memos/`.

```
python -m clearance scan-terms --evaluate                 # scan every terms document, print precision and recall
python -m clearance scan-terms --client tessaly           # one party's documents
python -m clearance scan-terms path/to/terms.txt --json   # any plain-text file
python -m clearance clear --matter M-1008 --as-of 2026-11-25 --out output/memos
python -m clearance clear --matter M-1003 --lanes data/registry_sample.json   # lanes from a registry file
python -m clearance tracker --out output
python -m clearance diff --client quillfether --replace quillfether-ocg-v1-2025 --with quillfether-ocg-v2-2026
python -m pytest -q
```

## Parts

| Part | File | Notes |
|---|---|---|
| Clause tracker | `clearance/clauses.py`, `data/clause_patterns.json` | Keyword and regex patterns, one sentence at a time. No model. Each hit keeps document id, character offsets, exact quote and class. |
| Tool lanes | `clearance/lanes.py`, `data/tool_lanes.json` | Ten fictional features across five fictional tools. Also reads a registry file in the governance-eval-kit format and reports what it could not map. |
| Policy | `data/policy.json` | 36 rules with id, plain text, owner role and review date. Also the decision order, the data classes, the roll-up options and the unknown guard. |
| Engine | `clearance/engine.py` | A small generic evaluator. It contains no rule ids, clause classes or lane field names; a test checks that. |
| Outputs | `clearance/reports.py` | Matter memo (HTML and JSON), client-terms tracker (CSV and HTML), change report (HTML and JSON), demo page. |
| Sample data | `data/clients.json`, `data/terms/`, `data/matters/` | 11 clients, 2 other parties (an insurer, a joint defense group), 20 terms documents, 16 matters. |
| Answer key | `data/answer_key.json` | 91 hand-labeled spans: 59 positive, 32 hard negatives. |

## How a decision is made

- Clause classes: AI prohibited; prior written consent required; disclosure or notice required; no training on
  client data; approved tools only; data residency or retention; billing restriction; human review required; AI
  expressly permitted; ambiguous; silent.
- A sentence is classified only in AI context: it names AI, or its paragraph or section heading does.
- Negation and scope guards stop a match and record why. "Nothing in this section prohibits ..." is not a
  prohibition. "Company employees are prohibited from ..." is not a restriction on the firm.
- Conflicts inside one party's documents (for example a prohibition in the guidelines and a permission in the
  engagement letter) and ambiguous clauses set the status to needs analyst review. The tool does not choose a
  reading and applies no order of precedence between documents. The stricter rule still fires in the meantime, and
  the memo and banner say the terms need review.
- Each rule is evaluated per data class in play on the matter. The most restrictive rule that fires wins, in the
  order NOT ALLOWED, HOLD FOR REVIEW, ALLOWED WITH CONDITIONS, ALLOWED. Sources are layered: client, insurer,
  co-counsel, protective order, firm lanes. A stricter source always wins over a looser one.
- A protective-order restriction is evaluated on its own data class, so client consent cannot clear it. In sample
  matter M-1008 the client consented to two features and the order bars outside vendors: the vendor-hosted one is NOT
  ALLOWED despite the consent, and the firm-hosted one is allowed with the order's conditions.
- Unknown never clears restricted data. Separate from the specific rules, a guard lists the facts each restricted
  class depends on; if any is unknown the result for that class cannot be better than a hold. If intake does not say
  whether a restricted class is present at all, every feature is held.
- Rules past their review date still apply and are flagged in the memo.

### Roll-up options

Each rule gives a result per data class. `rollup.restricted_class_denied` in `data/policy.json` sets how those
results become one decision for the feature.

- `block_feature` (shipped default). If a restricted class is present on the matter and the feature is not allowed
  for it, the feature is NOT ALLOWED on the matter. If that class is on hold for the feature, the feature is on HOLD;
  a hold is never turned into a denial.
- `exclude_class` (opt-in). The feature stays usable for the matter's other material, with a condition such as "Do
  not put protected health information in this feature." This clears more features. What it trades away: the
  restricted data is then kept out only by each person remembering the condition every time they use the tool.
  Nothing in the tool or the software enforces it. `hold_propagates` applies only in this mode: `true` makes a hold
  on one class hold the whole feature instead of excluding the class.

The two modes give identical per-class results; only the feature-level decision differs, and `block_feature` is
never the looser of the two (a test checks both points on every sample matter).

In either mode, if intake does not say whether a restricted class is present at all (PHI unknown, protective order
unknown), features that would otherwise be usable are put on HOLD, not denied. The rules for that class have only
unknown facts to work with, so their result is not treated as a finding about the feature.

Outcome mix across the 16 sample matters and 10 features (160 decisions):

| Mode | Allowed | Allowed with conditions | Hold for review | Not allowed |
|---|---|---|---|---|
| `block_feature` (default) | 7 | 20 | 18 | 115 |
| `exclude_class` | 7 | 35 | 17 | 101 |

Three kinds of analyst record are read from `data/clients.json`, each with who and when. The tool never infers
them: a dismissal of a false hit, a scope note that limits a clause to a data class or to tools off the approved
list, and findings for residency and retention limits.

## What is tested

117 tests, all passing (`python -m pytest -q`).

- Classifier: each guard, the consent-exception case, public-tool scope, staff training against model training,
  heading context, the sentence splitter, offsets reproducing quotes for every hit, silent documents, conflict and
  ambiguity surfacing, analyst dismissals, pattern file validation.
- Answer key: size, offsets, hard negatives; the scorer on a synthetic case; measured precision and recall; the
  committed evaluation equals a fresh run.
- Lanes: validation, registry mapping and unmapped-field report, a registry tool that lists health information is
  still not cleared for PHI, import of the existing kit example.
- Engine: evaluator operators and type strictness, decision order, policy loading, each sample situation,
  insurer and co-counsel layering, protective order over client consent (including blanket consent), both roll-up
  modes set explicitly in the test, a class hold staying a hold under the stricter mode, unknown class status holding
  rather than denying in both modes, default-deny
  for the health-data lane across 11 field values, the guard working with the specific PHI rules deleted, and a sweep
  that sets every guard fact to unknown on every matter and feature (over 500 checks) and requires that restricted
  data is never cleared.
- Outputs and CLI: memo escaping and self-containment, tracker rows, change report flips, every subcommand, error
  exit, committed outputs equal a fresh run, the demo page has four matters and no external references, runtime
  imports are standard library only, every open-question code in the policy exists in `OPEN_QUESTIONS.md`.

## Measured classifier accuracy

The answer key was written before the classifier was run. Documents are split into a development set (12
documents, used to adjust patterns) and a held-out set (8 documents, not looked at while adjusting).

| | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| Overall | 0.947 | 0.915 | 54 | 3 | 5 |
| Development documents | 0.944 | 1.000 | 34 | 2 | 0 |
| Held-out documents | 0.952 | 0.800 | 20 | 1 | 5 |

Two of 32 hard negatives are wrongly classified. `run_demo.py` prints these figures and writes them to
`output/classifier_evaluation.txt`.

Read these numbers with care.

- The same person wrote the documents, the key and the patterns. The held-out split reduces that problem but does
  not remove it. Real guidelines will score lower. Recall of 0.80 on held-out text is the more honest figure.
- First run on the development set: precision 0.909, recall 0.882. One round of general fixes followed (do not let
  "including public chatbots" narrow a prohibition; "let you know"; "not approved by"; "may not be generated by";
  drop "may adopt" as a sign of ambiguity).
- First run on the held-out set: precision 0.909, recall 0.800. One fix was made after seeing it, so the held-out
  precision above is not clean: "does not permit outside counsel to use" had been read as a permission as well as a
  prohibition. That was a missing negation guard, not a tuning choice, and it would have flagged a plain prohibition
  as a conflict. Held-out recall did not change. A later bug fix (apostrophes inside the staff-training guard)
  changed no score.
- No pattern was changed to fix the misses below.

Misses that remain:

| Document | Key label | Text | What happened |
|---|---|---|---|
| quillfether-ocg-v2-2026 | approved tools only | "Approval will list the specific tools cleared for that matter; no other tool may be used." | No pattern for "cleared" or "no other tool". |
| quillfether-ocg-v2-2026 | disclosure required | "Counsel must continue to identify AI-assisted tasks on each invoice." | "continue to" sits between the modal and the verb. Billing class was found. |
| quillfether-ocg-v2-2026 | ambiguous | "Quillfether no longer encourages unsupervised use of AI tools ..." | No pattern for withdrawn encouragement. |
| verdanthe-el-2026 | approved tools only | "Resident records will only be placed in tools that we have confirmed are appropriate ..." | "confirmed are appropriate" is not in the approved-list patterns. |
| ironvale-ocg-2026 | no training | "No Ironvale data may be used to develop or improve any AI vendor's products." | The apostrophe in "vendor's" breaks the word-gap pattern. |

False positives that remain:

| Document | Class given | Text | Effect |
|---|---|---|---|
| tessaly-ocg-2025 | disclosure required | "A request for consent must identify the tool, the vendor ..." | Would add a notice condition. Dismissed by an analyst record in the sample data. |
| tessaly-ocg-2025 | approved tools only | "All attorneys ... must complete the Firm's AI training before using an approved tool." | Would hold the matter for an approved list. Dismissed by an analyst record in the sample data. |
| ironvale-ocg-2026 | approved tools only | "Use of any AI platform not on that list requires advance approval ..." | None; the client already has that class. |

Effect of the misses on decisions: errors of omission make a clearance looser than the terms, which is the dangerous
direction. In the sample set the Quillfether change report lists "disclosure required" as removed in the update when
the new document still asks for invoice identification; the report warns that a removed class may be a miss.

## What is not done

- No legal source was consulted. No statute, rule, opinion or case is cited or paraphrased anywhere. The policy
  defaults are placeholders for decisions listed in `OPEN_QUESTIONS.md`.
- The classifier works on sentences and has no sense of scope. A prohibition on one task ("summaries of privileged
  communications may not be generated by AI") is treated as a prohibition on the whole matter. A consent clause
  about one data type applies to everything until an analyst adds a scope note.
- It does not extract parameters. Retention days, regions and approved tool lists are typed in by an analyst.
- It reads plain text only. No PDF or Word extraction, no tables, no defined-term resolution, no cross-references
  ("as set out in Appendix C").
- It does not read protective orders. Intake enters coded fields and optional quotes; the memo shows those quotes
  without offsets and says so.
- There is no way to record that a conflict or ambiguity has been resolved. The matter stays flagged until the
  documents change. Dismissals and scope notes exist; resolutions do not.
- No order of precedence between a client's documents, and no handling of "this letter controls" clauses.
- Consent records are matched by feature id only. Dates, expiry and matter scope of a consent are not checked.
- Nothing is enforced. The output is a memo and a banner. No integration with intake, document management or any
  AI tool.
- The registry import sets every lane field the registry lacks to unknown, so imported tools are never cleared for
  PHI or protective-order material.
- The sample registry file carries the placeholder fields the existing registry schema requires, including one whose
  name refers to a bill. Nothing here interprets that field; it is reported as unmapped.
- No user interface beyond static HTML. No audit log, no user accounts, no history of past clearances.
- The JSON data files were produced once by throwaway scripts and are meant to be edited by hand from here on.

## Files

```
README.md  OPEN_QUESTIONS.md  run_demo.py  index.html  .gitignore
clearance/   __init__.py __main__.py cli.py clauses.py engine.py lanes.py reports.py store.py
data/        policy.json tool_lanes.json clause_patterns.json clients.json answer_key.json registry_sample.json
data/terms/  20 plain-text terms documents
data/matters/ 16 matter intake files
tests/       conftest.py test_clauses.py test_engine.py test_lanes.py test_outputs.py
output/      classifier_evaluation.{txt,json} clause_hits.json matter_summary.txt client_terms_tracker.{csv,html}
             change_report_quillfether.{json,html} registry_import_report.json memos/M-1001..M-1016.{html,json}
```
