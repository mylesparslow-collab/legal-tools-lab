# Swapping in real data

**Status: not done. This tool has only ever read the synthetic files in `data/synthetic`. Nothing here was written against a real document system, and no compatibility with any product is claimed.** I had no access to any vendor's API documentation or export format when building this, so there is deliberately no connector written from memory.

This note says what a real adapter must supply, what the permission semantics must be, and what to ask IT before any test at the firm.

## What changes and what does not

All source access is behind one interface: `sources/base.py`, class `SourceAdapter`. To test on a real system:

1. Write one new subclass of `SourceAdapter` (a file export reader first; a live API later, if at all).
2. Write a mapping file like `config/mapping.synthetic.json` that maps the source's column names and codes to the canonical fields. Mapping is JSON, not code.
3. Change nothing in `kx/`. If something in `kx/` has to change, that is a finding to write down, not a quick patch.

Start with a read-only export to files on a firm machine. Do not start with a live connection.

## The six things an adapter must return

Canonical records are defined in `kx/schema.py`.

### 1. `people()`

| Field | Meaning | Notes |
|---|---|---|
| `person_id` | The identifier used in permission data and time records | Must be the same id everywhere. If the systems use different ids, the adapter does the join, and unmatched people are a finding |
| `name`, `office`, `practice`, `title` | Display only | |
| `status` | `active` or `departed` | Anything else cannot search. Departed people must be included so their work stays findable |

### 2. `matters()`

| Field | Meaning | Notes |
|---|---|---|
| `matter_id` | Stable matter identifier | |
| `name`, `client_id`, `client_industry`, `practice`, `matter_type`, `jurisdiction`, `office`, `opened`, `closed`, `description` | Metadata for filters, facets and the experience finder | Dates as `YYYY-MM-DD`. Practice, matter type, jurisdiction and industry are also searchable text |
| `security` | Exactly `public` or `restricted` | Map the source's codes in the mapping file. **Do not give this field a default.** An unmapped or blank value hides the matter from everyone, which is the intended behaviour |

### 3. `permissions()`: one complete snapshot

Returns group membership, grants and walls together.

| Part | Fields | Semantics the tool assumes |
|---|---|---|
| Group membership | `(group_id, person_id)` | Flat. If the source has nested groups, the adapter must expand them fully |
| Grants | `matter_id`, `principal_type` (`user` or `group`), `principal_id` | A grant gives read access to every document in a restricted matter. Grants on public matters are harmless |
| Walls | `wall_id`, `matter_ids`, `excluded_person_ids` | The named people cannot see the named matters. This beats every grant and public access |

Rules for the adapter:

- **Complete or raise.** If any part cannot be read, raise `SourceError`. The sync rolls back and the last complete snapshot stays in force. Never return a partial snapshot: a missing row could be the one that excludes someone.
- **Unknown is not empty.** If a wall exists but the source does not say who is excluded, return `excluded_person_ids=None`. The matters are then hidden from everyone until it is fixed.
- A wall that names a person the people list does not contain also hides its matters from everyone, and is reported.
- Only "read" access matters here. If the source distinguishes view, edit and full control, map anything that includes viewing content to a grant, and settle with IT what "can see the profile but not the content" should mean (the cautious answer is: not visible).

### 4. `matter_team()`

`matter_id`, `person_id`, `role` (`lead` or `support`). Used only by the experience finder.

### 5. `time_entries()`

`entry_id`, `matter_id`, `person_id`, `work_date`, `hours`. Narratives are not read and should not be exported.

### 6. `document_changes(cursor)`

Returns documents added or changed since the cursor, ids deleted since the cursor, and a new cursor.

| Field | Meaning | Notes |
|---|---|---|
| `doc_id` | Unique per version | If the source has one number with many versions, combine number and version |
| `matter_id` | The matter whose security the document inherits | A document with no matter is rejected |
| `title`, `body` | Text | The adapter is responsible for text extraction. Scanned documents with no text layer will be findable by title only |
| `doc_type` | One of: brief, motion, agreement, memo, staff report, opinion letter, checklist, form, other | Map the source's classes in the mapping file |
| `author_id`, `doc_date` | | |
| `family_id`, `version_no`, `is_final` | Version family | All versions share `family_id`. If the source has no "final" flag, decide a rule with the knowledge lawyer (for example, the latest version) and say so |
| `was_filed`, `model_form`, `reuse_count` | Precedent-quality signals | Each only ever raises rank. If a signal does not exist in the source, leave it false or zero and set its weight to 0 in `config/ranking.json` |
| `modified` | Source change stamp | Used for the cursor |
| `security_override` | Empty or `inherit` if the document simply inherits its matter's security | **Anything else and the document is refused.** See the first question below |

## Incremental sync and deletions

- The synthetic adapter uses a "changed at or after" stamp as its cursor and relies on content hashes to skip unchanged documents. That is safe against equal stamps but not against clock skew or backdated changes. A real adapter should use whatever change feed or sequence number the source offers, if it has one.
- **Deletions must arrive.** Either the source reports deleted ids, or a periodic full sync (`python -m kx index --full`) reconciles: anything the source no longer lists is removed. A deleted document that stays searchable is a leak of its own kind.
- **A document that moves to another matter** changes whose security it inherits. It must come through as a change. Test this explicitly.
- **Permission changes do not come through the document feed.** Run `python -m kx index --permissions-only` on its own schedule. How often is a decision for the firm; the interval is the longest time a new wall can go unhonoured. Set `acl_max_age_hours` in `config/ranking.json` so that search stops answering if the snapshot gets older than that.
- A matter that disappears from the source is removed with its documents.

## Questions for IT, before any test

Security model:

1. Can a document have security different from its matter (private documents, a restricted folder inside an open matter)? How common is it? This tool refuses such documents today; if they are common, the model needs document-level rules before a test means anything.
2. How are ethical walls represented: as a list of excluded people, as an inclusion-only team, or both? Is there a separate wall or information-barrier product, and is it the source of truth or the document system?
3. Is there a "deny" entry on individual matters or documents apart from walls? Does deny beat allow everywhere?
4. Are groups nested? Are there dynamic groups (everyone in an office, everyone in a practice) that are computed, not stored?
5. What does the default security of a new matter look like before anyone sets it? (It must not map to "public" by accident.)
6. Are there users with override or administrator rights? Search should not honour those; confirm they can be excluded from the export.
7. What identifier links a person across the document system, the wall data, and the time system?

Getting the data:

8. Is there a supported bulk export of documents with text, or only an API? Who approves its use, and where may the export sit?
9. Is there a change feed or sequence number for documents? For permissions? How are deletions and matter moves reported?
10. How quickly must a new wall take effect in search? That sets the permission sync interval.
11. Where do time records and matter team roles come from, and can they be exported without narratives?
12. How is extracted text obtained for scanned or image-only documents?

Signals:

13. Is there a flag for "filed", "final" or "model form", or a folder or naming convention that stands in for one? Who maintains it?
14. If a reuse count exists, how is it derived? If it counts use across all matters, it may hint at walled work and should stay switched off.

Running it:

15. Where would the index and the audit log live, who can read each, and how long is the audit log kept? Both contain confidential material: the index holds document text, and the log holds what people searched for.
16. How will the search identify the user? It must come from the firm's sign-in, never from a parameter.

## A first test at the firm, in order

1. Export a small, deliberately chosen set: a few open matters, one restricted matter, one walled matter, with real permission data. Get this choice approved by whoever owns walls.
2. Write the adapter and mapping. Run `python -m kx index` and read the report: every rejected document, every permission warning and every matter "hidden from everyone" needs an explanation.
3. Before anyone searches, compare `kx.acl.visible_matter_ids` for a handful of named people with what the document system itself shows them. Any difference stops the test.
4. Repeat the noninterference check with a walled test account: build a second index from the same export with everything that account cannot see left out, and compare outputs. `tests/test_noninterference.py` shows the method; its fixtures are written for the synthetic corpus and need adapting to the real export.
5. Put a wall up on a test matter, run the permissions-only sync, and confirm the next query honours it.
6. Only then look at ranking quality, with a knowledge lawyer writing the expected answers.
