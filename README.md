# legal-tools-lab

Personal portfolio demos of legal tools. Fictional data only. Not legal advice; not reviewed by an attorney.

## Tools

- [pension-mfn-engine/](pension-mfn-engine/): public-pension side-letter statutory gate and MFN election engine (report Tool 9). Python, synthetic data.
- [prop218-tabulator/](prop218-tabulator/) — Prop 218 written-protest tabulator and AB 2257 objection gate (Python, fictional data).
- [brown-act-cpra-desk/](brown-act-cpra-desk/): Brown Act agenda checks and a CPRA records desk with verified PDF redaction (report Tool 6). Python, fictional data.
- [buy-america-auditor](buy-america-auditor/): checks a transit bill of materials against FTA Buy America (49 CFR Part 661) and BABA (2 CFR Part 184). Synthetic data.
- [ipd-seismic/](ipd-seismic/): IFOA risk/reward pool ledger checker and waterfall, plus a hospital seismic deadline tracker (report Tool 4). Python, live-formula workbook, fictional data.
- [sb706-validator/](sb706-validator/): checks a progressive design-build procurement record against SB 706, Pub. Cont. Code §§ 22185–22185.11 (report Tool 5). Node, no dependencies, fictional data.
- [prop65-intel/](prop65-intel/): Prop 65 sixty-day notice benchmarks from public Attorney General data, deterministic triage, and a record-cite checker (report Tool 12). Python; public OAG data plus synthetic documents.
- [governance-eval-kit/](governance-eval-kit/): AI Tool Registry template, eval harness with a 12-document synthetic California corpus, five Copilot checklist agent packages, and a California court-deadlines helper (report Days 1–30). Python, fictional data.
- [ceqa-density/](ceqa-density/): CEQA record-of-proceedings compiler (Pub. Resources Code § 21167.6 after SB 131) and density bonus calculator for Gov. Code § 65915, SB 4 and AB 130 (report Tool 10). Python, live-formula workbook, fictional data.
- [filing-verification-kit/](filing-verification-kit/): draft filing verification standard, pre-filing checklist, per-filing verification record and hash-chained ledger, judge AI-order lookup, and draft court-disclosure wording for SB 574 (strategy initiative G1). Takes the citation checker's report as input. Python, fictional data.
- [matter-ai-clearance/](matter-ai-clearance/): intake check that reads client AI terms, health-data flags and protective-order fields and says which tool features a matter may use (G3, G4). Every rule is a configurable policy default, not a statement of law. Python, fictional data.
- [adoption-baseline/](adoption-baseline/): short usage survey plus an analyzer that turns assistant usage exports and a roster into a baseline report by practice, role and office, with small-group suppression (A1). Python, synthetic data.
- [catch-the-error-drill/](catch-the-error-drill/): browser training exercise built from the governance-eval-kit documents with planted errors; trainees mark what is wrong and see what they missed (A2). Static HTML and JS, fictional documents.
- [billing-guideline-check/](billing-guideline-check/): checks a draft bill against a client's billing rules before it goes out and reports the amount at risk (R2). LEDES-style reader written from memory and not checked against the published specification. Python, fictional data.
- [client-ai-statement/](client-ai-statement/): builds a one-page client statement on AI use from the tool registry and omits or weakens any sentence the registry does not support; a drift check re-tests an issued statement (S4). Python, fictional data.
- [knowledge-experience-search/](knowledge-experience-search/): keyword search for prior work and for who has done similar work, run as a named user with ethical walls enforced inside the query (A4). No real document system connected. Python and SQLite, synthetic data.
- [fee-modeler/](fee-modeler/): fixed and capped fee scenarios from comparable past matters, with a walk-forward back-test that reports how often past matters overran each band (R5). Python, synthetic data.
- [proposal-desk/](proposal-desk/): turns a public-agency request for proposals into a compliance matrix and a first draft assembled from approved past answers, with consent and wrong-agency checks (R4). Python, synthetic data.
