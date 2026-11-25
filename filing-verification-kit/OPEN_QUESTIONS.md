# Open questions for attorney review

Personal portfolio demo. Not legal advice. Not reviewed by an attorney. The author is not an attorney.

Tags in square brackets are keys into `data/authorities.json`. Each question says what the kit does today, so the answer can be turned into a setting or a change to the standard.

## 1. How should [ccp_128_7_d1] and [ccp_128_7_g] shape the standard?

- [ccp_128_7_d1] limits one kind of sanction against a represented party. Does that change who the standard should name as accountable, what the firm tells clients, or what the record needs to show?
- [ccp_128_7_g] takes discovery papers out of the section. Which document types count as discovery papers for this purpose? In particular, is a discovery motion filed with the court inside or outside the citation rule in [ccp_128_7_b2A]?
- Should the firm apply the full citation steps to discovery papers anyway, as a matter of practice?
- Today: `discovery_mode` is `advisory` (reported, not blocking) for requests, responses and objections. Discovery motions are treated as court filings. Both are settings in `data/policy.json`.

## 2. What does "personally verified" require in practice?

- [ccp_128_7_b2A] puts the duty on the responsible attorney. May any part of the work be done by another attorney, a paralegal or software, with the responsible attorney reviewing the result? If so, what must the responsible attorney do personally?
- Must the attorney read the whole authority, or the cited passage? Is a citator check part of verification? See [no_citator_product].
- Does "any citation" reach citations to the record, exhibits, declarations and secondary sources? The citation checker extracts legal citations only.
- When several attorneys sign, who is "the responsible attorney" for the record?
- What should a sufficient "how checked" entry say? Today: the kit requires who, when and at least a short description, and requires the attestor to be the responsible attorney (`attestor_must_be_responsible_attorney`).
- Today: a not-found citation or a quote mismatch cannot be signed over. Should an attorney note be enough when the checker is wrong? (`allow_attorney_override_not_found`, `allow_attorney_override_quote_mismatch`.)

## 3. What is the scope of the court-disclosure duty?

- [bpc_6068_1_a3C] refers to documents submitted to the court. Which documents are those? Is a paper served but not filed covered? Proposed orders? Exhibits? Letters to chambers?
- What counts as "use" of generative AI: drafting only, or also research, summarising, editing and features built into ordinary software?
- Is any particular wording, placement or level of detail required? Does disclosure have to be in the document itself?
- Is there any case where the firm may decide not to disclose after generative AI was used? Today: the kit allows that decision only with a written reason and a named approver, and keeps it on the record.
- The four draft wordings in `standard/DISCLOSURE_OPTIONS.md` need approval or replacement.
- A separate review of this provision is in progress. This kit should follow its result.

## 4. What are "reasonable steps" for AI output other than citations?

[bpc_6068_1_a3Bi] and [bpc_6068_1_a3Bii] cover AI output generally. The kit records one attorney statement per filing on how the output was reviewed and corrected. Is that enough? Should the record list the AI-drafted passages?

## 5. Protected information

[bpc_6068_1_b2] lists categories of information. The kit does not have the text of the list and does not reproduce it. It records a yes or no answer and, for a yes, a named reviewer. What should the standard require before and after such information is entered into a tool?

## 6. Parts of SB 574 this kit does not cover

[sb574_enactment] lists other sections the bill adds or amends. This kit addresses only the provisions listed in `data/authorities.json`. What do the other sections require of the firm, and do any of them belong in this standard (for example for arbitration or for other tribunals)?

## 7. Judge and court orders on AI

- Who keeps the orders file current, and how often? Today: entries older than 30 days are flagged (`judge_entry_staleness_days`).
- Should a stale or missing entry block a filing (today: yes), or only warn?
- How should federal courts and courts outside California be handled?

## 8. The record itself

- How long is the record kept, and where? Is it protected from disclosure to the other side, or should it be written on the assumption that a court may see it?
- Is a typed name enough for sign-off, or is a signed-in identity or e-signature needed?
- Should the standard apply to filings made before the operative date in [sb574_enactment]? Today: yes, the kit applies it regardless of date.

## 9. Policy defaults that need a decision

Every setting in `data/policy.json` is a default chosen for the demo. None has been approved. The ones most likely to matter: `discovery_mode`, the two override settings, `non_disclosure_needs_approval`, and the list of document types.
