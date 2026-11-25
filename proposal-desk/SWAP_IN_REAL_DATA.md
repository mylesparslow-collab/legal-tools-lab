# Swapping in real data

This demo has only ever run on invented data. This note says what a test at a firm would need.
It makes no claim about any named document, matter or proposal system: data comes in as CSV or
JSON exports through a mapping file, and nothing here has been tested against any product.

Before any real data is loaded, the firm decides who may see it, where it is stored, and whether
past proposals and client names may be used this way at all. That decision is not the tool's.

## 1. What to collect

Six record types and one facts file. The canonical field names are in `desk/schemas.py`.

| Record | What it is | Fields that matter most |
|---|---|---|
| Past proposal answers | One row per answer in a past proposal | `answer_text`, `question_type`, `proposal_agency`, `submitted`, `outcome`, `approved`, `approver`, `review_by` |
| Experience records | One row per engagement | `client_name`, `client_consent`, `anonymized_description`, `agency_type`, `practice`, `subjects`, `role`, years |
| Attorney bios | One row per attorney | `name`, `title`, `status` (active or departed), `admit_year`, `office`, `practices` |
| Rate schedules | Approved schedules with dates | `effective`, `expires`, `approved_by` (shown for reference only; never inserted) |
| References | One row per contact | `contact_name`, `client_name`, `client_consent`, `last_confirmed` |
| Standard forms | The firm's standard answers to common forms | `name`, `aliases`, `last_reviewed` |
| `firm_facts.json` | The only source of firm facts | `as_of`, `attorney_count`, `partner_count`, `founded_year`, `offices`, `bar_admissions`, `public_agency_clients`, `matter_counts`, `departed_attorneys`, `approved_by` |

Start small: ten to fifteen recent proposals in one practice, split into answers by hand. Splitting
a proposal into answers is manual work. The tool does not do it.

## 2. How to map it

Write a mapping file. For each record type give the file and, where the firm's column names
differ, the column for each canonical field:

```json
{"experience": {"file": "matters_export.csv",
                "fields": {"id": "Matter No", "client_name": "Client", "client_consent": "OK to name?"},
                "list_separator": ";", "date_format": "%m/%d/%Y",
                "defaults": {"practice": "general_counsel"}}}
```

Then run `python -m desk check-data --data <folder> --mapping <file>`. Records that fail
validation are rejected and listed with the reason. They are not repaired. Fix them at source.
A rejected record is simply absent from the library, so read the list.

## 3. How to tag answers

Tagging is what makes an answer safe to reuse. An untagged answer still works, but the fact guard
will flag it every time.

- **Question type**: one of `firm_overview`, `approach`, `team`, `experience`, `references`,
  `conflicts`, `rates`, `diversity_local`, `transition`. Conflicts and rates answers can be kept
  for the record; the tool never inserts them.
- **Agency type and practice**: used for ranking and matching.
- **Placeholders in the text**, in place of anything specific to the old proposal:
  `{AGENCY}`, `{AGENCY_SHORT}` (becomes "the District"), `{GOVERNING_BODY}`, `{CHIEF_EXEC}`.
- **Fact placeholders**, in place of any firm number or office list: `{FIRM_ATTORNEYS}`,
  `{FIRM_FOUNDED}`, `{FIRM_OFFICE_COUNT}`, `{FIRM_OFFICES}`, `{FIRM_CLIENTS}`. They are filled
  from `firm_facts.json` at draft time, so the answer never carries an old number.
- **Do not name clients or attorneys in answer text.** Client lists come from experience records
  under the consent rule. Team lists come from bios. A client named in answer text is flagged as
  another agency's name.
- **Agency abbreviations**: the guard guesses initialisms ("QHTD"). House abbreviations that are
  not initialisms need to be supplied; the guard has a parameter for them, but the loader does not
  yet read them from a file. That is a gap to close before a real test.

## 4. Who must approve reuse

| Decision | Who | Recorded as |
|---|---|---|
| An answer may be reused | Practice lead | `approved` true and `approver` name |
| A client may be named in a proposal or experience list | The client, through the responsible partner | `client_consent` true on the experience record |
| A client is described without being named | Responsible partner approves the wording | `anonymized_description` |
| A contact may be listed as a reference | The contact, through the responsible partner | `client_consent` true and `last_confirmed` date on the reference record |
| Firm facts | Whoever owns firm data (managing partner's office, marketing or finance) | `approved_by` and `as_of` in `firm_facts.json` |
| Rates | Pricing partner | outside the tool |
| Conflicts | Conflicts team | outside the tool |

**Client consent is the real issue.** Naming a client as a reference or in an experience list
without its agreement can breach the firm's confidentiality obligations and damage the
relationship, and some engagement terms forbid it. So:

- `client_consent` is required on every experience and reference record. A missing or unclear
  value is read as false. Only an explicit yes (`true`, `yes`, `y`, `1`) is true.
- Consent should record who gave it, when, and for what use. The demo schema has only the yes or
  no. A real pilot should add those fields and treat consent as expiring.
- An anonymized description can still identify a client ("the only harbor district in the
  county"). Someone who knows the client must approve the wording.
- The summary on an experience record is printed only when the client may be named.
- Consent on the experience record does not cover the reference contact. They are separate.

Whether and how the firm may do any of this is a question for the firm's own counsel.

## 5. How stale content is retired

- Every answer has a `review_by` date. After it the answer is shown as an alternative, marked
  stale, and never inserted. To bring it back, the practice lead re-reads it and sets a new date.
- Harvested answers come in unapproved with a review date 18 months after submission
  (`review_months_after_harvest` in `workplan.json`). Until approved they can only give a
  "partial" status.
- When an attorney leaves, set `status` to `departed` on the bio the same day. The guard then
  blocks any passage that names them, and they are never proposed.
- When a firm fact changes, change `firm_facts.json` and its `as_of` date. Tagged answers update
  themselves. Untagged answers with the old number start to be flagged. The go/no-go page warns
  when the facts file is more than 180 days old.
- References not confirmed in the last 365 days are marked "reconfirm before use".
- When a client withdraws consent, set `client_consent` to false. The name stops printing at once.
  Check harvested answer text for the name as well.
- Record the outcome (won, lost) once known. Ranking prefers winning answers. With few proposals
  this preference is weak evidence, not proof that an answer is good.
- Delete, do not just flag, anything the firm is no longer allowed to hold.

## 6. What to measure in a firm test

The numbers in the README come from invented data. A firm test should measure, on real RFPs:

1. Parser recall and precision against keys written by the proposal team, for RFPs the parser has
   never seen. The held-out result in this repo (recall 0.14 on first contact with a new layout)
   is the warning. Real RFPs arrive as PDFs; text extraction comes first and adds its own errors.
2. Missed mandatory items. One missed form matters more than the average.
3. How many inserted passages a partner accepts unchanged, edits, or throws away.
4. Fact-guard misses: wrong names or numbers that reached a draft unflagged. Seed some on purpose.
5. Any client named without consent. The target is zero, and one case should stop the test.
6. Time from RFP to matrix and first draft, against the current process.

Run it beside the current process, not instead of it, until those numbers are known.
