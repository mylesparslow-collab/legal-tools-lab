# Knowledge and experience search

**Personal portfolio demo. All data is synthetic: every client, lawyer, matter and document is invented. Not legal advice. This has never been run against a real document system and must not be pointed at one until the steps in `SWAP_IN_REAL_DATA.md` are done.**

A search tool for a firm that has opened new offices, where new lawyers do not know where the precedents are. It answers two questions:

- "Show me our best prior example of X" (document search).
- "Who here has done X" (experience finder).

Every query runs as a specific person and reads only what that person may open. The permission rules are the firm's own data (who is on a restricted matter, who an ethical wall excludes); this tool applies them and decides nothing about who should be walled from what.

## Headline result

Queries written by an independent author who had not seen the code, scored once on a sealed batch (`heldout/batch_b`, 30 document queries, run as a new associate):

| Sealed batch B, run once | Queries | Precision at 5 (listed) | Precision at 5 (listed or same subject) | A listed document in the top 10 |
|---|---|---|---|---|
| In the documents' own words | 10 | 0.9 | 0.98 | 10 of 10 |
| In different words | 20 | 0.35 | 0.45 | 11 of 20 |

So: when a lawyer uses the documents' own terms, the right precedents come up. When they describe the subject in other words, a listed document reaches the first ten a little over half the time. That is much better than keyword search alone and still not good enough to rely on. Details, and the three other numbers this should be read against, are under "Retrieval quality, honestly".

Permission checks through the command line and through the web server found no way for an excluded person to see, count or infer walled material. One real leak in the earlier web page was found and fixed (see "Web route and sign-in").

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
python -m kx search --user U102 --no-expand lessor consent   # exact words only
python -m kx eval                                    # score against the synthetic answer key
python -m kx heldout --batch heldout/batch_a --out result.json   # score a held-out batch
python -m kx timing                                  # per-query time, expansion on and off
```

`--user` on the command line is an operator's tool. The web UI does not take a user from the request; see "Web route and sign-in".

Tests: `python -m pytest -q` (pytest is the only thing outside the standard library, and only for tests).

## What it does

**Search.** Keywords, quoted phrases and field filters (`type:` `practice:` `mtype:` `jurisdiction:` `industry:` `author:` `office:` `after:` `before:` `year:` `filed:` `model:` `final:`). A document must cover at least half the query, with words weighted by how rare they are among the documents the asker can open; documents matching the whole query score highest and partial matches are marked. A quoted phrase is always required. A word found in no document the asker can open is dropped and named in the response. (`"match_mode": "all"` in `config/ranking.json` gives strict all-words matching instead.) Results carry a snippet, filter counts, and an optional explanation of the rank.

**Different wording.** A vocabulary-bridging layer (`kx/expand.py`) looks for documents that use other words for the same thing. Each word or phrase in the query becomes a group of alternatives, and a document satisfies the group through any one of them:

| Source | Weight | What it is |
|---|---|---|
| Your own words | 1.0 | |
| Spelling | 0.9 | British and American endings, by rule (labour, labor) |
| Word form | 0.8 | Other forms of the word that occur in the index (assign, assignment, assigning) |
| Typo | 0.7 | A near-miss spelling, tried only when your word is in no document you can open. One letter dropped, added or swapped; one changed letter only in words of eight letters or more; two edits only from ten letters |
| Thesaurus | 0.6 | `config/thesaurus.json`: curated legal and plain-language equivalents, abbreviations and spellings |
| Thesaurus, loose | 0.5 | A thesaurus phrase recognised with the words in another order or with a listed equivalent of one word ("deferred price" read as "deferred consideration") |
| Related terms | 0.3 | Only when there are fewer than ten direct matches: terms that recur in your own top results. Documents found this way are always listed after every direct match, at most ten |

An alternative never counts for more than your own word would: its rarity is capped at your word's. The response lists every alternative that was used and why, the explanation shows it per result, and `--no-expand` (or the tick box in the page, or `expand=off`) turns the whole layer off for one query. Weights are in `config/ranking.json`. See `output/different_wording_example.txt`.

The thesaurus is data, not code: 446 groups, general English and general legal vocabulary, no citations. It should be owned by the firm's knowledge lawyers, who add the firm's own terms of art from the zero-result report. It must never hold client names, matter names or code names, because it is the same for every user. A latent-semantic or embedding space was considered and not built: learned from all documents it would let hidden documents shape a user's results, and learned per visible set it is too heavy for this demo.

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

**Experience finder.** People ranked by matching matters: role (lead or support), recency, and recorded hours, with the matters listed as evidence. A matter matches on its type or practice, then on its description, then on the titles of its documents. People who have left the firm are flagged, not hidden. The same bridging layer applies, matched against each matter's own text. Someone with one matter or under 15 hours is labelled "thin evidence" and given no rank. If fewer than three matters match, the response says that is too little to rank on; the people are still listed in order of recorded involvement, as leads to ask.

**Audit log.** Every search, every "who" query and every document opened is written to a hash-chained JSON-lines log with user, time, query, filters and the ids returned. If the log cannot be written, no results are returned. `python -m kx audit report` lists queries that found nothing or only partial matches: the knowledge lawyer's to-do list.

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
| Matching, dropped words and partial matches | Decided on the visible set, so a word that exists only behind a wall is treated exactly like a word that exists nowhere |
| Thesaurus, word forms, spellings | Candidates come from static data or the term list; one is used, counted, weighted or shown only if it occurs in a document the asker can open |
| Typo correction | Only spellings that occur in the asker's visible documents are candidates, and the choice among them uses visible counts |
| Related terms | Taken from the asker's own top results and scored with visible-set statistics; a term that sits next to the query only behind a wall is never suggested or used |
| Reading a thesaurus phrase as separate words | Triggered only by what the asker can open |
| Web route | Every endpoint, header, length and error compared byte for byte against a server whose index never held the hidden material |
| Document by id | The lookup itself is permission-filtered; "you may not open it" and "it does not exist" are the same bytes |
| Near-duplicate and version folding | Run over visible results only; a hidden copy is neither listed nor counted, and never swallows a visible one |
| Experience finder | Only visible matters count: no credit, hours, dates or listing from a walled matter |
| Empty-result wording | Identical for a walled term and a term that exists nowhere |
| Unknown or departed asker | Empty answer, no detail |
| Optional reranker | Receives permitted documents only |
| Audit entries | List only ids the asker was shown |

Failing closed: unknown or blank security, a wall that does not say who is excluded, a wall naming a person the directory does not know, a document whose matter is missing, a document with its own security setting, a person with an unrecognised status, a failed or partial permission read (the whole sync rolls back), and an optional maximum age for the permission snapshot (`acl_max_age_hours`, off in the demo because the data is static).

Permission changes: permission tables are separate from the index. `python -m kx index --permissions-only` (or `Indexer.sync_permissions`) applies a new wall and the next query honours it. No document is re-indexed. See `output/wall_goes_up.txt`.

**Timing is out of scope.** A walled user's query does less work than an unwalled one, and no attempt is made to hide that. The audit log is the control for someone probing.

## Web route and sign-in

The page no longer sends a user id with a query. A small sign-in step (`POST /api/signin`) issues an opaque random token in an `HttpOnly`, `SameSite=Strict` cookie; the server keeps the mapping from token to person (`kx/session.py`, eight-hour expiry, sign-out revokes it) and reads the asker from that mapping and nowhere else. A `user` parameter or header on a request is ignored. **The sign-in step itself is a demo user picker standing in for the firm's single sign-on**: anyone who can reach the page can pick anyone. A pilot replaces the picker with a call from the firm's identity provider and keeps the rest. The server still binds to 127.0.0.1 only.

Endpoints: `/` (the page), `/api/meta` (the directory for the picker), `/api/signin`, `/api/signout`, `/api/search`, `/api/who`, `/api/suggest`, `/api/document`. There is no endpoint that returns a matter.

`tests/test_http.py` starts the real server on an ephemeral port and repeats the noninterference check through every endpoint: for each wall's excluded user, about 300 requests (913 across the three walls) are sent to a server over the full index and to a server over an index that never held anything that user cannot see. Status, headers, length and body must be identical. It also covers a missing, forged or expired session, a departed person, attempts to name another user, every hidden document requested by id, other spellings and routes to a document id, guessed endpoints, malformed input, other methods, and requests addressed to another host name.

What those tests found in the earlier version:

1. **A real leak.** The page data served to every user (`/api/meta`) named the walled matter. A demo user's label read "Walled from Project <code name>", and the example queries included "project <code name>". The excluded person was shown the name of the matter they are walled from. The byte comparison alone would not have caught this, because both servers served the same static text; a separate scan of every response for the walled code names did. Labels and example queries are now neutral, and a test keeps them so.
2. **The asker was a URL parameter.** Any user could edit it. Replaced by the session above.
3. **No document-by-id route existed**, so there was nothing to get wrong; the one added now (`/api/document`, used by "Full text" in the page) is filtered and audited.
4. **Hardening gaps, not leaks:** the server answered requests addressed to any host name (now refused unless 127.0.0.1 or localhost, which blocks DNS rebinding); the `Server` header gave the Python version; a non-numeric `limit` was not checked explicitly; a POST got the library's default HTML error page. All fixed and tested.

Through search, explain, facets, autocomplete, the experience finder and document fetch, the excluded users' responses were already byte-identical.

## Retrieval quality, honestly

Four measurements, in the order they were taken. Precision at 5 counts a result as correct only if the test author listed it. The lists are hand-judged samples capped at ten, so an unlisted result is unjudged, not wrong; the second figure also counts documents the author marked as on the same subject. No recall is computed on the held-out batches.

Different-wording queries only:

| | Queries | Precision at 5, listed | Listed or same subject | A listed document in the top 10 | What it is |
|---|---|---|---|---|---|
| 1. Earlier version, keyword search | 6 | 0.067 | | | The six different-vocabulary queries in the synthetic key (recall at 10 was 0.071). Seen queries. |
| 2. Batch A, first run | 20 | 0.46 | 0.55 | 14 of 20 | Unseen queries, first contact, before any change. Keyword search alone on the same batch: 0.11, 0.13, 6 of 20. |
| 3. Batch A, after fixes | 20 | 0.73 | 0.9 | 20 of 20 | **Fitted.** The fixes were made by looking at these queries' failures. Not evidence of quality. |
| 4. Batch B, run once at the end | 20 | 0.35 | 0.45 | 11 of 20 | **The honest figure.** Sealed until every change was finished. Nothing was changed afterwards. |

Queries in the documents' own words: batch A 0.7 / 0.96 / 10 of 10 at first run and 0.7 / 0.94 / 10 of 10 after fixes; batch B 0.9 / 0.98 / 10 of 10. "Who has done this" queries: batch A 4 of 6 with every expected first person in the top three at first run, 6 of 6 after fixes; batch B 5 of 6, with 15 of 18 expected people in the top five.

Row 4 is lower than row 2. The changes made between them did not carry over to new topics: most of the batch A gain came from thesaurus entries prompted by batch A's own misses. Read row 3 as a warning about how easily this kind of layer is fitted, and row 4 as what a lawyer with a new question should expect.

What was changed after the batch A first run, all of it general and none of it a query's own wording:

- Typo correction no longer turns one real word into another (parent into patent, majority into minority).
- "-ory" is no longer treated as a word ending (it merged invention with inventory).
- A thesaurus phrase with no visible match is read as separate words instead of failing as a whole.
- Matching changed from all-words-required to the weighted rule described above.
- More prepositions are ignored as filler (against, between, into and others).
- The experience finder puts people in order of involvement even when fewer than three matters match, with the warning kept.
- 62 thesaurus groups were added: 21 plain-language equivalents prompted by specific misses and 41 abbreviations added as a class. Every one is listed in `output/thesaurus_entries_added_after_batch_a.json` and marked in `config/thesaurus.json`.

A disclosure about the thesaurus: it was written from general knowledge, but by the same hand that wrote the synthetic vocabulary, and some of its phrases are the corpus's own (for example "timekeeping records", "vendor security assessment", "charitable planning"). The held-out queries were written by someone else, which is why they, not the synthetic key, are the test.

On the synthetic key (`data/synthetic/ANSWER_KEY.json`, same generator as the documents; recall is meaningful here because the key is complete):

| Queries | Count | Precision at 5 | Recall at 10 |
|---|---|---|---|
| In the corpus's own vocabulary | 31 | 0.91 | 0.96 |
| In different vocabulary | 6 | 0.267 | 0.262 |
| All | 37 | 0.805 | 0.847 |

Keyword only, different vocabulary: 0.0 / 0.0. (The earlier version scored 0.067 / 0.071 on these six; the difference is that partial matches on one common word are no longer returned.) On the six "best example" queries the planted model form ranked first five times.

Per-query results: `output/heldout_batch_a_first_run.json`, `output/heldout_batch_a_keyword_only.json`, `output/heldout_batch_a_after_fixes.json`, `output/heldout_batch_b_final.json`, `output/retrieval_quality.json`, `output/retrieval_quality_keyword_only.json`. A recorded run is never overwritten by the scorer.

**Time per query** with bridging on, 1,500 documents, on the build machine: median 12.3 ms, 95th percentile 24.9 ms, slowest 43.3 ms (off: 8.2, 15.0, 26.5). `python -m kx timing` repeats it.

**Still weak** (seen in batch B after the run; listed, not fixed):

- Lay descriptions of a concept with none of its terms ("someone to manage my affairs if I lose capacity", "forcing the case out of court to a private arbitrator"). A thesaurus cannot reach these.
- Three batch B queries returned nothing: several words matched, each in different documents, and no document covered half the query. The weighted rule needs a fallback to the best partial matches.
- Word-form matching still merges unrelated words ("probe" was read as a form of "probate", "rest" as "restatement").
- Typo correction still changed a real word once ("properly" to "property").
- The thesaurus helps only where someone has thought of the equivalence in advance. Coverage outside the areas it lists is thin.
- The experience finder does not yet split a thesaurus phrase back into words when the phrase matches nothing.
- A generic word left over after the others are dropped ("agreement", "company") can still produce a list of loosely related documents; the response says which words were found, but the list is not useful.

## Where semantic ranking would plug in

There is no language model and no embedding index. `kx/rerank.py` defines an optional reranker interface, off by default. `search()` calls it only after permission filtering and folding, and passes it only the top permitted documents, so a reranker can reorder a permitted list but cannot widen access. A retrieval stage based on embeddings would need its own permission filter inside the nearest-neighbour query; that is a larger change and is not attempted.

## What is tested

218 tests, all passing (`python -m pytest -q`):

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
- CLI and the page (self-contained, no external requests).
- The web route (`tests/test_http.py`): everything listed under "Web route and sign-in".
- Vocabulary bridging (`tests/test_expansion.py`): each source, weights below the user's own words, the explanation, the per-query switch, and a leak test per source, including a term that co-occurs with the query only inside walled documents and exists in an open document elsewhere.
- The held-out scorer, on a made-up batch.
- The quality numbers above: the test fails if this README and a fresh run disagree.

The leak tests were checked by breaking the code on purpose (for example computing document frequencies over the whole corpus, dropping the filter from autocomplete, near-duplicate edges, hours or teams, letting typo candidates or thesaurus alternatives through without a visible occurrence, reading the user from a URL parameter, fetching a document by id without the filter, answering 403 instead of 404 for a hidden document, or putting a code name back in the example queries). Each break was caught. One caution: some filters are applied twice in the code, so a single removed filter does not always fail a test; the document-by-id check was confirmed by removing both.

## What is not done

- **No real system has been connected.** There is one adapter, for the synthetic files. No vendor API or export format is implemented or claimed. `SWAP_IN_REAL_DATA.md` lists what a real adapter must supply and what to ask IT.
- **Document-level security is not modelled.** Documents inherit matter security. A document that carries its own security setting is refused, not guessed at.
- **Only exclusion walls.** A wall here is a list of people excluded from matters. Other wall designs (for example inclusion-only teams) would be expressed as restricted matters, and that mapping is untested.
- **Sign-in is a demo picker.** Sessions are real (server-side, opaque cookie), but the step that decides who you are is a menu. It stands in for the firm's single sign-on and proves nothing about identity. Sessions live in memory and end when the server stops. The server binds to 127.0.0.1 only and has no TLS.
- **Timing side channels** are not addressed (see above).
- **The audit chain detects edits, removals and reordering, not removal of the newest entries or replacement of the whole file,** unless the latest hash is also kept somewhere else. The log itself contains queries and result ids and needs its own access control. Autocomplete keystrokes are not logged.
- **Reuse count is taken from the source as given.** If a real system computes it across all matters, it could hint that a walled matter reused a document. Ask how it is derived before using it.
- **Scale.** Statistics are computed per query over the visible set. That takes about 12 ms a query at 1,500 documents on the build machine with bridging on and has not been measured at firm scale. Typo correction scans the term list and would need an index of its own on a large vocabulary; a large corpus would need cached statistics per permission group, with the same guarantee re-tested.
- **Language.** English only. Synonyms come only from the curated thesaurus; word-form and typo handling are crude (see "Still weak"). No negation operator, one value per filter.
- **No semantic model.** There is no embedding or language model. Batch B shows what that costs on lay descriptions.
- **Near-duplicate detection** found 29 of the 30 planted pairs here; its threshold (0.6) has not been tuned on real documents.
- **The zero-result report** cannot tell "the firm has nothing on this" from "this user may not open it", and does not try.

## Layout

```
kx/            acl.py (permissions), index.py, search.py, expand.py (vocabulary bridging),
               experience.py, audit.py, rerank.py (optional interface), service.py,
               session.py, server.py, evaluate.py, heldout.py (held-out scorer),
               __main__.py (CLI), web/app.html
sources/       base.py (the adapter interface), mapping.py, synthetic_files.py, memory.py
config/        ranking.json (weights), thesaurus.json (equivalents; owned by knowledge lawyers),
               mapping.synthetic.json (source columns to canonical fields)
heldout/       two batches of queries and hand-judged answers by an independent author
synth/         seeded corpus generator and vocabulary
data/synthetic the generated corpus, ANSWER_KEY.json, manifest.json
output/        sample outputs written by run_demo.py
tests/         pytest suite
SWAP_IN_REAL_DATA.md
```

The corpus: 1,500 documents across 250 matters, 10 practices, 8 offices and 120 people (6 departed), with 3 ethical walls covering 4 matters, 15 restricted matters, 128 draft families and 30 planted near-duplicates. Seeded, so `python -m kx generate` reproduces it exactly.
