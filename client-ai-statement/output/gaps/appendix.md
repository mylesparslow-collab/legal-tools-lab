# Evidence appendix

**INTERNAL. Not for clients. For General Counsel review before the statement is approved.**

Statement: Example Firm LLP (fictional). Statement for clients and proposals. As of 2026-11-25, version 1.0. Registry dated 2026-11-25 (sha256 1830ff529d6f). 374 of 620 words.

Status: DRAFT. The statement and proposal paragraph are watermarked DRAFT.
To approve this exact text, set approval.approved_by, approval.approved_on and approval.content_hash in the statement inputs, then rebuild. Any change to the printed text changes the hash and returns the statement to DRAFT.
Content hash of this text: ea20000b1864e8bcc3f99cc880451d2012b841b502aa51b0ed4ed5d8e4a8bcfe

## Warnings

- Tool 'public-records-search' is in use but has no category in the statement inputs; the statement cannot list tool categories.

## 1. Printed sentences and the evidence behind each

1. **We use five AI-assisted tools in client work.**
   - Section: What we use. Claim: `tools_in_use / count_only`.
   - Registry: 5 of 5 entries in scope meet the rule. In scope: contract-review, intake-assistant, email-drafting, brief-drafting, public-records-search
2. **Three are in firmwide use and two are in a limited pilot.**
   - Section: What we use. Claim: `rollout / split`.
   - Registry: 5 of 5 entries in scope meet the rule. In scope: contract-review, intake-assistant, email-drafting, brief-drafting, public-records-search
3. **Four of five tools in use have a named owner at the firm.**
   - Section: What we use. Claim: `named_owner / count`.
   - Registry: 4 of 5 entries in scope meet the rule. contract-review: business_owner = 'Partner, Corporate Group (role; fictional)' | intake-assistant: business_owner = 'Director of Client Intake (role; fictional)' | email-drafting: business_owner = 'To be assigned' | brief-drafting: business_owner = 'Partner, Litigation Group (role; fictional)' | public-records-search: business_owner = 'Research Services Manager (role; fictional)'
4. **One of five tools in use is not approved to receive client confidential information.**
   - Section: What we use it for, and what we do not. Claim: `not_for_client_information / count`.
   - Registry: 1 of 5 entries in scope meet the rule. contract-review: data_boundary.data_allowed = ["firm_internal", "client_confidential", "personal_data"] | intake-assistant: data_boundary.data_allowed = ["firm_internal", "client_confidential", "health_information"] | email-drafting: data_boundary.data_allowed = ["firm_internal", "client_confidential"] | brief-drafting: data_boundary.data_allowed = ["public", "firm_internal", "client_confidential"] | public-records-search: data_boundary.data_allowed = ["public"]
5. **Three of four tools approved for client confidential information do not allow what we enter to be used to train a model.**
   - Section: How your information is protected. Claim: `no_training / count`.
   - Registry: 3 of 4 entries in scope meet the rule. contract-review: data_boundary.used_for_training = 'no' | intake-assistant: data_boundary.used_for_training = 'unknown' | email-drafting: data_boundary.used_for_training = 'no' | brief-drafting: data_boundary.used_for_training = 'no'
6. **Three of four tools approved for client confidential information are covered by a written agreement with the provider, recorded in our tool registry.**
   - Section: How your information is protected. Claim: `provider_agreements / count`.
   - Registry: 3 of 4 entries in scope meet the rule. contract-review: data_boundary.agreements = ["Data protection addendum with Fictional Provider A, signed 2026-02-10"] | intake-assistant: data_boundary.agreements = null | email-drafting: data_boundary.agreements = ["Standard terms with Fictional Provider F"] | brief-drafting: data_boundary.agreements = ["Master services agreement with Fictional Provider G, signed 2025-06-01"]
7. **Four of five tools in use have a written review step: a person at the firm reviews the tool's output before anyone relies on it.**
   - Section: How work is checked. Claim: `human_review / count`.
   - Registry: 4 of 5 entries in scope meet the rule. contract-review: human_review = 'The responsible attorney reviews every flagged and unflagged clause before the review is relied on.' | intake-assistant: human_review = 'Intake staff review each summary before the conflicts team relies on it.' | email-drafting: human_review = null | brief-drafting: human_review = 'The drafting attorney reviews each draft section.' | public-records-search: human_review = 'A researcher opens each result in the source before reporting it.'
8. **We test tools against a fixed set of documents with known answers. Every tool in firmwide use that this test applies to has a passing result on record.**
   - Section: How work is checked. Claim: `testing / every_firmwide`.
   - Registry: 3 of 3 entries in scope meet the rule. contract-review: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2026-09-15' | intake-assistant: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2026-07-08' | brief-drafting: golden_set.status = 'scored', golden_set.passes = true, golden_set.run_date = '2025-08-20'
9. **Four of five tools in use have a review on record within the past 12 months.**
   - Section: How work is checked. Claim: `review_cycle / count`.
   - Registry: 4 of 5 entries in scope meet the rule. contract-review: last_review = '2026-10-28' | intake-assistant: last_review = '2026-08-14' | email-drafting: last_review = '2026-10-30' | brief-drafting: last_review = '2025-09-12' | public-records-search: last_review = '2026-11-02'
10. **We tell you before we use one of these tools to draft part of a court filing in your matter.**
   - Section: How work is checked. Claim: `court_disclosure / D1`.
   - DRAFT option D1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
11. **We bill for the time our lawyers and staff spend, including time spent reviewing and correcting tool output. We do not bill for time a tool saved, and we do not add a separate charge for the tools described here.**
   - Section: How we bill for AI-assisted work. Claim: `billing / B1`.
   - DRAFT option B1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
12. **Three of four tools approved for client confidential information have a check against the client's written terms on AI before use on a matter.**
   - Section: Your terms and opting out. Claim: `client_terms_check / count`.
   - Registry: 3 of 4 entries in scope meet the rule. contract-review: ocg_check.method = 'automated_gate' | intake-assistant: ocg_check.method = 'manual_lookup' | email-drafting: ocg_check.method = 'manual_lookup' | brief-drafting: ocg_check.method = 'none'
13. **You can tell us not to use these tools on your matters, or set conditions on their use. Write to your relationship partner or the Office of General Counsel. We record your instruction in the matter intake record and apply it to work done after we confirm receipt.**
   - Section: Your terms and opting out. Claim: `opt_out / O1`.
   - DRAFT option O1. Policy wording chosen in the statement inputs. No registry evidence. Needs General Counsel approval.
14. **Questions about this statement go to the Office of General Counsel: aiquestions@examplefirm.example.**
   - Section: Who to contact. Claim: `contact / role`.
   - Not registry evidence. Taken from the statement inputs or the client-terms record; confirm by hand. (inputs): inputs.contact.role = 'the Office of General Counsel', inputs.contact.channel = 'aiquestions@examplefirm.example'

## 2. Downgraded claims (a weaker wording was printed)

- `tools_in_use` printed as: **We use five AI-assisted tools in client work.**
  - Not used (`by_category`): "We use {tools_in_use_phrase} in client work: {category_list}." NOT SUPPORTED. public-records-search: id must have an entry in inputs.tool_categories; found 'public-records-search'
- `named_owner` printed as: **Four of five tools in use have a named owner at the firm.**
  - Not used (`each`): "Each tool has a named owner at the firm who answers for it." NOT SUPPORTED. email-drafting: business_owner must not be one of ['to be assigned', 'tbd', 'none', 'unassigned', 'unknown']; found 'To be assigned'
- `no_training` printed as: **Three of four tools approved for client confidential information do not allow what we enter to be used to train a model.**
  - Not used (`all_tools`): "No tool we use allows what we enter to be used to train a model." CANNOT TELL. intake-assistant: data_boundary.used_for_training must be 'no'; cannot tell (recorded as 'unknown')
  - Not used (`client_conf_tools`): "No tool approved for client confidential information allows what we enter to be used to train a model." CANNOT TELL. intake-assistant: data_boundary.used_for_training must be 'no'; cannot tell (recorded as 'unknown')
- `provider_agreements` printed as: **Three of four tools approved for client confidential information are covered by a written agreement with the provider, recorded in our tool registry.**
  - Not used (`each`): "Each tool approved for client confidential information is covered by a written agreement with its provider, recorded in our tool registry." CANNOT TELL. intake-assistant: data_boundary.agreements must be filled in; cannot tell (field is missing or empty in the record)
- `human_review` printed as: **Four of five tools in use have a written review step: a person at the firm reviews the tool's output before anyone relies on it.**
  - Not used (`every`): "Every tool in use has a written review step: a person at the firm reviews the tool's output before anyone relies on it." CANNOT TELL. email-drafting: human_review must be filled in; cannot tell (field is missing or empty in the record)
- `testing` printed as: **We test tools against a fixed set of documents with known answers. Every tool in firmwide use that this test applies to has a passing result on record.**
  - Not used (`every_in_use`): "We test tools against a fixed set of documents with known answers. Every tool in use that this test applies to has a passing result on record." NOT SUPPORTED. email-drafting: golden_set.status must be 'scored'; found 'not_run' | email-drafting: golden_set.passes must be True; cannot tell (field is missing or empty in the record) | email-drafting: golden_set.run_date must be a date on or before the as-of date; cannot tell (field is missing or empty in the record)
- `review_cycle` printed as: **Four of five tools in use have a review on record within the past 12 months.**
  - Not used (`registry_interval`): "We review tools every {review_interval_days} days. Each tool in use has a review on record within that period." NOT SUPPORTED. brief-drafting: last_review must be a date no more than 180 days before the as-of date; found '2025-09-12' (439 days before the as-of date 2026-11-25)
  - Not used (`annual`): "Each tool in use has a review on record within the past 12 months." NOT SUPPORTED. brief-drafting: last_review must be a date no more than 365 days before the as-of date; found '2025-09-12' (439 days before the as-of date 2026-11-25)
- `client_terms_check` printed as: **Three of four tools approved for client confidential information have a check against the client's written terms on AI before use on a matter.**
  - Not used (`each_recent`): "Before a tool is used on a matter, we check that client's written terms on AI. Each tool approved for client confidential information has this check, and each check was confirmed to work in the past {ocg_check_max_age_days} days." NOT SUPPORTED. intake-assistant: ocg_check.last_checked must be a date no more than 90 days before the as-of date; found '2026-05-02' (207 days before the as-of date 2026-11-25) | brief-drafting: ocg_check.method must be one of ['automated_gate', 'manual_lookup']; found 'none' | brief-drafting: ocg_check.last_checked must be a date no more than 90 days before the as-of date; cannot tell (field is missing or empty in the record)
  - Not used (`each`): "Before a tool is used on a matter, we check that client's written terms on AI. Each tool approved for client confidential information has this check." NOT SUPPORTED. brief-drafting: ocg_check.method must be one of ['automated_gate', 'manual_lookup']; found 'none'

## 3. Omitted claims (no wording is supported)

- `uses`
  - `listed`: "We use these tools for: {use_list}." NOT SUPPORTED. public-records-search: id must have an entry in inputs.tool_categories; found 'public-records-search'
- `no_sensitive_data`
  - `personal_and_health`: "No tool in use is approved to receive personal data or health information." NOT SUPPORTED. contract-review: data_boundary.data_allowed must include none of ['personal_data', 'health_information']; found ["firm_internal", "client_confidential", "personal_data"] | intake-assistant: data_boundary.data_allowed must include none of ['personal_data', 'health_information']; found ["firm_internal", "client_confidential", "health_information"]
  - `health_only`: "No tool in use is approved to receive health information." NOT SUPPORTED. intake-assistant: data_boundary.data_allowed must include none of ['health_information']; found ["firm_internal", "client_confidential", "health_information"]
- `court_citations`
  - `each`: "For each tool whose output may reach a court filing, we have a written step for an attorney to verify citations before filing and a set place where that verification is logged." NOT SUPPORTED. brief-drafting: sb574_log.mechanism must not start with 'none'; found 'None yet' | brief-drafting: sb574_log.log_location must be filled in; cannot tell (field is missing or empty in the record)
  - `count`: "{Pass} of {scope} tools whose output may reach a court filing {have} a written step for an attorney to verify citations before filing and a set place where that verification is logged." NOT SUPPORTED. brief-drafting: sb574_log.mechanism must not start with 'none'; found 'None yet' | brief-drafting: sb574_log.log_location must be filled in; cannot tell (field is missing or empty in the record) | 0 of 1 entries in scope meet the rule; at least 1 needed.

## 4. Claims that do not apply or were excluded

- `no_tools_in_use`: Applies only when the registry has no tool in use.
- `tool_names`: does not apply: inputs.name_vendors must be True
- `no_court_use`: Applies only when no tool in use can reach a court filing.

## 5. DRAFT options chosen (lawyer decisions)

- confidentiality: option C0 (Say nothing beyond the registry facts). Prints nothing.
- court_disclosure: option D1 (Tell the client first)
- billing: option B1 (Time spent, no tool charge)
- opt_out: option O1 (Opt out or set conditions, recorded at intake)

## 6. Tool categories and uses to confirm against the registry

The registry schema has no category field. These labels come from the statement inputs.

| Tool id | Status | Category printed | Use printed | Registry purpose |
| --- | --- | --- | --- | --- |
| contract-review | production | Contract review | first-pass review of contracts against our clause checklist | First-pass review of commercial contracts against the firm's clause checklist. |
| intake-assistant | production | Matter intake | sorting new-matter intake forms | Sorts new-matter intake forms and drafts conflict-check summaries. |
| email-drafting | pilot | Correspondence drafting | first drafts of routine correspondence | First drafts of routine client correspondence. |
| brief-drafting | production | Brief drafting | first drafts of motion and brief sections | Drafts sections of motions and briefs. |
| public-records-search | pilot | MISSING | MISSING | Searches public dockets and public agency records. |

## 7. Proposal paragraph

We use five AI-assisted tools in client work. Three of four tools approved for client confidential information do not allow what we enter to be used to train a model. Four of five tools in use have a written review step: a person at the firm reviews the tool's output before anyone relies on it. Every tool in firmwide use that our known-answer test applies to has a passing result on record. We bill for the time our people spend, not for time a tool saved, and add no separate charge for the tools. Three of four tools approved for client confidential information have a check against the client's written terms on AI before use on a matter. Our one-page statement dated 2026-11-25 gives the detail.

126 words. Sentences: `tools_in_use`, `no_training`, `human_review`, `testing`, `billing`, `client_terms_check`, `(closing)`.
