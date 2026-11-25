# Brown Act agenda check and CPRA records desk

A small Python tool that checks a local-agency meeting agenda against coded Brown Act rules and
runs the mechanical side of a California Public Records Act response: response clocks, old-to-new
citation mapping, a reviewer-approved withholding log, and PDF redaction that is verified after save.

This is a personal portfolio demo. It was not built or reviewed by an attorney, it is not legal
advice, and it is not a law-firm product. Every agency, person, request and record in
`sample_data/` is fictional.

## Run it

```
pip install -r requirements.txt
python sample_data/make_pdfs.py      # builds the fictional record PDFs
python -m desk demo                  # writes output/report.html and the rest
python -m pytest                     # 42 tests
```

Single commands:

```
python -m desk agenda sample_data/agenda_regular.json
python -m desk cpra sample_data/requests.csv --today 2027-01-22 --ics output/requests.ics
python -m desk legacy sample_data/denial_letter_draft.txt
python -m desk propose sample_data/records
python -m desk produce sample_data/records --out output
```

## What it checks

Agenda (`desk/agenda.py`)

- Posting and notice clocks: 72 hours for a regular meeting (physical and website), 24 hours for a
  special meeting (posting, member notice or waiver, media notice), and the one-hour media notice for
  an emergency meeting.
- Quorum by how each member attends: in person, traditional posted teleconference, remote as a
  disability accommodation (counted as in person), remote for just cause (yearly caps, in-person
  quorum at one location, repealed 1/1/2030), and remote during a proclaimed emergency.
- Closed-session descriptions against the optional forms in Gov. Code § 54954.5, including the
  fields each form asks for.
- Open-session descriptions: very thin descriptions, and a keyword comparison with the staff report
  that flags a "discussion" item whose report recommends action or names a dollar amount the agenda
  leaves out. Also the bar on executive pay items at a special meeting.

Records (`desk/cpra.py`, `desk/redact.py`)

- Day-10 determination date and the latest date a 14-day extension can reach, with checks that an
  extension was noticed in time, for a listed reason, and not past the limit. Calendar file export.
- Finds former § 6250-series citations in a draft letter and gives the current Division 10 section.
- Proposes possible exemptions by pattern (employee home contact details, SSN-shaped numbers, medical
  detail, privilege markings, draft markings, credentials). A proposal does nothing until a named
  reviewer approves it in `decisions.json`. The withholding log lists approved entries only.
- Redaction deletes the text from the PDF, redraws what was not redacted, draws the box, then reopens
  the saved file and searches the text layer and the file bytes for every redacted string. If anything
  is found the output file is deleted and the run stops. An approved redaction is applied to every
  document in the set, which is how quoted copies in reply chains get caught.

## Where the legal numbers live

No deadline or threshold is hard-coded in the Python. They are in `data/*.json`, each with a
citation, a leginfo link, a status and the date checked:

- `verified`: compared with the section text on leginfo.legislature.ca.gov on 2026-11-25.
- `assumption`: a design choice or common practice that is not statute text (for example, quorum as a
  majority of all seats, and rolling a weekend deadline to the next business day).
- `not_modeled`: the statute exists and the tool does not check it.

`CORRECTIONS.md` lists where the source research report differed from the statute text.

## Limits

- The agenda checks need structured input (`sample_data/agenda_*.json`). Nothing parses a PDF agenda.
- The staff-report comparison is keyword matching. The report this came from described a language-model
  step for that and for exemption proposals. No model is called here.
- Not checked: Gov. Code § 54953.4 (remote public access and translation duties for larger bodies),
  the teleconference tracks in §§ 54953.8.1 and 54953.8.4 to 54953.8.7, and six of the § 54954.5 forms.
- When more than one teleconference track is used at a meeting, the tool applies each track's rule
  separately and flags the combination for review.
- The old-to-new CPRA pairing table was written from memory of the 2023 recodification. The new
  sections' text was read; the pairing was not checked against the Law Revision Commission table.
- `data/holidays.json` is an illustrative list, marked unverified.
- Redaction handles text drawn directly on the page. Scanned pages, text inside images, and text
  inside form objects are not handled; for the last, the run stops with an error. Redrawn text uses
  Helvetica. Document metadata is covered only by the byte search.
- An approved redaction is carried to identical text in other documents without a second approval.

## Layout

```
data/          rules, exemption categories, citation map, holidays (all with status fields)
desk/          agenda.py, cpra.py, redact.py, report.py, rules.py, __main__.py
sample_data/   three fictional agendas, a request log, a draft letter, five records, reviewer decisions
tests/         pytest suite
output/        sample run: report.html, agenda_findings.json, requests.ics, withholding_log.csv, production/
```

Dependencies: pypdfium2 (Apache-2.0 / BSD-3-Clause) for PDF work, reportlab (BSD) only to build the
sample PDFs, pytest for tests.
