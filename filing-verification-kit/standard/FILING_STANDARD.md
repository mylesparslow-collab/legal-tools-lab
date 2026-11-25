# Filing verification standard (DRAFT)

Status: DRAFT for the General Counsel to edit. Personal portfolio demo. Not legal advice. Not reviewed by an attorney.

How to read this page: a tag in square brackets, such as [ccp_128_7_b2A], is a key into `data/authorities.json`. That file holds the section number, a paraphrase and the date the text was read. It is the only place a statutory paraphrase is kept. Every sentence on this page without a tag is a proposed firm rule, not a statement of law. Open points are in `OPEN_QUESTIONS.md`.

## 1. Purpose

SB 574 is operative on the date given in [sb574_enactment]. A written policy does not show that any one filing was checked. This standard requires a saved record for each filing.

## 2. Scope

- In scope: every paper the firm files in a court, of the kinds described in [ccp_128_7_b2A].
- Discovery papers: see [ccp_128_7_g]. Firm rule (setting `discovery_mode`): citation checks are run and reported for discovery papers but do not block them. The AI-use steps in section 4 still apply to them. Discovery motions are treated as court filings until counsel decides otherwise.
- Any document type not on the firm's list is classified by an attorney before filing.

## 3. Responsible attorney

One attorney is named for each filing: the attorney who signs the paper. That attorney makes the per-citation attestations and signs the record. Staff and software may help find and check authorities. They do not attest. Basis: [ccp_128_7_b2A].

## 4. Before filing

The responsible attorney confirms each of these on the final text of the document.

1. Citation check. The firm's citation checker has been run on the final text and its report matches the document hash.
2. Attestation. For every citation in the report the attorney records who verified it, when, and how. This covers every citation, not only cases and statutes: [ccp_128_7_b2A]. A machine result of "pass" or "found" is not an attestation.
3. Flags. A citation the checker cannot find, or a quotation that does not match its source, is corrected in the document and the check is run again. Other machine warnings need a written note from the attorney.
4. Good law. The attorney checks later history with a citator. This is firm practice. See [no_citator_product].
5. AI use. The record states whether generative AI was used, with which tools and for what. If it was used, the attorney states how its output was verified and corrected: [bpc_6068_1_a3Bi], [bpc_6068_1_a3Bii].
6. Protected information. If generative AI was used, the attorney answers whether information in the categories of [bpc_6068_1_b2] was entered into a tool. A "yes" goes to a named reviewer before filing.
7. Disclosure. If generative AI was used, a disclosure decision is recorded, with the wording chosen: [bpc_6068_1_a3C]. Wording comes from `standard/DISCLOSURE_OPTIONS.md` once approved. A decision not to disclose needs a written reason and a named approver.
8. Judge and court orders. The judge's and court's orders on AI are looked up. An entry older than 30 days is rechecked. No entry means "not checked", never "no order". Any certification, disclosure or prohibition on file is followed and the response recorded.

## 5. Record saved

For each filing the firm keeps: the document SHA-256; the citation list with each attestation; the AI-use answers; the disclosure decision and text; a copy of the judge-order entries relied on; the checklist result; the signer's name, statement and time. The record is written to an append-only, hash-chained ledger. A record covers one exact file. Any edit after sign-off voids it, and the steps in section 4 are repeated.

## 6. Failed check

A filing with a blocking item is not filed. The attorney fixes the cause and runs the checklist again. Every run, pass or fail, is logged. Nobody may sign for the responsible attorney. If a deadline is at risk, the attorney tells the General Counsel before the deadline, not after.

## 7. Exceptions

- Discovery papers, as set out in section 2.
- No other standing exception. A one-off exception needs the General Counsel's written approval, saved with the record. An exception changes firm procedure only; it does not change anything in [ccp_128_7_b2A] or [bpc_6068_1_a3Bi].
- Who bears the risk when a check is skipped is a question for counsel: see [ccp_128_7_d1] and `OPEN_QUESTIONS.md`, question 1.
