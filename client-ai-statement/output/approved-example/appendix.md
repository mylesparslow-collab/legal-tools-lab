# Evidence appendix

**INTERNAL. Not for clients. For General Counsel review before the statement is approved.**

Statement: Example Firm LLP (fictional). Statement for clients and proposals. As of 2026-11-25, version 1.0. Registry dated 2026-11-25 (sha256 6e9230a7d522). 483 of 620 words.

Status: APPROVED by General Counsel (role; fictional sign-off for the demo) on 2026-11-25.
Approved content hash: a170aba04792c22317494717fd63b4e34d78020557aad73a99e5cba20202983c

## Warnings

None.

## 1. Printed sentences and the evidence behind each

1. **We use four AI-assisted tools in client work: contract review, legal research and drafting, transcript summaries and translation.**
   - Section: What we use. Claim: `tools_in_use / by_category`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: id = 'contract-review' | research-drafting: id = 'research-drafting' | transcript-summary: id = 'transcript-summary' | translation: id = 'translation'
2. **Two are in firmwide use and two are in a limited pilot.**
   - Section: What we use. Claim: `rollout / split`.
   - Registry: 4 of 4 entries in scope meet the rule. In scope: contract-review, research-drafting, transcript-summary, translation
3. **Each tool has a named owner at the firm who answers for it.**
   - Section: What we use. Claim: `named_owner / each`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: business_owner = 'Partner, Corporate Group (role; fictional)' | research-drafting: business_owner = 'Partner, Litigation Group (role; fictional)' | transcript-summary: business_owner = 'Senior Counsel, Litigation Group (role; fictional)' | translation: business_owner = 'Director of Knowledge Management (role; fictional)'
4. **We use these tools for: first-pass review of contracts against our clause checklist; research memos and first drafts of brief sections; summaries of deposition and hearing transcripts; working translations of public and internal documents.**
   - Section: What we use it for, and what we do not. Claim: `uses / listed`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: id = 'contract-review' | research-drafting: id = 'research-drafting' | transcript-summary: id = 'transcript-summary' | translation: id = 'translation'
5. **One of four tools in use is not approved to receive client confidential information.**
   - Section: What we use it for, and what we do not. Claim: `not_for_client_information / count`.
   - Registry: 1 of 4 entries in scope meet the rule. contract-review: data_boundary.data_allowed = ["firm_internal", "client_confidential"] | research-drafting: data_boundary.data_allowed = ["public", "firm_internal", "client_confidential"] | transcript-summary: data_boundary.data_allowed = ["firm_internal", "client_confidential"] | translation: data_boundary.data_allowed = ["public", "firm_internal"]
6. **No tool in use is approved to receive personal data or health information.**
   - Section: What we use it for, and what we do not. Claim: `no_sensitive_data / personal_and_health`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: data_boundary.data_allowed = ["firm_internal", "client_confidential"] | research-drafting: data_boundary.data_allowed = ["public", "firm_internal", "client_confidential"] | transcript-summary: data_boundary.data_allowed = ["firm_internal", "client_confidential"] | translation: data_boundary.data_allowed = ["public", "firm_internal"]
7. **No tool we use allows what we enter to be used to train a model.**
   - Section: How your information is protected. Claim: `no_training / all_tools`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: data_boundary.used_for_training = 'no' | research-drafting: data_boundary.used_for_training = 'no' | transcript-summary: data_boundary.used_for_training = 'no' | translation: data_boundary.used_for_training = 'no'
8. **Each tool approved for client confidential information is covered by a written agreement with its provider, recorded in our tool registry.**
   - Section: How your information is protected. Claim: `provider_agreements / each`.
   - Registry: 3 of 3 entries in scope meet the rule. contract-review: data_boundary.agreements = ["Data protection addendum with Fictional Provider A, signed 2026-02-10"] | research-drafting: data_boundary.agreements = ["Master services agreement with Fictional Provider B, zero-retention schedule, signed 2026-03-04"] | transcript-summary: data_boundary.agreements = ["Data protection addendum with Fictional Provider A, signed 2026-02-10"]
9. **We enter your confidential information only into tools that our registry approves for client confidential information.**
   - Section: How your information is protected. Claim: `confidentiality / C1`.
   - DRAFT option C1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
10. **Every tool in use has a written review step: a person at the firm reviews the tool's output before anyone relies on it.**
   - Section: How work is checked. Claim: `human_review / every`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: human_review = 'The responsible attorney reviews every flagged and unflagged clause before the review is relied on.' | research-drafting: human_review = 'The drafting attorney verifies every proposition and citation; the supervising partner reviews the final draft.' | transcript-summary: human_review = 'An attorney on the matter checks each summary against the transcript before it is circulated.' | translation: human_review = 'A fluent reviewer at the firm checks each translation before it is used.'
11. **We test tools against a fixed set of documents with known answers. Every tool in use that this test applies to has a passing result on record.**
   - Section: How work is checked. Claim: `testing / every_in_use`.
   - Registry: 3 of 3 entries in scope meet the rule. contract-review: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2026-09-15' | research-drafting: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2026-10-02' | transcript-summary: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2026-10-21'
12. **For each tool whose output may reach a court filing, we have a written step for an attorney to verify citations before filing and a set place where that verification is logged.**
   - Section: How work is checked. Claim: `court_citations / each`.
   - Registry: 1 of 1 entries in scope meet the rule. research-drafting: sb574_log.mechanism = 'Filing attorney reads each cited authority in the original source and signs the citation check form before filing.', sb574_log.log_location = "Matter workspace, folder 'Citation checks'"
13. **We review tools every 180 days. Each tool in use has a review on record within that period.**
   - Section: How work is checked. Claim: `review_cycle / registry_interval`.
   - Registry: 4 of 4 entries in scope meet the rule. contract-review: last_review = '2026-10-28' | research-drafting: last_review = '2026-11-10' | transcript-summary: last_review = '2026-11-12' | translation: last_review = '2026-09-30' | (inputs): registry.review_interval_days = 180
14. **We tell you before we use one of these tools to draft part of a court filing in your matter.**
   - Section: How work is checked. Claim: `court_disclosure / D1`.
   - DRAFT option D1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
15. **We bill for the time our lawyers and staff spend, including time spent reviewing and correcting tool output. We do not bill for time a tool saved, and we do not add a separate charge for the tools described here.**
   - Section: How we bill for AI-assisted work. Claim: `billing / B1`.
   - DRAFT option B1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
16. **Before a tool is used on a matter, we check that client's written terms on AI. Each tool approved for client confidential information has this check, and each check was confirmed to work in the past 90 days.**
   - Section: Your terms and opting out. Claim: `client_terms_check / each_recent`.
   - Registry: 3 of 3 entries in scope meet the rule. contract-review: ocg_check.method = 'automated_gate', ocg_check.last_checked = '2026-10-20' | research-drafting: ocg_check.method = 'manual_lookup', ocg_check.last_checked = '2026-11-03' | transcript-summary: ocg_check.method = 'manual_lookup', ocg_check.last_checked = '2026-11-03'
17. **You can tell us not to use these tools on your matters, or set conditions on their use. Write to your relationship partner or the Office of General Counsel. We record your instruction in the matter intake record and apply it to work done after we confirm receipt.**
   - Section: Your terms and opting out. Claim: `opt_out / O1`.
   - DRAFT option O1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
18. **Questions about this statement go to the Office of General Counsel: aiquestions@examplefirm.example.**
   - Section: Who to contact. Claim: `contact / role`.
   - Not registry evidence. Taken from the statement inputs or the client-terms record; confirm by hand. (inputs): inputs.contact.role = 'the Office of General Counsel', inputs.contact.channel = 'aiquestions@examplefirm.example'

## 2. Downgraded claims (a weaker wording was printed)

None.

## 3. Omitted claims (no wording is supported)

None.

## 4. Claims that do not apply or were excluded

- `no_tools_in_use`: Applies only when the registry has no tool in use.
- `tool_names`: does not apply: inputs.name_vendors must be True
- `no_court_use`: Applies only when no tool in use can reach a court filing.

## 5. DRAFT options chosen (lawyer decisions)

- confidentiality: option C1 (Registry-approved tools only)
- court_disclosure: option D1 (Tell the client first)
- billing: option B1 (Time spent, no tool charge)
- opt_out: option O1 (Opt out or set conditions, recorded at intake)

## 6. Tool categories and uses to confirm against the registry

The registry schema has no category field. These labels come from the statement inputs.

| Tool id | Status | Category printed | Use printed | Registry purpose |
| --- | --- | --- | --- | --- |
| contract-review | production | Contract review | first-pass review of contracts against our clause checklist | First-pass review of commercial contracts against the firm's clause checklist. |
| research-drafting | production | Legal research and drafting | research memos and first drafts of brief sections | Research memos and first drafts of brief sections from the firm's licensed research sources. |
| transcript-summary | pilot | Transcript summaries | summaries of deposition and hearing transcripts | Summaries and issue indexes of deposition and hearing transcripts. |
| translation | pilot | Translation | working translations of public and internal documents | Working translations of public and firm-internal documents. |

## 7. Proposal paragraph

We use four AI-assisted tools in client work: contract review, legal research and drafting, transcript summaries and translation. No tool we use allows what we enter to be used to train a model. Every tool has a written review step: a person at the firm reviews its output before anyone relies on it. Every tool in use that our known-answer test applies to has a passing result on record. We bill for the time our people spend, not for time a tool saved, and add no separate charge for the tools. Before a tool is used on a matter, we check that client's written terms on AI. Our one-page statement dated 2026-11-25 gives the detail.

115 words. Sentences: `tools_in_use`, `no_training`, `human_review`, `testing`, `billing`, `client_terms_check`, `(closing)`.
