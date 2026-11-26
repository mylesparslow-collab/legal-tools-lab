# Catch-the-error drill

A 10 to 30 minute reading exercise for lawyers who are about to be given AI drafting or review tools. The trainee reviews contract drafts that have errors planted in them, marks what looks wrong, and then sees what was caught and what was missed.

This is a personal portfolio demo. Every document in it is fictional. It is not legal advice, it was not reviewed by an attorney, and it is not in use at any firm.

The documents, the planted errors and the explanation for each one come from the sibling folder `../governance-eval-kit` (12 synthetic California agreements, 90 planted defects, an answer key, and a register of the statute sections that were read). This tool adds no law of its own: every explanation a trainee sees is copied from that kit's answer keys and defect catalog.

## How to open it

Double-click `index.html`. It runs from the file system, with no server, no network and no install. `facilitator.html` is the page for group results.

To rebuild the exercise data after the eval kit changes:

```
python3 build.py            # writes app/data.js
python3 build.py --check    # exits 1 if app/data.js is out of date
```

Python 3.11 or later, standard library only. Tests need `pytest`, Node and Playwright with Chromium.

## What it does

Three exercises:

- **Timed spot check.** Five minutes with a whole agreement of 6,000 to 9,500 words. The trainee marks what they can; when the clock stops the answers are shown. `index.html?seconds=180` changes the time.
- **Which would you verify?** Ten statements from one agreement, five of them planted errors, in document order. The trainee ticks the ones they would check before relying on them.
- **Review an AI draft.** An excerpt (about 1,300 or 2,500 words) or a whole agreement, with no clock. The trainee selects a passage and chooses a defect type. The answer screen shows found, missed and false alarms side by side, with the answer key's explanation, the statute cited, and the catalog's statement of the rule.

A facilitator picks a session by practice area (commercial lease, SNF or RCFE asset purchase, public works contract, executive employment, or mixed), by length (10, 20 or 30 minutes) and by rotation (A, B or C, which changes which of the three documents plays which part). A 10 minute session is the spot check and the verify list. 20 and 30 minute sessions add the review, on the shorter or longer excerpt. Any single exercise can also be run on any document.

At the end the trainee sees a summary with totals, a breakdown by defect type and by catalog rule, and can print it or save it as a JSON file. The file has no name in it. The facilitator page loads several of those files and shows, for the group only, the share of planted errors found in each exercise, the planted errors most people missed, and any unplanted paragraph that two or more people marked. It has no per-person table.

`FACILITATOR_GUIDE.md` has the session plan and debrief points.

## How marks are scored

Offsets are character positions in a document's display text. The rule is in `app/scoring.js`:

1. A mark must be 20 to 600 characters. Shorter or longer marks are refused in the app and not scored.
2. A mark reaches a planted error when it overlaps one of the error's quoted spans by at least 30 characters, or by half the span if the span is shorter than 60 characters.
3. A mark counts for one planted error: the one it overlaps most (on a tie, the one listed first in the answer key). A selection that covers two planted errors finds only one of them.
4. A planted error is found when a mark counts for it. If the type chosen on the first such mark is not the error's type, it is "found, misclassified". Both count toward recall.
5. Further marks on an error already found are repeats. They are not hits and not false alarms.
6. A scored mark that counts for no planted error is a false alarm.

Rules 2 and 3 are the eval kit's own rule for matching a verbatim quote (`harness/score.py`, `_match`), with the same constants, and a test checks the two implementations against each other on 300 random cases. The differences are deliberate:

- The kit's prompt asks tools for quotes of 20 to 400 characters. The drill allows up to 600, so a person can mark a whole sentence without counting characters.
- The kit also matches a missing-clause defect by the section a tool cites, and lets a reviewer adjudicate. The drill has neither; a person marks text.
- The type check (rule 4) is new. The kit does not score classification.

The defect types are the catalog's own two fields, kind and severity: clause conflicts with a rule (high severity), clause conflicts with a rule (medium severity), a required clause is missing. The catalog has no difficulty or subtlety field, so the drill has no difficulty levels.

In the verify list a tick on an unplanted statement is counted as an extra check, not as an error.

## How the build works

`build.py` reads the corpus, the answer keys, the defect catalog and the register of verified sections, and writes `app/data.js`. Nothing is copied by hand.

- Each quote in an answer key is located with the kit's own text normaliser and must occur exactly once in its document, inside one paragraph or table cell, and match the displayed text. Otherwise the build stops with an error. There is no fuzzy matching.
- Each document and answer key is recorded with its SHA-256, and the data file carries a build id. Result files record both, and the facilitator page skips a file from a different build.
- A defect whose authority is not in `verified_authorities.json` is left out and listed.
- Excerpts are the run of consecutive sections, within the word budget, that holds the most planted errors. Unplanted statements for the verify list are sentences that state a number, from paragraphs with no planted error, chosen by a hash of the text so the list is stable.

Of the 90 planted defects, 89 are scored. One (`lease-01-D1`, no CASp inspection statement) is a missing clause for which the key gives no passage. It cannot be found by marking text, so it is shown on the answer screen as "also planted, not scored". None were excluded.

## What is tested

`python3 -m pytest -q` runs 69 tests:

- **Build (34).** `app/data.js` matches a fresh build; all 90 defects are accounted for; every span equals its key quote word for word and occurs once; hashes match the source files; explanations, titles, authorities and catalog rules are copied verbatim; every authority is in the verified register; excerpts, verify lists and the 45 sets are well formed; the build fails on a missing quote, a one-character difference, a duplicated quote, an ellipsis quote and an unknown catalog code, and leaves out a defect with an unverified authority.
- **Scoring (27).** The 30-character threshold on both sides, the half-span rule, edge-touching marks, a selection covering two defects, ties, repeats, wrong type in the right place, too-short and too-long marks, two-span defects, empty cases, breakdowns, the verify list, session totals, result-file validation, group results, and agreement with the eval kit's matcher.
- **App (8).** No network calls or remote files, storage only inside `try`, dark mode, focus and print styles, no names or ranking, and the browser test below.

`node tests/smoke.js` opens the app from `file://` in Chromium and makes 12 checks: a full 20 minute session in which one planted span and one wrong span score exactly one hit and one false alarm; the saved JSON; keyboard-only marking; a run with `localStorage` blocked on a tablet-sized dark screen where the clock runs out; an over-long mark being refused; the facilitator page adding up three files and skipping a bad one; and no page errors or network requests. It writes the screenshots in `docs/`.

## What is not done

- **No lawyer has tried it.** Timings, excerpt lengths and the 150 words a minute reading budget are planning assumptions, not measurements.
- **The errors are planted, not produced by an AI tool.** The documents were written to carry specific statutory conflicts. Nothing here shows what a real tool gets wrong, or how often.
- **The law was read by an AI assistant on November 25, 2026 and not checked by an attorney.** The drill inherits that limit from the eval kit. See that kit's `VERIFICATION.md` and `CORRECTIONS.md`. Statutes change; re-read before using this with anyone.
- **"Not planted" is not "correct".** The answer key covers planted defects only. The kit says each document has one clause that looks wrong and is not, but the keys do not record which, so the drill cannot point to it.
- **Missing clauses are a poor fit for marking.** Three of the four omission defects are scored by marking the nearest related clause, as the key locates them; the fourth is not scored.
- **The verify list is statements, not citations.** The corpus is contracts, so there are no case citations to check. Fabricated authority is not exercised.
- **Accessibility was built in but not audited.** Marking works from the keyboard (arrows move by paragraph and sentence, number keys mark), focus is visible, and the pages follow the system light or dark setting. It has not been tested with a screen reader or on a physical tablet, and sentence splitting for the keyboard path is approximate. Only Chromium was run.
- **No session state survives a reload.** A reload in the middle of an exercise starts over. Only the last finished summary is kept, in `localStorage` when it is available.
- **Group results are as honest as the files.** A result file is plain JSON that a trainee could edit. This is a training aid, not an assessment.

## Files

```
index.html              trainee page
facilitator.html        group results page
build.py                builds app/data.js from ../governance-eval-kit
app/data.js             generated: documents, planted spans, sets
app/scoring.js          matching and scoring (browser and Node)
app/app.js              trainee page logic
app/facilitator.js      group results logic
app/styles.css
tests/                  pytest suite, Node bridge, Playwright smoke test
docs/                   screenshots from the smoke test
FACILITATOR_GUIDE.md    session plan and debrief
```
