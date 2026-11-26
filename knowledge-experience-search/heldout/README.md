# Held-out queries for the knowledge and experience search

Written by an independent test author on 2026-11-26. The author did not read
the search code, did not read the corpus generator or its vocabulary lists, and
did not run the tool. All data is fictional.

## The sealed-batch rule

- `batch_a/` is the working batch. Run it as often as you like, look at the
  misses, and fix weaknesses.
- `batch_b/` is sealed. Do not open `batch_b/ANSWER_KEY.json` or anything in
  `batch_b/builder/` while you are changing the tool. Run batch B once, at the
  very end, and report that score as the final figure. If the tool is changed
  after batch B has been run, the batch B score is no longer a held-out score
  and must be reported as such.

## What is in each batch

| | batch_a | batch_b |
|---|---|---|
| Document queries | 30 (HA01 to HA30) | 30 (HB01 to HB30) |
| In the documents' own words | 10 (HA01 to HA10) | 10 (HB01 to HB10) |
| In different words | 20 (HA11 to HA30) | 20 (HB11 to HB30) |
| "Who has done this" queries | 6 (WA1 to WA6) | 6 (WB1 to WB6) |
| Typos | 1 query (HA19, two misspelt words) | 1 query (HB30, two misspelt words) |
| Query with a type filter | HA10 | HB10 |
| Query with a quoted phrase | HA05 | HB05 |

The different-words queries cover synonyms, lay phrasing, British and American
variants, abbreviations, broader and narrower wording, changed word order and
typos. Each query's `variation` field says which. The two batches use
different topics for almost every query so that fixing batch A does not
directly fix batch B.

Each batch has one file, `ANSWER_KEY.json`, plus a `builder/` folder holding
the helper scripts used to list candidates for reading (kept for audit only).

All queries are to be run as `U102`, the `eval_user` of the existing key. There
are no wall tests and no restricted-matter tests in these batches.

## Key format

`queries` uses the same entry format as `data/synthetic/ANSWER_KEY.json`:
`id`, `category`, `query`, `as_user`, `topic`, `doc_type`, `relevant`. The
existing categories are reused. Extra fields, which a scorer can ignore:

- `variation`: how the query differs from the documents' wording.
- `focus_terms`: for narrower queries, the point the query is about, in the
  documents' words.
- `same_topic_not_listed`: other documents U102 can open whose main topic is
  the same but which are not in `relevant`. See "Lists are not exhaustive".
- `judged_by`: the test applied when reading.

`experience_queries` is a new section; the existing key has no equivalent.
Each entry has `query`, `as_user`, `variation`, `matter_rule` (which matters
count and why), `matters` (the matters that justify the answer), and three
lists of people, each with `lead_on`, `support_on` and `hours_recorded` on
those matters:

- `strongest`: the person or people the author would expect first.
- `should_rank_near_top`: should be in the top five.
- `also_reasonable`: fine to see in the top ten; not an error.

## How relevance was judged

By hand, before any tool run, in three steps.

1. For each query the author decided what a lawyer typing it wants, and which
   subject that corresponds to in the corpus.
2. A helper script listed the documents whose main subject is that one. The
   main subject was taken from each document's own opening sentence and body,
   not from the generator's lists. Only documents on matters with security
   code P were considered, so that every listed document is one U102 can open
   without a grant.
3. The author read the listed documents (titles and openings for all, full
   body for a sample, and all of those whose title does not name the subject)
   and kept up to ten. For queries about a narrower point, a document was kept
   only if it discusses the point as more than a passing mention. For queries
   that ask for a document type, only that type was kept. Where more than ten
   qualified, preference went to final versions over drafts, originals over
   adapted copies, and model forms and frequently reused documents.

A document counts as relevant when its main subject answers the query. A
document that only mentions the subject in passing while being about something
else was not listed.

## Lists are not exhaustive

Most subjects have more than ten relevant documents. `relevant` is capped at
ten and is a sample of the best ones, not the full set. So:

- Score **precision at 5** counting a result as correct only if it is in
  `relevant`, and separately report **whether any listed document appears in
  the top 10**.
- Treat a result that is not in `relevant` as **unjudged**, not as wrong. Do
  not compute recall against these lists.
- A lenient precision at 5 can also be reported, counting a result as correct
  if it is in `relevant` or in `same_topic_not_listed`. Report strict and
  lenient side by side; the truth lies between them. For queries with a
  `doc_type` or `focus_terms`, `same_topic_not_listed` includes documents of
  the wrong type or that barely touch the point, so lenient overstates there.
- If the tool folds drafts and adapted copies into one result, map each result
  through the `equivalents` map in `data/synthetic/ANSWER_KEY.json` before
  comparing, as the existing evaluation does. The author did not check how
  the tool folds.

For the "who" queries: score whether every `strongest` person is in the top
three and how many of `strongest` plus `should_rank_near_top` are in the top
five. A person not listed is unjudged. Matters U102 cannot open were left out
of `matters`; a person whose only experience is on such matters should not
appear for U102.

## Known soft spots in the keys

- Main subject was assigned by the author's reading aided by a script. A small
  number of documents may be assigned to a neighbouring subject.
- The ranking of people is a judgement that weighs leading a matter above
  supporting it and more hours above fewer. The split between
  `should_rank_near_top` and `also_reasonable` is the least certain part.
- Some lay queries could reasonably match a second subject (for example a
  query about sending data abroad also touches vendor contracts). Only the
  primary subject was listed; hits on the second are unjudged.
- HA05 and HB05 contain a quoted phrase. The listed documents are about the
  subject; the author did not require the exact phrase in every one.

## What the author read

Read: `README.md`; in `data/synthetic/`: `documents.jsonl`, `matters.csv`,
`people.csv`, `matter_team.csv`, `time_entries.csv`, `walls.csv`,
`wall_members.csv`, `matter_access.csv`, `group_members.csv` (for U102's
access), and the existing `ANSWER_KEY.json` (for the format; its queries,
including its different-vocabulary queries, were therefore seen and were not
reused).

Not read: anything under `kx/`, `synth/` (including `synth/vocab.py`),
`tests/`, the tool's configuration or output.

One thing to disclose: the scratch folder the author worked in already held a
search index file and an audit log written by someone else's earlier run of
the tool. The author did not use them. While checking what they were, the
author saw the index's table names and the first two lines of the audit log
(a query for a client name by another user). Nothing from them went into the
keys.
