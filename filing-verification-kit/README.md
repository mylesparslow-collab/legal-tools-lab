# Filing verification kit

Personal portfolio demo. All data is fictional: the clients, attorneys, judges, courts, cases and orders are invented. Not legal advice. Not reviewed by an attorney. The author is not an attorney.

## What it does

California SB 574 is operative January 1, 2027 (see `sb574_enactment` in `data/authorities.json`). A firm policy on its own does not show that a given filing was checked. This kit is the workflow around a citation checker that already exists: it turns "we have a policy" into one saved record per filing.

1. **Filing standard** (`standard/FILING_STANDARD.md`). A one-page draft for a General Counsel to edit: who is responsible, what is checked, what is saved, what happens on a failed check, exceptions.
2. **Pre-filing checklist** (`filingkit/checklist.py`). Reads a filing descriptor and reports 15 items, each PASS, FAIL, NEEDS ATTENTION or NOT APPLICABLE with a reason. A filing is clear to file only when no blocking item remains.
3. **Verification record** (`filingkit/record.py`, `filingkit/ledger.py`). On sign-off, writes a JSON record and a printable HTML page, and appends to a hash-chained JSONL ledger. Editing the document afterwards makes the record invalid.
4. **Judge AI-order lookup** (`filingkit/judges.py`). Answers "current", "recheck before relying" (entry older than 30 days by default) or "not checked". It never answers "no order exists".
5. **Disclosure wording options** (`standard/DISCLOSURE_OPTIONS.md`). Four drafts for the General Counsel to choose from. None is approved.
6. **Open questions** (`OPEN_QUESTIONS.md`) for an attorney.

The rule the kit is built around: a machine result is not attorney verification. A citation the checker marks PASS still needs the responsible attorney's own entry saying who checked it, when, and how.

## Run it

Python 3.10 or later. Standard library only. No network access is used.

```bash
python run_demo.py          # rebuilds output/ and index.html from the sample filings
```

Then open `index.html` in a browser. It walks through one fictional filing and lists all eight.

```bash
python -m filingkit check  sample_filings/F-2027-001/filing.json
python -m filingkit sign   sample_filings/F-2027-001/filing.json --signer "Perrin Ashgrove (fictional attorney)" \
                           --attest --out-dir /tmp/fk --ledger /tmp/fk/ledger.jsonl
python -m filingkit record /tmp/fk/F-2027-001.record.json --document sample_filings/F-2027-001/document.txt \
                           --ledger /tmp/fk/ledger.jsonl
python -m filingkit verify-ledger /tmp/fk/ledger.jsonl
python -m filingkit judge  --court-id fict-port-selwyn --judge-id fict-marrowby
python -m pytest -q
```

Exit codes: 0 clear or valid, 1 input error, 2 blocked, 3 invalid record or ledger, 4 record check incomplete. `--as-of` sets the clock (the sample judge entries are dated around January 2027, so use for example `--as-of 2027-01-12` when trying the samples).

## Sample filings

| Filing | Scenario | Result |
|---|---|---|
| F-2027-001 | Clean pass, AI use disclosed | Clear, signed |
| F-2027-002 | All citations pass the machine check; one has no attorney attestation | Blocked |
| F-2027-003 | Signed, then the document is edited | Record becomes INVALID |
| F-2027-004 | Discovery response | Clear; citation items advisory |
| F-2027-005 | AI used, no disclosure decision | Blocked |
| F-2027-006 | Fictional judge with a certification order | Clear, response recorded |
| F-2027-007 | Fictional judge whose entry is stale | Blocked until rechecked |
| F-2027-008 | Not-found citation and quote mismatch | Blocked |

Results are in `output/` (`SUMMARY.txt` is the short version).

## How it connects to the existing citation checker

The checker (`sb574_verifier`, package `citecheck`) is not modified or imported. `filingkit/adapter.py` reads its JSON:

- the machine report written by `python -m citecheck.cli DOC --json out.json` (`doc_sha256`, `citations[]` with `id`, `text`, `machine_status`, `checks[]`), and
- the verification certificate from its `build_certificate()` (`document.sha256`, `citations[]` with `citation_id`, `verified_by`, `verified_at`, `note`).

`filingkit/dochash.py` reproduces the checker's text normalisation so the kit can confirm a report belongs to the document in front of it. The ledger uses the same entry layout and hash scheme as the checker's ledger, so `verify-ledger` can check either.

The checker was run for this build (in a scratch environment with its dependencies installed) to produce:

- `tests/fixtures/`: its own 17-citation sample brief, the machine report, a certificate and a ledger. These are real outputs of that tool, not hand-written. They contain statute and regulation citations because that sample brief does; those are test input, not statements made by this kit.
- `sample_filings/*/citation_report.json`: its reports on the eight fictional documents here, which cite only the fictional cases in its demo mirror.

## Law

Every statutory statement the kit shows comes from `data/authorities.json` (nine entries, each with section, paraphrase and `verified_on`). Documents and code refer to entries by key, for example `[ccp_128_7_b2A]`. To correct a paraphrase, edit that one file and run `python run_demo.py`. Anything else that looks like a requirement is a firm policy setting in `data/policy.json` or a question in `OPEN_QUESTIONS.md`. The kit does not say that any particular citator product is required.

## What is tested

`python -m pytest -q` runs 124 tests:

- adapter: both checker formats load; malformed reports are rejected; a machine report never becomes an attestation
- hashing: the kit's text hash equals the checker's `doc_sha256` for the sample brief as .txt and as .docx
- ledger: edits, removals, reordering and bad lines are detected; a ledger written by the checker verifies
- judge lookup: schema checks, the 30-day boundary, configurable window, "not checked" wording
- checklist: each blocking rule, each policy switch, discovery handling, the real 17-citation report
- record: sign-off rules, required contents, invalidation on any document edit, record or ledger tampering, HTML escaping
- command line: exit codes and a full check, sign, record, verify-ledger run
- guards: no statute section outside the verified list anywhere in the kit; paraphrases only in `authorities.json`; the demo page loads nothing external; `run_demo.py` reproduces the committed `output/` byte for byte

## What is not done

- No attorney has reviewed the standard, the disclosure drafts, the policy defaults or the paraphrases.
- No sign-in. The signer's name is typed. There is no electronic signature.
- The ledger is tamper-evident, not tamper-proof. Someone who can rewrite the whole file can rebuild the chain, and removing entries from the end is only caught if the head hash was saved elsewhere (`--expect-head`). No file locking for concurrent writers.
- Nothing stops a document from being filed. Enforcement would sit in the document management or e-filing step, which would ask for a valid record with the same SHA-256.
- The judge orders file is fictional sample data and is maintained by hand. There is no feed of real orders.
- .docx support reads body paragraphs only, like the checker. It was tested against one .docx. Tables, footnotes and headers are not hashed into the text hash (the file hash still covers every byte).
- The kit does not check whether an authority is still good law, and does not check citations to the record or exhibits.
- It covers only the SB 574 provisions listed in `data/authorities.json`. The bill's other sections are not addressed.
- A later record does not automatically supersede an earlier one for the same filing; both stay in the ledger.

## Files

```
filingkit/        adapter, dochash, checklist, record, render, ledger, judges, disclosure, policy, authorities, cli, demo_page
data/             authorities.json, policy.json, judge_orders.sample.json, disclosure_options.json
standard/         FILING_STANDARD.md, DISCLOSURE_OPTIONS.md
sample_filings/   eight fictional filings (descriptor, document, checker report, attestations)
output/           demo results (checklists, records, ledger, edit and tamper demos)
tests/            pytest suite and fixtures from the existing checker
index.html        static demo page, built by run_demo.py
OPEN_QUESTIONS.md
```
