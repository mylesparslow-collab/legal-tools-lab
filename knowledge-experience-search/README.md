# Knowledge and experience search

**Personal portfolio demo. All data is synthetic: every client, lawyer, matter and document is invented. Not legal advice. This has never been run against a real document system and must not be pointed at one until the steps in `SWAP_IN_REAL_DATA.md` are done.**

A search tool for a firm that has opened new offices, where new lawyers do not know where the precedents are. It answers two questions:

- "Show me our best prior example of X" (document search).
- "Who here has done X" (experience finder).

Every query runs as a specific person and reads only what that person may open. The permission rules are the firm's own data (who is on a restricted matter, who an ethical wall excludes); this tool applies them and decides nothing about who should be walled from what.

## Run it

Python 3, standard library only. No network access is used.

```
python run_demo.py            # build the index, write sample outputs to output/
python run_demo.py --serve    # the same, then a local web UI on http://127.0.0.1:8765
```

Or open `output/demo.html` directly: a static snapshot of prepared queries that needs no server.

Command line:

```
python -m kx index                                   # build or update the index
python -m kx index --permissions-only                # refresh people, groups, grants, walls only
python -m kx search --user U102 --explain earn-out provisions agreement
python -m kx search --user U102 '"forum selection clause" type:motion filed:yes'
python -m kx who --user U102 loan workout
python -m kx audit verify | report | tail
python -m kx eval                                    # score against the synthetic answer key
```

Tests: `python -m pytest -q` (pytest is the only thing outside the standard library, and only for tests).

## What it does

**Search.** Keywords, quoted phrases and field filters (`type:` `practice:` `mtype:` `jurisdiction:` `industry:` `author:` `office:` `after:` `before:` `year:` `filed:` `model:` `final:`). All terms are required; if no document has every term, it falls back to documents with some of them and says so. Results carry a snippet, filter counts, and an optional explanation of the rank.

**Ranking.** BM25 over three fields (title, body, and metadata such as document type, practice, matter type and court), blended with precedent-quality signals. Weights are in `config/ranking.json`, not in code:

| Part of the score | Weight | Value |
|---|---|---|
| Text match | 0.60 | BM25 divided by the best BM25 among your results |
| Marked as a model form | 0.14 | 0 or 1 |
| Final version | 0.08 | 0 or 1 |
| Was filed | 0.06 | 0 or 1 |
| Reuse count | 0.07 | log scale, capped at 20 |
| Recency | 0.05 | halves every 4 years |

`--explain` (or "Why this ranked here" in the UI) shows each term's matches by field and each signal's contribution. They add up to the score.

**Versions and near-duplicates.** Drafts fold into the final version. Lightly edited copies of the same document on other matters fold into the highest-ranked copy. Both are done at query time, over the documents you can see.

**Experience finder.** People ranked by matching matters: role (lead or support), recency, and recorded hours, with the matters listed as evidence. A matter matches on its type or practice, then on its description, then on the titles of its documents. People who have left the firm are flagged, not hidden. Someone with one matter or under 15 hours is labelled "thin evidence" and given no rank. If fewer than three matters match, nobody is ranked: the people are listed by name as leads to ask.

**Audit log.** Every search and every "who" query is written to a hash-chained JSON-lines log with user, time, query, filters and the ids returned. If the log cannot be written, no results are returned. `python -m kx audit report` lists queries that found nothing or only partial matches: the knowledge lawyer's to-do list.

## Permissions

Rules, in `kx/acl.py`:

1. The asker must be a known, active person. Otherwise nothing is visible.
2. A matter is visible only if its security is exactly "public" or "restricted" and its permission data is complete.
3. A restricted matter needs a grant to the person or to a group they belong to.
4. An ethical wall exclusion removes the matter for that person and beats every grant.
5. A document inherits its matter's security.

The filter is part of every retrieval query. Rows the asker cannot see are never fetched, so nothing can be derived from them afterwards. The design test is **noninterference**: a person's output must be identical, byte for byte, to what they would get from an index that never contained the documents they cannot see. `tests/test_noninterference.py` checks exactly that on the full corpus for a user behind each of the three walls.

Leak channels with explicit tests:

| Channel | How it is closed |
|---|---|
| Results and snippets | Only visible rows are fetched |
| Result counts | Counted after filtering; there is no "more results hidden" figure |
| Filter (facet) totals and values | Computed from the visible result set |
| Autocomplete | Terms come only from titles and metadata of visible documents |
| Ranking statistics | Document count, document frequencies and average lengths are computed over the asker's visible set at query time, so a term that exists only behind a wall cannot move any score |
| "All terms, else any term" fallback | Decided on the visible set, so it triggers exactly as if the hidden term did not exist |
| Near-duplicate and version folding | Run over visible results only; a hidden copy is neither listed nor counted, and never swallows a visible one |
| Experience finder | Only visible matters count: no credit, hours, dates or listing from a walled matter |
| Empty-result wording | Identical for a walled term and a term that exists nowhere |
| Unknown or departed asker | Empty answer, no detail |
| Optional reranker | Receives permitted documents only |
| Audit entries | List only ids the asker was shown |

Failing closed: unknown or blank security, a wall that does not say who is excluded, a wall naming a person the directory does not know, a document whose matter is missing, a document with its own security setting, a person with an unrecognised status, a failed or partial permission read (the whole sync rolls back), and an optional maximum age for the permission snapshot (`acl_max_age_hours`, off in the demo because the data is static).

Permission changes: permission tables are separate from the index. `python -m kx index --permissions-only` (or `Indexer.sync_permissions`) applies a new wall and the next query honours it. No document is re-indexed. See `output/wall_goes_up.txt`.

**Timing is out of scope.** A walled user's query does less work than an unwalled one, and no attempt is made to hide that. The audit log is the control for someone probing.

## Retrieval quality, honestly

Measured against `data/synthetic/ANSWER_KEY.json`, as a new associate with no special access. Precision at 5 is the share of the first five results that are relevant; recall at 10 is the share of relevant documents found in the first ten.

| Queries | Count | Precision at 5 | Recall at 10 |
|---|---|---|---|
| In the corpus's own vocabulary | 31 | 0.91 | 0.959 |
| In different vocabulary | 6 | 0.067 | 0.071 |
| All | 37 | 0.773 | 0.815 |

By type: topic and document type 0.914 / 0.976 (14 queries); topic with a type filter 1.0 / 0.983 (6); exact phrase 0.8 / 0.875 (5); best example 0.9 / 0.967 (6). On the six "best example" queries the planted model form ranked first five times; the sixth time it was not returned at all, because its text lacks one of the query words and all words are required.

Read these numbers with care:

- The answer key and the documents come from the same generator. "Relevant" means the document's main topic and type are the ones the query was built from. This shows the pipeline works. It says little about real documents.
- The synthetic vocabulary is small (about 1,000 distinct terms) and tidy. Real document text is neither.
- The "different vocabulary" row is the real warning. Six queries describe a topic in words the documents do not use, and keyword search finds almost nothing. That is the case semantic ranking is for, and it is not built here.

Full per-query results: `output/retrieval_quality.json`.

## Where semantic ranking would plug in

There is no language model and no embedding index. `kx/rerank.py` defines an optional reranker interface, off by default. `search()` calls it only after permission filtering and folding, and passes it only the top permitted documents, so a reranker can reorder a permitted list but cannot widen access. A retrieval stage based on embeddings would need its own permission filter inside the nearest-neighbour query; that is a larger change and is not attempted.

## What is tested

174 tests, all passing (`python -m pytest -q`):

- Permission rules, each fail-closed case, and agreement between the SQL filter and a separate plain-Python statement of the rules for all 120 people and 250 matters.
- One test per leak channel in the table above, on a small hand-built world, plus whole-corpus noninterference for search, autocomplete and the experience finder.
- The answer key's wall and restricted-matter checks: documents that must never appear for given users, with a control user who does see them.
- Permission changes taking effect on the next query with postings untouched.
- A structural check that every statement in the query modules that reads documents, postings, edges, teams or time records includes the visibility filter.
- Index: incremental update, changed documents, tombstones, full reconcile, matter removal, metadata changes, rollback on a failed sync, near-duplicate detection against the planted pairs.
- Search: ranking, phrases, filters, facets, fallback, explain adding up, each quality signal, config weights, folding, pagination, reranker.
- Experience finder: role, recency, hours cap, departed flag, thin evidence, too-few-matters behaviour.
- Audit: chain verification, edits, removals, reordering, a forged single hash, the report, and "no log, no results".
- Mapping file and source adapter: code translation, unknown codes, rejected rows, missing permission files, cursor and tombstones.
- CLI and the local server (loopback only, self-contained page, JSON errors).
- The quality numbers above: the test fails if this README and a fresh run disagree.

The leak tests were checked by breaking the code on purpose (for example computing document frequencies over the whole corpus, or dropping the filter from autocomplete, near-duplicate edges, hours or teams). Each break was caught.

## What is not done

- **No real system has been connected.** There is one adapter, for the synthetic files. No vendor API or export format is implemented or claimed. `SWAP_IN_REAL_DATA.md` lists what a real adapter must supply and what to ask IT.
- **Document-level security is not modelled.** Documents inherit matter security. A document that carries its own security setting is refused, not guessed at.
- **Only exclusion walls.** A wall here is a list of people excluded from matters. Other wall designs (for example inclusion-only teams) would be expressed as restricted matters, and that mapping is untested.
- **The user switcher is a demo device.** The web server takes the user from the request. A real deployment must take it from the firm's sign-in. The server has no authentication and binds to 127.0.0.1 only.
- **Timing side channels** are not addressed (see above).
- **The audit chain detects edits, removals and reordering, not removal of the newest entries or replacement of the whole file,** unless the latest hash is also kept somewhere else. The log itself contains queries and result ids and needs its own access control. Autocomplete keystrokes are not logged.
- **Reuse count is taken from the source as given.** If a real system computes it across all matters, it could hint that a walled matter reused a document. Ask how it is derived before using it.
- **Scale.** Statistics are computed per query over the visible set. That takes about 17 ms a query at 1,500 documents on the build machine and has not been measured at firm scale; a large corpus would need cached statistics per permission group, with the same guarantee re-tested.
- **Language.** English only, plural folding only, no synonyms, no spelling correction, no negation operator, one value per filter.
- **Near-duplicate detection** found 29 of the 30 planted pairs here; its threshold (0.6) has not been tuned on real documents.
- **The zero-result report** cannot tell "the firm has nothing on this" from "this user may not open it", and does not try.

## Layout

```
kx/            acl.py (permissions), index.py, search.py, experience.py, audit.py,
               rerank.py (optional interface), service.py, server.py, evaluate.py,
               __main__.py (CLI), web/app.html
sources/       base.py (the adapter interface), mapping.py, synthetic_files.py, memory.py
config/        ranking.json (weights), mapping.synthetic.json (source columns to canonical fields)
synth/         seeded corpus generator and vocabulary
data/synthetic the generated corpus, ANSWER_KEY.json, manifest.json
output/        sample outputs written by run_demo.py
tests/         pytest suite
SWAP_IN_REAL_DATA.md
```

The corpus: 1,500 documents across 250 matters, 10 practices, 8 offices and 120 people (6 departed), with 3 ethical walls covering 4 matters, 15 restricted matters, 128 draft families and 30 planted near-duplicates. Seeded, so `python -m kx generate` reproduces it exactly.
