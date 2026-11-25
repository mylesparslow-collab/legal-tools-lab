# Proposal desk

**Personal portfolio demo. All data is synthetic. Not legal advice. Never run it on real proposals.**

Every agency, lawyer, client, matter and past proposal in this folder is invented. The firm is
"Example Firm LLP". Any resemblance to a real organisation or person is accidental. The tool has
not been tested on real RFPs or on a real firm's records. `SWAP_IN_REAL_DATA.md` says what that
test would need.

## What it does

Public agencies issue requests for proposals (RFPs) for legal services. Responses are repetitive,
deadline-driven, and easy to lose on a missed form. This tool takes the plain text of an RFP and
produces:

1. **A parsed RFP.** Deadlines with the quoted source line, submission mechanics (copies, format,
   page limit, font, margins, delivery), each numbered requirement as its own item with its exact
   text, mandatory forms, evaluation criteria and weights, minimum qualifications, insurance
   statements. Addenda are applied and the change is shown. Anything the parser is unsure of is
   kept and marked "check".
2. **A compliance matrix** (HTML and CSV). Every requirement, form, qualification, insurance
   statement and submission rule, with where the draft answers it, a status, an owner and a due
   date counted back from the submission deadline in business days. A disqualifiers panel lists
   every mandatory item not yet satisfied.
3. **A first draft** (Markdown and print-ready HTML) in the RFP's own order and numbering,
   assembled from previously approved answers. Each inserted passage shows its source proposal,
   date and approver. Every gap is marked in the text.
4. **An experience and team match** with the reason for each choice, and a check of minimum
   qualifications that bio data can check.
5. **A conflicts hand-off list**: the parties named in the RFP, for the conflicts team.
6. **A go/no-go summary**: deadline, minimum qualifications, content coverage, open disqualifiers.
7. **A harvest command** that files final answers back into the library after submission.

Drafting is retrieval and assembly. No model writes anything. `drafting/llm_hook.py` is one
clearly marked, switched-off place where a firm-approved model could later rewrite an assembled
passage. Anything it returned would go through the same fact guard and would still need a person
to read it against the source.

RFP requirements are whatever the RFP text says. The tool knows no procurement rules.

## Run it

Python 3 standard library only. No network access. pytest is needed only for the tests.

```
python run_demo.py          # writes output/ and index.html, prints a summary
python -m pytest -q         # 222 tests
```

Open `index.html` for the demo page (one RFP: the water district general counsel RFP with an
addendum and a page limit). Sample outputs for all four RFPs are in `output/`.

Command line:

```
python -m desk parse   data/rfps/general_counsel_redwood_flats.txt [--json out.json] [--key data/answer_keys/general_counsel_redwood_flats.json]
python -m desk match   data/rfps/general_counsel_redwood_flats.txt --as-of 2026-11-25
python -m desk draft   data/rfps/general_counsel_redwood_flats.txt --out out/ --as-of 2026-11-25 [--holidays data/holidays_sample.json] [--status data/demo_status_redwood_flats.json]
python -m desk matrix  data/rfps/general_counsel_redwood_flats.txt --out out/ --as-of 2026-11-25
python -m desk harvest final.md --rfp data/rfps/general_counsel_redwood_flats.txt --data <library copy> [--outcome pending]
python -m desk harvest --set-outcome P-2026-H-redwood-flats won --data <library copy>
python -m desk check-data [--data <library>] [--mapping <mapping.json>]
```

`--as-of` defaults to today. The demo fixes it at 2026-11-25 so the committed outputs do not change.

## Rules the tool enforces

- **Client consent.** A client is named only when its record has `client_consent` true. The
  default is false, and only an explicit yes counts. Without consent the approved anonymized
  description is printed ("a water district in the foothills"). With neither, the record is left
  out and listed for the proposal lead. Reference contacts follow the same rule.
- **Conflicts.** The conflicts section is never written by the tool. Past conflicts statements in
  the library are never inserted.
- **Pricing, cover letter, disclosures, signatures.** Left to a person. Marked in the draft.
- **Stale content.** An answer past its review date is shown as an alternative and never inserted.
- **Fact guard.** Firm facts come from one file, `firm_facts.json`, with an as-of date. A reused
  passage is flagged as blocking if it names another agency (full name, possessive, place name
  alone, abbreviation), uses an agency word that does not fit ("the City" for a District, "City
  Council" for a board), names an attorney who has left, or states a head count, founding year,
  office, client count, matter count or bar admission that disagrees with the file. A clean answer
  is preferred over a higher-ranked flagged one; if none is clean, the flagged passage is inserted
  with the flag shown and the section counts as partial.
- **Due dates.** Business days skip weekends. Holidays are skipped only if a holiday file is given.

## Results on the sample data

Run as of 2026-11-25.

| RFP | Coverage | Answered / partial / none / person | Open disqualifiers | Blocking flags |
|---|---|---|---|---|
| City attorney, City of Marlow Ridge | 86% (6 of 7) | 6 / 1 / 0 / 4 | 24 | 0 |
| General counsel, Redwood Flats Water District | 83% (5 of 6) | 5 / 1 / 0 / 4 | 20 | 0 |
| Labor negotiator, Quillfeather Unified School District | 50% (3 of 6) | 3 / 2 / 1 / 2 | 15 | 1 |
| Special counsel, Tannery Creek Transit Authority | 71% (5 of 7) | 5 / 2 / 0 / 2 | 24 | 1 |

Coverage is the share of requirements the library is allowed to answer (everything except cover
letter, conflicts, pricing and disclosures) that were answered in full from approved, current
text that passed the fact guard. "Answered" does not mean finished: a person still reads it.
The disqualifier counts are high because every form, signature, insurance statement and delivery
step starts open.

These numbers describe a synthetic library written to exercise the tool. They say nothing about
coverage on a real library.

### Parser check

| | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| Four sample RFPs, against hand-written keys | 199 | 1 | 0 | 0.995 | 1.000 |
| Held-out fifth RFP, first run | 6 | 3 | 38 | 0.667 | 0.136 |
| Held-out fifth RFP, after six general fixes | 33 | 7 | 11 | 0.825 | 0.750 |

Read these with care.

- The first row is in-sample. The same person wrote the RFPs, the keys and the parser. The keys
  were written before the parser. On its first run the parser got one agency name wrong, read one
  table header as a criterion and gave two people the wrong role; those were fixed. The one remaining
  extra item is an exhibit named in the text, which the parser keeps as "check" by design.
- The second row is the honest one. A fifth RFP (`data/holdout/`) was written in a different
  layout after the parser was finished and run once. The parser did not recognise its headings
  and found almost nothing. It did report "no submission deadline found" and "no numbered
  proposal requirements found" rather than failing silently.
- The third row is after six general fixes prompted by that run. It is no longer held out. The
  remaining misses were left unfixed and are listed in `output/parser_evaluation.md`.

Real RFPs arrive as PDFs with tables, footers and scanned attachments. Until the parser has been
tested on them, assume it may do no better than the second row.

## What is tested

222 pytest tests, all passing:

- parser: each sample RFP against its key; exact requirement text and numbering; quoted source
  lines; addendum changes to dates, page limit and forms; an addendum that contradicts the
  schedule; wrapped lines and tabs; items marked "check" (unknown question, approximate date,
  invalid date, word and number that disagree, forms outside a forms section); missing deadline;
- fact guard: wrong agency name in full, possessive (straight and curly apostrophe), capitals,
  across a line break, abbreviation, dotted abbreviation, place name alone, an agency that shares
  a place name with this one, a place that is also a firm office; agency words and governing-body
  terms; departed attorney; 27 firm-fact statements, right and wrong; unfilled placeholders;
- consent: named, anonymized and omitted records; consent values other than an explicit yes; no
  non-consented client name appears in any output for any sample RFP;
- library: BM25; preference for won, recent, approved, same agency type and practice; stale
  answers never inserted; provenance on every passage;
- matrix and assembly: RFP order and numbering; conflicts, pricing and cover letter never
  written; every item has a row, owner and due date; business-day arithmetic with and without a
  holiday file; the disqualifier panel equals the set of unsatisfied mandatory rows; page-limit
  failure; status file; the model hook is off, and when a test switches it on its output is
  fact-checked and the section drops to partial;
- harvest, the mapping loader (CSV with other column names, rejected records), the command line,
  self-contained HTML, and that committed outputs match a fresh run.

## What is NOT done

- **No real data.** Nothing here has seen a real RFP, a real proposal or a real firm's records.
- **Plain text only.** No PDF or Word input, no tables that span pages, no scanned attachments.
  Text must be extracted first, and extraction errors are not detected.
- **The parser is pattern-based.** It reads the layouts it has patterns for. See the held-out
  result above. Sub-items nested under a requirement are not linked to their parent. Requirements
  written as prose with no number or bullet are missed. Only the first submission deadline is used.
- **Question types are keyword rules.** A question that asks two things gets one type. The tool
  does not check that an inserted answer addresses every part of the question.
- **The fact guard checks what it has patterns for.** A wrong number in an unusual sentence, a
  wrong agency name that is not in the library, a misspelt name, or a departed attorney referred
  to by surname only (warning, not blocking) can get through. A passage with no flags has not
  been proved correct. Numbers the guard cannot place are listed as a warning for a person.
- **Minimum qualifications.** Only years since admission (year only, jurisdiction not checked),
  office location and firm head count are checked. Everything else is marked for a person.
- **Page estimate is a word count** at a configurable words-per-page figure, not a layout.
- **Holidays** are not handled unless a holiday file is supplied. No time zones. Deadline times
  are shown but not used in the arithmetic.
- **Forms are not filled in.** The matrix says whether the firm has standard answers on file.
- **No conflicts check, no pricing, no signatures, no submission.**
- **No clean export.** The draft is a working draft with internal notes. Producing the final
  document is a person's job.
- **No user accounts, no audit log, no concurrency control** on the library files.
- **Status marks** ("done") are taken on trust from a JSON file.
- **Not compatible with any named system.** Data comes in through a mapping file from CSV or
  JSON exports. Nothing has been tested against any product's export.
- `index.html` was looked at once in headless Chrome. The HTML files are checked for structure and
  self-containment by test. They have not been reviewed in other browsers, on a phone, or printed.

## Layout

```
desk/            rfp.py (parser)  evaluate.py (parser scoring)  library.py (BM25, ranking)
                 experience.py (matching, team, qualifications, references)  facts.py (fact guard)
                 pipeline.py (draft sections, matrix, disqualifiers, go/no-go)  render.py
                 harvest.py  loader.py + schemas.py (canonical schemas, mapping loader)
                 demo_page.py  __main__.py (command line)  util.py
drafting/        llm_hook.py (optional, off)
data/rfps/       four hand-written RFPs        data/answer_keys/   hand-written keys
data/holdout/    fifth RFP, its key, and the recorded first-run result
data/library/    generated synthetic library (generate_data.py, seeded) and mapping.json
data/            demo_config.json, sample status file, sample holiday file, harvest sample
output/          committed sample outputs      index.html   demo page for one RFP
tests/           222 tests
```
