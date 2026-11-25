# Prop 218 protest tabulator and AB 2257 objection gate

A personal portfolio demo. All parcels, owners, customers, letters, and the agency
("Marlow Creek Water District") are invented. It is not legal advice, was not built
by an attorney, and is not a tool of any law firm.

It does the counting that sits behind a California water or sewer rate hearing:

1. **Protest tally (Cal. Const. art. XIII D, § 6).** Matches each written protest to a
   parcel by APN, then billing account, then service address. Counts one protest per
   identified parcel (Gov. Code § 53755(b)) and compares the count with a majority of
   all identified parcels.
2. **Assessment ballots (art. XIII D, § 4).** A separate, weighted tally: opposed
   dollars against in-favor dollars, with co-owner ballots split by record interest
   (Gov. Code § 53753(e)).
3. **Calendar and notice checks.** The 45-day hearing gap, the AB 2257 45-day windows
   and notice contents (Gov. Code § 53759.1(c)), and the raw 120-day limitations date
   (Gov. Code § 53759).
4. **Objection gate.** Lists every timely written objection and whether it has a
   written response that was dated before the hearing closed and put in front of the
   board (§ 53759.1(c)(5)). Also holds the gate while a protest letter with
   objection-like wording is waiting for a person to triage it.
5. **Record index.** A checklist of the record categories in § 53759.2(b)(1)(A)-(H).

## Run it

Python 3.10 or later. No packages to install.

```
python generate_synthetic.py        # rebuilds sample_data/ (seeded, same every time)
python tabulator.py                 # writes output/
python tabulator.py --assessment    # the small § 4 ballot example
python -m unittest discover -s tests
```

Outputs in `output/`: `report.md`, `result.json`, `protest_audit_log.csv` (every
submission, its disposition, and the reason), `review_queue.csv`, `objection_gate.csv`.

## How it decides

- Nothing is guessed. A submission is COUNTED, DUPLICATE, WITHDRAWN, INVALID,
  NOT_COUNTED, or sent to REVIEW, and each line says why.
- The result is one of three: majority protest, no majority protest, or undetermined.
  It is "undetermined" whenever the items in review could change the answer.
- Submissions are processed in order of receipt, then by ID, so the same inputs give
  the same outputs whatever order the rows are in.
- Names match only when one name's words contain the other's and at least two words
  agree. A surname alone, or a person signing for a trust or LLC, goes to review.
- There is no language model in this build. The "objection-like wording" flag is a
  keyword list in `rules.json`. It only routes letters to a person.

## Legal numbers are data

`rules.json` holds every number and rule the engine uses, each with its source, a
short quote, and a status. All entries the engine relies on were read on
leginfo.legislature.ca.gov on 2026-11-25. Two case citations are marked
`not_verified` and are not used by the code; a test enforces that.

Things that are agency policy, not statute, are kept apart under
`agency_policy_defaults`: which delivery channels count as written, whether a
signature is required, whether withdrawals are accepted, and the test for an
eligible tenant.

## Open questions for an attorney

- Whether one unanswered timely objection defeats the exhaustion bar. The statute
  says the requirement "applies only if the local agency does all of the following"
  and also that there is no independent cause of action over the adequacy of a
  response (§ 53759.1(c), (e)). The gate is an internal control and takes no position.
- Whether a protest letter that states legal grounds counts as a "written objection".
- Co-owner assessment ballots when only some co-owners return one (§ 53753(e)(3)).
- Weekend and holiday roll-forward for the 120-day date.
- The eligible-tenant test, and who may sign for a trust, LLC, or public owner.
- Day counting for the 45-day periods (the engine uses a plain calendar-day difference).

See `CORRECTIONS.md` for where the source research report differed from the text.
