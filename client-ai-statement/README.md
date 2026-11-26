# Client AI-use statement generator

Personal portfolio demo. Fictional data only. Not legal advice. Not reviewed by an attorney.

The firm, clients, tools, providers and scores in the sample data are invented ("Example Firm LLP (fictional)").

## What it does

It writes a one-page statement for clients and proposals: what AI tools the firm uses, how it checks them, how it bills for AI-assisted work, and how a client can set its own terms.

A statement written by hand can claim things the firm cannot back up. This one is built from the firm's AI tool registry (the format in `../governance-eval-kit/registry/`). Each sentence is a claim with an evidence rule. If the registry does not support a sentence, the generator prints a weaker true wording, or leaves the sentence out. It does not print it.

| Piece | Where | What it does |
| --- | --- | --- |
| Claim library | `data/claims.json` | Each sentence, its wording variants (strongest first) and the registry fields that must hold for each. Rules are data, not code. |
| DRAFT options | `data/draft_options.json` | Wording choices for points a lawyer must decide: billing, confidentiality commitment, court disclosure, opt-out, client precedence. |
| Evidence engine | `statement/evidence.py` | Evaluates a rule against the registry: SUPPORTED, NOT SUPPORTED (with the entries and fields that break it) or CANNOT TELL (field missing or recorded as unknown). Only SUPPORTED prints. |
| Builder | `statement/build.py` | Assembles the fixed sections, applies fallbacks, enforces the word ceiling and the banned-words check. |
| Evidence appendix | `appendix.html`, `appendix.md` | Internal page for the General Counsel: every printed sentence with the registry values behind it, every downgraded claim, every omitted claim and why. |
| Drift check | `python -m statement check` | Re-checks an issued statement against the current registry. Exit code 1 if a printed sentence is no longer supported. |

## Run it

```
python3 run_demo.py
```

This writes every sample output into `output/`. Python 3 standard library only; no network. If Node with Playwright and Chromium is installed, it also writes `statement.png` and `statement.pdf` for each statement and stops if a PDF is not exactly one page. Without Node that step is skipped.

Individual commands (run from this folder):

```
python3 -m statement build --registry samples/registry.clean.json --inputs samples/statement_inputs.json \
    --as-of 2026-11-25 --out output
python3 -m statement build --registry samples/registry.clean.json --inputs samples/statement_inputs.json \
    --client samples/client_terms.consent.json --as-of 2026-11-25 --out output/client-consent
python3 -m statement check --statement output/statement.json --registry samples/registry.later.json --as-of 2027-05-20
python3 -m statement appendix --statement output/statement.json --out output
```

`build` writes `statement.html`, `statement.md`, `statement.json`, `proposal.md`, `appendix.html` and `appendix.md`. Exit codes: 0 ok, 1 drift found (`check` only), 2 bad input or the build was refused.

`--as-of` is required. Dates are compared with that date, never the system clock.

## Sample outputs

| Folder | Input | What to look at |
| --- | --- | --- |
| `output/` | `registry.clean.json` | Firm-wide statement. Every claim prints in its strongest wording. DRAFT watermark because nothing is approved. |
| `output/gaps/` | `registry.gaps.json` | Eight claims downgraded to counts ("Three of four tools..."), three omitted. The appendix says which entry and field caused each. |
| `output/client-consent/` | clean registry + `client_terms.consent.json` | Client-specific version with a "For your matters" section. |
| `output/client-restricted/` | clean registry + `client_terms.restricted.json` | Client restricts two tools; only one has a client-terms check in the registry, so that claim is downgraded. |
| `output/approved-example/` | clean registry + a fictional approval record | The page without the DRAFT watermark. The sign-off is invented for the demo. |
| `output/drift/` | clean statement vs. `registry.later.json` | Two printed sentences are no longer true: one tool's provider terms now allow training on inputs, and one tool's review lapsed. |

## How a claim is decided

A claim in `data/claims.json`:

```json
{
  "id": "no_training",
  "variants": [
    {"id": "all_tools",
     "text": "No tool we use allows what we enter to be used to train a model.",
     "rule": {"scope": ["in_use"], "quantifier": "all", "require": [
       {"field": "data_boundary.used_for_training", "op": "eq", "value": "no", "unknown_values": ["unknown"]}]}},
    {"id": "client_conf_tools", "text": "No tool approved for client confidential information allows ...", "rule": {}},
    {"id": "count", "text": "{Pass} of {scope} tools approved for client confidential information {do} not allow ...", "rule": {}}
  ]
}
```

- `scope` names which registry entries the claim is about. "In use" means status `pilot` or `production`. Proposed, paused and retired tools are outside every claim.
- `quantifier` is `all`, `none` or `at_least`. An `all` rule with nothing in scope is NOT SUPPORTED: there is nothing to base the sentence on.
- A missing field, a null, a value listed in `unknown_values`, or a date after the as-of date gives CANNOT TELL. CANNOT TELL does not print.
- The builder prints the first variant that is SUPPORTED. If that is not the first variant, the claim is listed as downgraded in the appendix with the reason the stronger wording failed.
- A rule can also read the registry header, the statement inputs or the client-terms record (`{"context": [...]}`), and rules can be combined with `all_of`.

## Statement inputs (what the registry schema has no field for)

`samples/statement_inputs.json`:

| Field | Meaning |
| --- | --- |
| `version` | Version label printed in the footer. |
| `name_vendors` | `false` prints tool categories only. `true` adds a sentence naming each tool. |
| `tool_categories` | Per registry tool id: `category` and `use`, the client-facing labels. The appendix prints them beside the registry's own `purpose` text so a reviewer can compare. |
| `contact` | `role` and `channel`. A role, not a person. |
| `opt_out_role` | Who a client writes to. |
| `draft_options` | One option id per topic from `data/draft_options.json`. A billing option is required. |
| `approval` | `approved_by`, `approved_on`, `content_hash`. See below. |
| `exclude_claims` | Claim ids the firm chooses not to print. Listed in the appendix. |

## DRAFT and approval

Every statement is watermarked DRAFT until the approval record is complete: `approved_by`, `approved_on`, and `content_hash` equal to the hash shown in the evidence appendix for that exact text. The hash covers every printed sentence and the footer. If the registry changes and a sentence changes with it, the hash no longer matches and the statement goes back to DRAFT.

This is one step stricter than "fill in two fields": an approval cannot carry over to text the approver did not see.

## Client-terms record

`samples/client_terms.consent.json` and `samples/client_terms.restricted.json`:

| Field | Required | Values |
| --- | --- | --- |
| `client_ref` | yes | How the client is named on the page. |
| `terms_source` | yes | Where the terms come from, for example "Outside Counsel Guidelines, section 9". |
| `terms_date` | yes | Date of those terms (YYYY-MM-DD). |
| `ai_use` | yes | `permitted`, `permitted_with_consent` or `prohibited`. |
| `consent_on_file` | no | `null`, or `{"date": "YYYY-MM-DD", "note": "..."}`. |
| `disclosure_required` | no | `true` or `false`. |
| `disclosure_method` | if disclosure is required | `matter_start_notice`, `invoice_narrative` or `on_request`. |
| `tools_prohibited` | no | Registry tool ids. An id that is not in the registry is an error. |
| `data_restrictions` | no | Any of `client_confidential`, `personal_data`, `health_information`. |
| `notes` | no | Not printed. |

The client version adds a "For your matters" section first. It restates the client's terms from this record, and adds registry-backed sentences about the tools those terms restrict. The restricted set is: every tool in use if AI use is prohibited or consent is required and none is on file; otherwise the tools the client names plus any tool approved for a data type the client bars.

## Length

The page has a fixed type size. `WORD_LIMIT` in `statement/build.py` is 620 words (title, labels, sentences and footer). Above it the build fails with a message; it does not shrink the type. A test pads a statement to exactly 620 words and confirms the PDF is one page.

The proposal paragraph targets about 120 words and has a ceiling of 135.

## Banned words

`data/banned_words.json` has three lists. Hype words ("cutting-edge", "leverage", "revolutionary", "robust" and others) and vague words ("appropriate", "where possible", "reasonable" and others) fail the build anywhere. Absolute words ("never", "always", "guarantee", "fully secure", "every", "each", "all", "none", "no tool") are allowed only in a sentence whose evidence rule covers every entry in scope and is SUPPORTED.

## What is tested

`python3 -m pytest` runs 91 tests:

- Evidence engine: all three statuses, the exact entry and field reported, scope handling, unknown versus contradicted values, date boundaries at the day, dates after the as-of date, empty scopes, malformed rules.
- Builder: section order, strongest-variant selection, each downgrade and omission on the gaps registry, unsupported wording absent from every output, grammar in count sentences, vendor naming, required billing option, a draft option the registry cannot back, approval and its lapse when text changes, the word ceiling, client variants, input validation.
- Banned words across all generated text and across the libraries.
- Appendix: marked internal, lists every printed sentence, shows registry values, explains each downgrade and omission.
- Drift: no drift on the source registry; exactly two broken claims on the later registry; drift from time passing alone; a new tool that trains on inputs; changed counts; exit codes.
- Page: PDF rendered with Chromium is exactly one page for the samples and for a statement padded to the word ceiling. These tests skip if Node or Playwright is missing.
- Sample registries validate against the registry schema; the schema copy in `data/` is byte-identical to the kit's.

## What is NOT done

- No lawyer has reviewed any wording. Every option in `data/draft_options.json` is a draft, and `OPEN_QUESTIONS.md` lists what the General Counsel would need to decide.
- The tool does not know what any law, court rule or ethics rule requires and does not say. The statement describes the firm's own practices only.
- A SUPPORTED claim means the registry says so. The tool cannot tell whether the registry is right. A wrong registry gives a wrong statement with a tidy appendix.
- Several registry fields are free text (`human_review`, `agreements`, the citation verification `mechanism`). The rules only check that they are filled in (and, for the mechanism, that it does not start with "none", the same test the kit uses). Whether the text describes a real control is for the reviewer; the appendix prints the text.
- Tool categories and uses come from the statement inputs, not the registry, because the schema has no such field.
- The registry holds the date of the last review, not a schedule. "Reviewed every 180 days" is printed as what the evidence shows: the interval the registry sets, and a review on record inside it for each tool.
- The client-terms record is typed by hand. Nothing reads a client's outside counsel guidelines.
- The registry's client-terms check is recorded per tool, not per client. The client version can say a tool has a check; it cannot prove that the check holds this client's terms.
- Policy sentences from the DRAFT options (billing, opt-out and the others) have no registry rule. The drift check lists them as NOT CHECKED.
- The drift check is a command, not a scheduled job, and it does not notify anyone.
- No Word output. HTML, Markdown, JSON, and PDF/PNG through Chromium.
- One language, US Letter only.
