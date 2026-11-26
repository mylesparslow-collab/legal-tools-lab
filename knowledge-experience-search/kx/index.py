"""SQLite-backed inverted index.

Tables hold canonical records, a positional inverted index over three fields
(title, body, metadata), near-duplicate edges and the permission tables.
Ranking is done in kx/search.py; this module only stores and maintains.

FTS5 is detected (``fts5_available``) but not used. Its built-in bm25() takes
document frequencies from the whole table, so a term that exists only in a
walled matter would shift the scores another user sees. The index here keeps
plain postings so that kx/search.py can compute every statistic over the
asking user's visible set.

Permission tables are separate from postings. Changing who may see a matter
never touches the postings, so a new wall is in force on the next query.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
import struct
from collections import Counter

from kx.schema import Document, PermissionSnapshot
from kx.text import root, tokenize

FIELD_TITLE, FIELD_BODY, FIELD_META = 0, 1, 2
FIELD_NAMES = {FIELD_TITLE: "title", FIELD_BODY: "body", FIELD_META: "metadata"}

SKETCH_SIZE = 64      # smallest shingle hashes kept per document
SKETCH_KEYS = 8       # of those, how many are used to find candidate pairs
SKETCH_SHARED_KEYS = 3  # candidate pairs must share at least this many keys
SHINGLE = 4           # words per shingle

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS people(
  person_id TEXT PRIMARY KEY, name TEXT, office TEXT, practice TEXT, title TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS group_members(
  group_id TEXT NOT NULL, person_id TEXT NOT NULL, PRIMARY KEY(group_id, person_id));
CREATE INDEX IF NOT EXISTS group_members_person ON group_members(person_id);
CREATE TABLE IF NOT EXISTS matters(
  matter_id TEXT PRIMARY KEY, name TEXT, client_id TEXT, client_industry TEXT, practice TEXT,
  matter_type TEXT, jurisdiction TEXT, office TEXT, opened TEXT, closed TEXT, description TEXT,
  security TEXT, acl_ok INTEGER NOT NULL DEFAULT 0, meta_hash TEXT);
CREATE TABLE IF NOT EXISTS matter_grants(
  matter_id TEXT NOT NULL, principal_type TEXT NOT NULL, principal_id TEXT NOT NULL,
  PRIMARY KEY(matter_id, principal_type, principal_id));
CREATE TABLE IF NOT EXISTS wall_exclusions(
  wall_id TEXT NOT NULL, matter_id TEXT NOT NULL, person_id TEXT NOT NULL,
  PRIMARY KEY(wall_id, matter_id, person_id));
CREATE INDEX IF NOT EXISTS wall_exclusions_lookup ON wall_exclusions(matter_id, person_id);
CREATE TABLE IF NOT EXISTS wall_incomplete(matter_id TEXT PRIMARY KEY, reason TEXT);
CREATE TABLE IF NOT EXISTS matter_team(
  matter_id TEXT NOT NULL, person_id TEXT NOT NULL, role TEXT, PRIMARY KEY(matter_id, person_id));
CREATE TABLE IF NOT EXISTS time_entries(
  entry_id TEXT PRIMARY KEY, matter_id TEXT, person_id TEXT, work_date TEXT, hours REAL);
CREATE INDEX IF NOT EXISTS time_entries_matter ON time_entries(matter_id);
CREATE TABLE IF NOT EXISTS docs(
  doc_pk INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT UNIQUE NOT NULL, matter_id TEXT NOT NULL,
  title TEXT, body TEXT, doc_type TEXT, author_id TEXT, doc_date TEXT, family_id TEXT,
  version_no INTEGER, is_final INTEGER, was_filed INTEGER, model_form INTEGER,
  reuse_count INTEGER, len_title INTEGER, len_body INTEGER, len_meta INTEGER,
  content_hash TEXT, sketch BLOB, modified TEXT);
CREATE INDEX IF NOT EXISTS docs_matter ON docs(matter_id);
CREATE TABLE IF NOT EXISTS terms(
  term_id INTEGER PRIMARY KEY, term TEXT UNIQUE NOT NULL, root TEXT);
CREATE INDEX IF NOT EXISTS terms_root ON terms(root);
CREATE TABLE IF NOT EXISTS postings(
  term_id INTEGER NOT NULL, doc_pk INTEGER NOT NULL, field INTEGER NOT NULL,
  tf INTEGER NOT NULL, positions TEXT NOT NULL,
  PRIMARY KEY(term_id, doc_pk, field)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS postings_doc ON postings(doc_pk);
CREATE TABLE IF NOT EXISTS dup_keys(
  key INTEGER NOT NULL, doc_pk INTEGER NOT NULL, PRIMARY KEY(key, doc_pk)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS near_dups(
  doc_a INTEGER NOT NULL, doc_b INTEGER NOT NULL, sim REAL NOT NULL,
  PRIMARY KEY(doc_a, doc_b)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS near_dups_b ON near_dups(doc_b);
"""


def connect(path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(str(path))
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def fts5_available(conn: sqlite3.Connection) -> bool:
    """Reported by ``kx index`` for information. The index does not use FTS5."""
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.kx_fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp.kx_fts_probe")
        return True
    except sqlite3.Error:
        return False


def _hash64(text: str) -> int:
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(),
                          "big", signed=True)


def make_sketch(tokens: list) -> list:
    """The smallest SKETCH_SIZE shingle hashes of a token list, sorted."""
    if not tokens:
        return []
    if len(tokens) < SHINGLE:
        return [_hash64(" ".join(tokens))]
    hashes = {_hash64(" ".join(tokens[i:i + SHINGLE])) for i in range(len(tokens) - SHINGLE + 1)}
    return sorted(hashes)[:SKETCH_SIZE]


def sketch_similarity(a: list, b: list) -> float:
    """Estimated Jaccard similarity of two documents from their sketches.

    Depends only on the two documents compared, never on the rest of the corpus."""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    union = sorted(sa | sb)[:min(SKETCH_SIZE, len(sa | sb))]
    both = sum(1 for h in union if h in sa and h in sb)
    return both / len(union)


def _pack(sketch: list) -> bytes:
    return struct.pack(f"<{len(sketch)}q", *sketch)


def _unpack(blob) -> list:
    if not blob:
        return []
    return list(struct.unpack(f"<{len(blob) // 8}q", blob))


def _doc_hash(doc: Document) -> str:
    payload = json.dumps([doc.doc_id, doc.matter_id, doc.title, doc.body, doc.doc_type,
                          doc.author_id, doc.doc_date, doc.family_id, doc.version_no,
                          bool(doc.is_final), bool(doc.was_filed), bool(doc.model_form),
                          doc.reuse_count], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _matter_meta_text(row) -> str:
    return " ".join(str(v or "") for v in row)


class Indexer:
    def __init__(self, conn: sqlite3.Connection, near_dup_threshold: float = 0.6, clock=None):
        self.conn = conn
        self.near_dup_threshold = near_dup_threshold
        self.clock = clock or (lambda: _dt.datetime.now(_dt.timezone.utc))
        self._terms: dict | None = None
        init_schema(conn)

    # -- small helpers -----------------------------------------------------
    def _term_id(self, term: str) -> int:
        if self._terms is None:
            self._terms = dict(self.conn.execute("SELECT term, term_id FROM terms"))
        tid = self._terms.get(term)
        if tid is None:
            tid = self.conn.execute("INSERT INTO terms(term, root) VALUES (?, ?)",
                                    (term, root(term))).lastrowid
            self._terms[term] = tid
        return tid

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT INTO meta(key, value) VALUES (?, ?) "
                          "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    def get_meta(self, key: str):
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _add_postings(self, doc_pk: int, field: int, tokens: list) -> None:
        positions: dict = {}
        for i, tok in enumerate(tokens):
            positions.setdefault(tok, []).append(i)
        self.conn.executemany(
            "INSERT INTO postings(term_id, doc_pk, field, tf, positions) VALUES (?,?,?,?,?)",
            [(self._term_id(t), doc_pk, field, len(p), ",".join(map(str, p)))
             for t, p in positions.items()])

    def _meta_tokens(self, doc_type: str, matter_id: str) -> list:
        row = self.conn.execute(
            "SELECT practice, matter_type, jurisdiction, client_industry FROM matters "
            "WHERE matter_id = ?", (matter_id,)).fetchone()
        return tokenize(f"{doc_type or ''} {_matter_meta_text(row or ())}")

    def _reindex_meta(self, doc_pk: int, doc_type: str, matter_id: str) -> None:
        self.conn.execute("DELETE FROM postings WHERE doc_pk = ? AND field = ?",
                          (doc_pk, FIELD_META))
        tokens = self._meta_tokens(doc_type, matter_id)
        self._add_postings(doc_pk, FIELD_META, tokens)
        self.conn.execute("UPDATE docs SET len_meta = ? WHERE doc_pk = ?", (len(tokens), doc_pk))

    def _clear_doc_index(self, doc_pk: int) -> None:
        self.conn.execute("DELETE FROM postings WHERE doc_pk = ?", (doc_pk,))
        self.conn.execute("DELETE FROM dup_keys WHERE doc_pk = ?", (doc_pk,))
        self.conn.execute("DELETE FROM near_dups WHERE doc_a = ? OR doc_b = ?", (doc_pk, doc_pk))

    # -- reference data ----------------------------------------------------
    def apply_people(self, people) -> int:
        people = list(people)
        self.conn.execute("DELETE FROM people")
        self.conn.executemany(
            "INSERT OR REPLACE INTO people(person_id, name, office, practice, title, status) "
            "VALUES (?,?,?,?,?,?)",
            [(p.person_id, p.name, p.office, p.practice, p.title, p.status) for p in people])
        return len(people)

    def apply_matters(self, matters) -> dict:
        """Upsert matters; remove matters (and their documents) no longer in the source."""
        matters = list(matters)
        existing = dict(self.conn.execute("SELECT matter_id, meta_hash FROM matters"))
        seen = set()
        changed_meta = []
        for m in matters:
            seen.add(m.matter_id)
            meta_hash = hashlib.sha256(json.dumps(
                [m.practice, m.matter_type, m.jurisdiction, m.client_industry]).encode()).hexdigest()
            if m.matter_id in existing:
                self.conn.execute(
                    "UPDATE matters SET name=?, client_id=?, client_industry=?, practice=?, "
                    "matter_type=?, jurisdiction=?, office=?, opened=?, closed=?, description=?, "
                    "security=?, meta_hash=? WHERE matter_id=?",
                    (m.name, m.client_id, m.client_industry, m.practice, m.matter_type,
                     m.jurisdiction, m.office, m.opened, m.closed, m.description, m.security,
                     meta_hash, m.matter_id))
                if existing[m.matter_id] != meta_hash:
                    changed_meta.append(m.matter_id)
            else:
                # acl_ok starts at 0: a new matter is invisible until the
                # permission rules have been evaluated for it.
                self.conn.execute(
                    "INSERT INTO matters(matter_id, name, client_id, client_industry, practice, "
                    "matter_type, jurisdiction, office, opened, closed, description, security, "
                    "acl_ok, meta_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
                    (m.matter_id, m.name, m.client_id, m.client_industry, m.practice,
                     m.matter_type, m.jurisdiction, m.office, m.opened, m.closed, m.description,
                     m.security, meta_hash))
                changed_meta.append(m.matter_id)
        removed = [mid for mid in existing if mid not in seen]
        docs_removed = 0
        for mid in removed:
            for (doc_id,) in self.conn.execute(
                    "SELECT doc_id FROM docs WHERE matter_id = ?", (mid,)).fetchall():
                self.delete_document(doc_id)
                docs_removed += 1
            self.conn.execute("DELETE FROM matters WHERE matter_id = ?", (mid,))
        for mid in changed_meta:
            for doc_pk, doc_type in self.conn.execute(
                    "SELECT doc_pk, doc_type FROM docs WHERE matter_id = ?", (mid,)).fetchall():
                self._reindex_meta(doc_pk, doc_type, mid)
        self._recompute_acl_ok()
        return {"matters": len(matters), "matters_removed": len(removed),
                "documents_removed_with_matters": docs_removed}

    def _recompute_acl_ok(self) -> None:
        self.conn.execute(
            "UPDATE matters SET acl_ok = CASE WHEN security IN ('public', 'restricted') "
            "AND matter_id NOT IN (SELECT matter_id FROM wall_incomplete) THEN 1 ELSE 0 END")

    def apply_permissions(self, snapshot: PermissionSnapshot) -> dict:
        """Replace all permission data with a complete snapshot. Fails closed on gaps."""
        warnings = []
        known_people = {r[0] for r in self.conn.execute("SELECT person_id FROM people")}
        known_matters = {r[0] for r in self.conn.execute("SELECT matter_id FROM matters")}
        self.conn.execute("DELETE FROM group_members")
        self.conn.executemany("INSERT OR IGNORE INTO group_members(group_id, person_id) VALUES (?,?)",
                              [(g, p) for g, p in snapshot.group_members])
        self.conn.execute("DELETE FROM matter_grants")
        for g in snapshot.grants:
            if g.principal_type not in ("user", "group"):
                warnings.append(f"grant on {g.matter_id} ignored: unknown grantee kind "
                                f"{g.principal_type!r}")
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO matter_grants(matter_id, principal_type, principal_id) "
                "VALUES (?,?,?)", (g.matter_id, g.principal_type, g.principal_id))
        self.conn.execute("DELETE FROM wall_exclusions")
        self.conn.execute("DELETE FROM wall_incomplete")
        for wall in snapshot.walls:
            reason = None
            if not wall.excluded_person_ids:
                reason = f"wall {wall.wall_id} does not say who is excluded"
            else:
                unknown = [p for p in wall.excluded_person_ids if p not in known_people]
                if unknown:
                    reason = (f"wall {wall.wall_id} excludes unknown person "
                              f"{', '.join(sorted(unknown))}")
            for mid in wall.matter_ids:
                if mid not in known_matters:
                    warnings.append(f"wall {wall.wall_id} names unknown matter {mid}")
                if reason:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO wall_incomplete(matter_id, reason) VALUES (?,?)",
                        (mid, reason))
                for pid in wall.excluded_person_ids or ():
                    self.conn.execute(
                        "INSERT OR IGNORE INTO wall_exclusions(wall_id, matter_id, person_id) "
                        "VALUES (?,?,?)", (wall.wall_id, mid, pid))
            if reason:
                warnings.append(reason + ": its matters are hidden from everyone")
        self._recompute_acl_ok()
        for mid, security in self.conn.execute(
                "SELECT matter_id, security FROM matters "
                "WHERE security NOT IN ('public', 'restricted') OR security IS NULL").fetchall():
            warnings.append(f"matter {mid} has unknown security {security!r}: hidden from everyone")
        self._set_meta("acl_state", "ok")
        self._set_meta("acl_synced_at", self.clock().isoformat())
        return {"group_memberships": len(snapshot.group_members), "grants": len(snapshot.grants),
                "walls": len(snapshot.walls), "warnings": warnings}

    def apply_team(self, team) -> int:
        team = list(team)
        self.conn.execute("DELETE FROM matter_team")
        self.conn.executemany(
            "INSERT OR REPLACE INTO matter_team(matter_id, person_id, role) VALUES (?,?,?)",
            [(t.matter_id, t.person_id, t.role) for t in team])
        return len(team)

    def apply_time(self, entries) -> int:
        entries = list(entries)
        self.conn.execute("DELETE FROM time_entries")
        self.conn.executemany(
            "INSERT OR REPLACE INTO time_entries(entry_id, matter_id, person_id, work_date, hours) "
            "VALUES (?,?,?,?,?)",
            [(e.entry_id, e.matter_id, e.person_id, e.work_date, float(e.hours)) for e in entries])
        return len(entries)

    # -- documents ---------------------------------------------------------
    def upsert_document(self, doc: Document) -> str:
        """Returns "added", "updated", "unchanged" or "rejected: <reason>"."""
        if (doc.security_override or "").strip().lower() not in ("", "inherit"):
            self.delete_document(doc.doc_id)
            return "rejected: document has its own security setting, which this tool does not model"
        if not doc.doc_id or not doc.matter_id:
            return "rejected: document has no id or no matter"
        content_hash = _doc_hash(doc)
        row = self.conn.execute("SELECT doc_pk, content_hash FROM docs WHERE doc_id = ?",
                                (doc.doc_id,)).fetchone()
        if row and row[1] == content_hash:
            return "unchanged"
        title_tokens = tokenize(doc.title)
        body_tokens = tokenize(doc.body)
        sketch = make_sketch(body_tokens)
        values = (doc.matter_id, doc.title, doc.body, doc.doc_type, doc.author_id, doc.doc_date,
                  doc.family_id or None, int(doc.version_no or 1), int(bool(doc.is_final)),
                  int(bool(doc.was_filed)), int(bool(doc.model_form)), int(doc.reuse_count or 0),
                  len(title_tokens), len(body_tokens), content_hash, _pack(sketch), doc.modified)
        if row:
            doc_pk = row[0]
            self._clear_doc_index(doc_pk)
            self.conn.execute(
                "UPDATE docs SET matter_id=?, title=?, body=?, doc_type=?, author_id=?, doc_date=?, "
                "family_id=?, version_no=?, is_final=?, was_filed=?, model_form=?, reuse_count=?, "
                "len_title=?, len_body=?, content_hash=?, sketch=?, modified=? WHERE doc_pk=?",
                values + (doc_pk,))
            outcome = "updated"
        else:
            doc_pk = self.conn.execute(
                "INSERT INTO docs(doc_id, matter_id, title, body, doc_type, author_id, doc_date, "
                "family_id, version_no, is_final, was_filed, model_form, reuse_count, len_title, "
                "len_body, content_hash, sketch, modified, len_meta) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (doc.doc_id,) + values).lastrowid
            outcome = "added"
        self._add_postings(doc_pk, FIELD_TITLE, title_tokens)
        self._add_postings(doc_pk, FIELD_BODY, body_tokens)
        self._reindex_meta(doc_pk, doc.doc_type, doc.matter_id)
        self._link_near_duplicates(doc_pk, sketch)
        return outcome

    def _link_near_duplicates(self, doc_pk: int, sketch: list) -> None:
        if len(sketch) < 4:
            return  # too short to compare meaningfully
        keys = sketch[:SKETCH_KEYS]
        marks = ",".join("?" * len(keys))
        # A pair is compared only if it shares several of its smallest
        # hashes. Boilerplate sentences give unrelated documents one or two
        # in common; real near-duplicates share most of them.
        candidates = [r[0] for r in self.conn.execute(
            f"SELECT doc_pk FROM dup_keys WHERE key IN ({marks}) AND doc_pk != ? "
            "GROUP BY doc_pk HAVING COUNT(*) >= ?",
            keys + [doc_pk, min(SKETCH_SHARED_KEYS, len(keys))])]
        for other in candidates:
            blob = self.conn.execute("SELECT sketch FROM docs WHERE doc_pk = ?", (other,)).fetchone()
            sim = sketch_similarity(sketch, _unpack(blob[0] if blob else None))
            if sim >= self.near_dup_threshold:
                a, b = sorted((doc_pk, other))
                self.conn.execute(
                    "INSERT OR REPLACE INTO near_dups(doc_a, doc_b, sim) VALUES (?,?,?)",
                    (a, b, round(sim, 4)))
        self.conn.executemany("INSERT OR IGNORE INTO dup_keys(key, doc_pk) VALUES (?,?)",
                              [(k, doc_pk) for k in keys])

    def delete_document(self, doc_id: str) -> bool:
        row = self.conn.execute("SELECT doc_pk FROM docs WHERE doc_id = ?", (doc_id,)).fetchone()
        if not row:
            return False
        self._clear_doc_index(row[0])
        self.conn.execute("DELETE FROM docs WHERE doc_pk = ?", (row[0],))
        return True

    # -- sync --------------------------------------------------------------
    def sync_permissions(self, adapter) -> dict:
        """Refresh people, groups, grants and walls only. No document is re-read."""
        with self.conn:
            people = self.apply_people(adapter.people())
            report = self.apply_permissions(adapter.permissions())
        report["people"] = people
        return report

    def sync(self, adapter, full: bool = False) -> dict:
        """Bring the index in line with the source, in one transaction.

        ``full`` re-reads every document and removes any indexed document the
        source no longer lists. Without it only changes since the stored
        cursor are read. If the adapter raises, nothing is changed."""
        counts = Counter()
        rejected = []
        with self.conn:
            people = self.apply_people(adapter.people())
            matter_report = self.apply_matters(adapter.matters())
            permission_report = self.apply_permissions(adapter.permissions())
            team = self.apply_team(adapter.matter_team())
            time_rows = self.apply_time(adapter.time_entries())
            cursor = None if full else self.get_meta("doc_cursor")
            batch = adapter.document_changes(cursor)
            rejected.extend(batch.rejected)
            seen = set()
            for doc in batch.upserts:
                seen.add(doc.doc_id)
                outcome = self.upsert_document(doc)
                if outcome.startswith("rejected"):
                    rejected.append((doc.doc_id, outcome))
                    seen.discard(doc.doc_id)
                    counts["rejected"] += 1
                else:
                    counts[outcome] += 1
            for doc_id in batch.deleted_doc_ids:
                seen.discard(doc_id)
                if self.delete_document(doc_id):
                    counts["deleted"] += 1
            if full:
                for (doc_id,) in self.conn.execute("SELECT doc_id FROM docs").fetchall():
                    if doc_id not in seen:
                        self.delete_document(doc_id)
                        counts["deleted"] += 1
            self._set_meta("doc_cursor", batch.cursor or "")
        return {
            "source": adapter.describe(), "mode": "full" if full else "incremental",
            "people": people, **matter_report,
            "team_rows": team, "time_entries": time_rows,
            "documents_added": counts["added"], "documents_updated": counts["updated"],
            "documents_unchanged": counts["unchanged"], "documents_deleted": counts["deleted"],
            "documents_rejected": [list(r) for r in rejected],
            "permission_warnings": permission_report["warnings"],
            "walls": permission_report["walls"], "grants": permission_report["grants"],
            "cursor": batch.cursor,
        }

    def stats(self) -> dict:
        one = lambda sql: self.conn.execute(sql).fetchone()[0]
        return {
            "documents": one("SELECT COUNT(*) FROM docs"),
            "matters": one("SELECT COUNT(*) FROM matters"),
            "people": one("SELECT COUNT(*) FROM people"),
            "terms": one("SELECT COUNT(*) FROM terms"),
            "postings": one("SELECT COUNT(*) FROM postings"),
            "near_duplicate_pairs": one("SELECT COUNT(*) FROM near_dups"),
            "version_families": one("SELECT COUNT(DISTINCT family_id) FROM docs "
                                    "WHERE family_id IS NOT NULL"),
            "matters_hidden_from_everyone": one("SELECT COUNT(*) FROM matters WHERE acl_ok = 0"),
            "fts5_available_but_unused": fts5_available(self.conn),
        }
