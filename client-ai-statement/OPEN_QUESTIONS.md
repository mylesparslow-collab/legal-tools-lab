# Open questions for the General Counsel

Personal portfolio demo. Fictional data. Not legal advice. Not reviewed by an attorney.

Nothing in this tool states what any statute, court rule or rule of professional conduct requires. The author could not consult legal sources while building it and did not write law from memory. Each point below needs a lawyer's decision before a statement goes to a client. Until the approval record is complete, every output is watermarked DRAFT.

## A. Wording that needs a decision (from `data/draft_options.json`)

1. **Billing for AI-assisted work.** Options B1, B2 and B3 are drafts. Which, if any, matches the firm's fee agreements and billing practice? Does the answer differ for hourly, fixed-fee and contingent work? Is "we do not bill for time a tool saved" a statement the firm can keep, and how would it be checked? May tool costs be passed through at all, and on what terms? What do the applicable professional conduct rules and any ethics guidance say about fees for AI-assisted work? This tool does not answer that.
2. **Confidentiality commitment.** Options C1 and C2 promise that client confidential information goes only into registry-approved tools. Is the firm willing to make that promise in writing to clients? Is there a control behind it, or only a policy? Should the statement say anything about retention periods, where data is processed, or subcontractors? Do existing engagement letters or client guidelines already set a different standard?
3. **Court filings and disclosure.** Options D1 and D2 are drafts. Should the statement say anything about disclosure to courts? Disclosure and certification requirements differ by court and judge and change over time; this tool knows none of them. Is "we tell you before we use a tool to draft part of a filing" a commitment the litigation group can keep on every matter?
4. **Opt-out.** Options O1 and O2 say a client may refuse or restrict the tools. From what moment does an instruction apply? Who records it, and where? Can every tool in fact be switched off for one client's matters? Is there work the firm would decline or price differently if a client opts out, and should the statement say so?
5. **Client terms and this statement.** Option P1 says stricter client terms govern. Is that the right rule when a client's terms are silent, looser or ambiguous? Should the client version of the statement be treated as part of the engagement terms, or as information only?

## B. Evidence-backed sentences that still need a legal read

6. **Does a registry entry prove the sentence?** A claim prints when the registry fields say so. Is the registry an adequate basis for a statement to clients? Who attests that the registry is accurate on the as-of date?
7. **"Written agreement with its provider."** The registry lists agreement names as free text. Does each listed agreement contain the confidentiality, retention and no-training terms the sentence implies? Should the sentence name the type of agreement?
8. **"Does not allow what we enter to be used to train a model."** The registry holds `used_for_training: no | yes | unknown`. What is the source for each "no": contract term, vendor setting, vendor marketing? Is the wording accurate for provider practices such as abuse monitoring or human review of inputs?
9. **"A person at the firm reviews the tool's output before anyone relies on it."** The rule checks that a review step is written down, not that it happens. Is "has a written review step" the right level of claim?
10. **"A written step for an attorney to verify citations before filing."** Same point. Is there an audit of the citation log? Does the wording meet, fall short of, or overstate what the applicable court rules and professional duties call for? This tool does not know.
11. **Testing.** "Has a passing result on record" depends on the pass mark the firm set. Who set it, and is it defensible if a client asks? The registry does not record when a tool went into firmwide use, so the tool cannot show that testing came first.
12. **Count sentences.** When a universal claim fails, the fallback prints a count ("Three of four tools..."). That tells the client one tool falls short. Is printing the count better than omitting the claim? `exclude_claims` in the statement inputs removes a claim; the appendix records the exclusion.
13. **Pilots.** The statement counts pilot tools as "in use". Is that right for client-facing purposes? Are pilot tools used on live client matters?
14. **Tools that are not generative AI.** The registry does not flag whether a tool uses a generative model. Should rule-based tools be counted in "AI-assisted tools"?

## C. Process

15. **Who approves, and what does approval cover?** The tool treats approval as tied to one exact text (a content hash). Is General Counsel sign-off enough, or do practice group leaders, the firm's insurer or the management committee also need to approve?
16. **Reissue.** If the drift check finds a printed sentence is no longer true, what must the firm do: withdraw, correct, notify clients who received it? Within what time? Does a statement in a proposal create obligations after the engagement starts?
17. **How often to run the drift check.** Monthly, on every registry change, or before each proposal goes out?
18. **Client-specific versions.** Who enters the client-terms record, and who checks it against the client's actual guidelines? Should the client version be sent to the client, or used only inside the firm?
19. **Consent.** Where a client's terms require consent, what counts as consent on file (form, signer, scope)? The record holds a date and a note only.
20. **Naming vendors.** `name_vendors` is off by default. Are there confidentiality terms in vendor agreements that restrict naming them, or client expectations that favor naming them?
21. **Marketing rules.** A statement in a proposal is a communication about the firm's services. Does it need review under the rules that govern such communications? This tool does not address that.
22. **Privilege and the appendix.** The evidence appendix is marked internal. How should it be stored and labeled, and who may see it?
