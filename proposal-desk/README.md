# Proposal desk

**Personal portfolio demo. All data is synthetic. Not legal advice. Never run it on real proposals.**

Every agency, lawyer, client, matter and past proposal in this folder is invented. The firm is
"Example Firm LLP". Any resemblance to a real organisation or person is accidental. The tool has
not been tested on real RFPs or on a real firm's records. `SWAP_IN_REAL_DATA.md` says what that
test would need.

**Parser accuracy on RFPs it had never seen: requirements precision 0.769, recall 0.571; all
categories together precision 0.798, recall 0.512.** That is one run on three RFPs written by an
independent author (held-out batch B), made after the parser was frozen and not repeated. The
submission deadline in force was right on 1 of the 3. On one of the three the parser found no
requirements at all. Every other parser figure in this README is in-sample or was used for fixes;
see "Parser check" below.

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
python -m pytest -q         # 278 tests
python run_heldout.py a after_fixes   # held-out runs are recorded once; this prints "Already recorded"
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

- **Two separate consents.** They are different permissions and are stored in different fields.
  - `consent_to_name_client` (experience records): the client agreed to be named. Without it the
    approved anonymized description is printed ("a water district in the foothills"). With
    neither, the record is left out and listed for the proposal lead.
  - `consent_to_list_contact` (reference records): the contact agreed to be listed as a
    reference. A reference line prints a contact and a client, so it needs both: this field on
    the reference record and `consent_to_name_client` on the linked experience record. If either
    is missing, false or unclear, or the link does not resolve, the reference is not listed.
  Both default to false and only an explicit yes counts. Neither is inferred from the other. The
  earlier single field `client_consent` is not read; `check-data` warns if it sees one.
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

The figure to rely on is the last row. P is precision, R is recall.

| Run | Requirements P | R | All categories P | R | Submission deadline right | Page limit right | Addendum checks |
|---|---|---|---|---|---|---|---|
| Held-out batch A, first run, before any change | 1.000 | 0.000 | 0.489 | 0.132 | 0 of 3 | 0 of 3 | 2 of 11 |
| Held-out batch A, after general fixes made from its misses | 1.000 | 1.000 | 0.994 | 1.000 | 3 of 3 | 3 of 3 | 14 of 14 |
| **Held-out batch B, one run at the end, sealed until then** | 0.769 | 0.571 | 0.798 | 0.512 | 1 of 3 | 2 of 3 | 5 of 11 |

How these were made:

- `heldout/` holds six RFPs and hand-written keys by an independent author who had not read the
  parser (`heldout/README.md`). Batch A was the working batch. Batch B was not opened until the
  parser was frozen, was run once, and the parser has not been changed since.
- **First run on batch A.** The parser as it stood found none of the 36 requirements, no
  deadlines, forms, criteria, qualifications or insurance items. It did not recognise any of the
  three layouts. Precision of 1.000 on requirements there means only that it reported nothing.
- **After fixes on batch A.** The parser was largely rewritten from those misses. Batch A is now
  an in-sample figure and shows only that the fixes do what they were meant to do.
- **Batch B.** Per RFP, requirements P / R: Dunmarrow 0.625 / 1.000, Wexcombe 1.000 / 0.000,
  Saltbrook 1.000 / 0.769. By category, correct / extra / missed: deadlines 9 / 3 / 10,
  requirements 20 / 6 / 15, forms 3 / 0 / 12, evaluation criteria 10 / 4 / 6, minimum
  qualifications 0 / 0 / 13, insurance 5 / 3 / 6, submission mechanics 17 / 1 / 14, parties
  23 / 5 / 7. Question type was right on all 20 requirements that were found.
- One caveat about batch B. `heldout/README.md` describes each batch B layout in a sentence (dates
  written as "the 10th of December 2026", ISO dates, weights as fractions, addenda placed first).
  That file had to be read for the key format, so those descriptions were seen while the fixes
  were made, and three test documents in those styles were written for `tests/layouts/`. The
  batch B RFPs, keys and builder were not opened before the run.
- Scoring is in `desk/heldout_score.py`. It accepts the key's `alt_labels` and `alt_qtypes`,
  matches unnumbered requirements on text, counts anything under `not_requirements` or
  `dates_that_are_not_deadlines` as an extra, and treats a deleted requirement that is still
  parsed as an extra. Items marked "check" count like any other. Addendum handling is its own
  column: one check per value an addendum changed, as in force after the last addendum, plus
  whether the date as issued is still shown where the new date was right (which is why the
  number of checks differs between rows). It is not added into the all-categories figure.
- Recorded results: `data/heldout_results/` (three `.json` and `.md` files). `run_heldout.py`
  will not overwrite a recorded run.

Earlier figures, kept for the record:

| | Correct | Extra | Missed | Precision | Recall |
|---|---|---|---|---|---|
| Round 1: four sample RFPs, in-sample | 199 | 1 | 0 | 0.995 | 1.000 |
| Round 1: fifth RFP by the parser's author, first run | 6 | 3 | 38 | 0.667 | 0.136 |
| Round 1: the same fifth RFP after six general fixes | 33 | 7 | 11 | 0.825 | 0.750 |
| Now: four sample RFPs, in-sample | 199 | 0 | 0 | 1.000 | 1.000 |
| Now: the fifth RFP, in-sample | 44 | 0 | 0 | 1.000 | 1.000 |

- All five rows are self-fit. The same person wrote those RFPs, their keys and the parser, and
  the fifth RFP was used for fixes after its first run. They show the parser does what it was
  built to do on those files and nothing more.
- The pattern has now repeated three times: a layout nobody tuned for scores low on first
  contact (recall 0.136, then 0.132, then 0.512), and high once it has been fixed against.

### What is still wrong on batch B

The parser was not changed after the batch B run. These are the causes, read afterwards from the
recorded result and from the batch B RFPs (which were parsed again once to list their sections;
nothing was re-scored).

- **Headings written as numbered questions in capitals** ("2. WHEN IS EVERYTHING DUE?") were not
  taken as headings, because the heading pattern does not allow a question mark. On that RFP no
  section was found, so nothing but the parties was extracted: 0 of 12 requirements, 0 of 6
  deadlines. The parser did report "no submission deadline found" and "no numbered proposal
  requirements found".
- **Section names outside the keyword list.** "THRESHOLD REQUIREMENTS" was not read as minimum
  qualifications and "SUPPLEMENTAL QUESTIONS" was not read as proposal content. No minimum
  qualification was found in batch B (0 of 13).
- **Sub-sections of a different kind inside a section.** Minimum requirements and formatting
  rules numbered 4.1 and 4.2 under "PROPOSAL REQUIREMENTS" were read as six extra requirements.
- **A section that mixes kinds.** "FORMAT, DELIVERY AND FORMS" was read as a forms section only,
  so delivery rules and most of its forms were missed. Forms recall was 3 of 15.
- **Addenda.** 5 of 11 checks passed. The due date moved twice, its time, the page limit, the
  deleted requirement and the removed form were right. Missed: a date changed "from January 6,
  2027 to 1/11/27", interviews and board action restated in two plain sentences in one item, a
  form added by "Add HA Form 6, ...", and points moved from a deleted item to a criterion named
  in quotation marks. Item labels such as "2-A." were not expected.
- **A data-sheet row for the closing time** was not matched to the submission deadline on one RFP.
- **A weights table with a header row and a total row** produced three extra criteria.
- **Insurance amounts written "USD 5,000,000"** are stored by the parser as "$5,000,000". The key
  holds the printed form, so three items were counted as both extra and missed. This is a
  disagreement about format, and it was left in the score as run.
- **Names.** "Housing Authority of the County of Dunmarrow" was shortened to "County of
  Dunmarrow"; a company name with "&" lost its first word; a union named "Guild" or "Local 4410"
  was not classed as adverse; one staff member in a board paragraph was classed as board.

Real RFPs arrive as PDFs with tables, footers and scanned attachments. Assume the parser will do
no better on them than the batch B row, and possibly as badly as the first run on batch A. Every
parse needs a person to read it against the RFP.

## What is tested

278 pytest tests, all passing:

- parser: each sample RFP against its key; exact requirement text and numbering; quoted source
  lines; addendum changes to dates, page limit and forms; an addendum that contradicts the
  schedule; wrapped lines and tabs; items marked "check" (unknown question, approximate date,
  invalid date, word and number that disagree, forms outside a forms section); missing deadline;
- parser layouts (`tests/test_layouts.py`, with three documents written for the tests): date and
  time forms; dates in sentences; date-first schedule rows; page headers and a table of
  contents; lettered sections with roman items; two-line and run-in headings; question headings;
  data-sheet rows and tick boxes; weights in a sentence and as fractions; unnumbered
  requirements; addenda placed first, a date moved twice, deleted requirements, removed forms
  and criteria, changed weights and insurance amounts; people with roles in lists;
- held-out scoring (`tests/test_heldout.py`): alternative labels and question types, unnumbered
  matching on text, negatives, deleted requirements, the addendum line; the three recorded runs
  exist and are not overwritten; a fresh batch A run equals the recorded one; this README states
  the recorded figures. No test opens batch B;
- fact guard: wrong agency name in full, possessive (straight and curly apostrophe), capitals,
  across a line break, abbreviation, dotted abbreviation, place name alone, an agency that shares
  a place name with this one, a place that is also a firm office; agency words and governing-body
  terms; departed attorney; 27 firm-fact statements, right and wrong; unfilled placeholders;
- consent: named, anonymized and omitted records; consent values other than an explicit yes; the
  two consents checked separately, with a reference withheld when either is missing or the link
  is broken; the old single field ignored and reported; no non-consented client or contact name
  appears in any output for any sample RFP;
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
- **The parser is pattern-based.** It reads the layouts it has patterns for. On unseen layouts it
  found about half of what the keys list (batch B above), and on one RFP nothing. Sub-items
  nested under a requirement are not linked to their parent. Unnumbered requirements are found
  only in a section recognised as proposal content, and are marked "check". Dates read from
  sentences, weights read from sentences and anything found outside its expected section are
  marked "check". Only the first submission deadline is used.
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
desk/            rfp.py (parser)  evaluate.py (in-sample scoring)  heldout_score.py (held-out scoring)
                 library.py (BM25, ranking)
                 experience.py (matching, team, qualifications, references)  facts.py (fact guard)
                 pipeline.py (draft sections, matrix, disqualifiers, go/no-go)  render.py
                 harvest.py  loader.py + schemas.py (canonical schemas, mapping loader)
                 demo_page.py  __main__.py (command line)  util.py
drafting/        llm_hook.py (optional, off)
data/rfps/       four hand-written RFPs        data/answer_keys/   hand-written keys
data/holdout/    fifth RFP by the parser's author, its key, and the two recorded round 1 results
heldout/         six RFPs and keys by an independent author (batch_a, batch_b) and their README
data/heldout_results/   the three recorded held-out runs      run_heldout.py   runs and records them
data/library/    generated synthetic library (generate_data.py, seeded) and mapping.json
data/            demo_config.json, sample status file, sample holiday file, harvest sample
output/          committed sample outputs      index.html   demo page for one RFP
tests/           278 tests, and tests/layouts/ (three documents written for the tests)
```
