"""The one entry point the CLI and the web server use.

Each call opens its own read-only database connection, runs as the named
user, and writes an audit entry before returning. If the audit entry cannot
be written the call raises and no results are returned.
"""
from __future__ import annotations

from kx import audit, experience, index, search
from kx.config import load_config


class Service:
    def __init__(self, db_path, audit_path, config=None, clock=None, as_of=None):
        self.db_path = str(db_path)
        self.config = config or load_config()
        self.audit = audit.AuditLog(audit_path, clock=clock)
        self.as_of = as_of

    def _conn(self):
        return index.connect(self.db_path, readonly=True)

    def search(self, user, query="", filters=None, limit=10, offset=0, explain=False,
               reranker=None, expand=None):
        conn = self._conn()
        try:
            result = search.search(conn, user, query, filters, self.config, limit=limit,
                                   offset=offset, explain=explain, as_of=self.as_of,
                                   reranker=reranker, expand=expand)
        finally:
            conn.close()
        partial = result["relaxed"] or bool(result["expansion"]["not_found"])
        self.audit.append("search", user, query, result["filters"],
                          [r["doc_id"] for r in result["results"]],
                          access=result["access"], relaxed=partial)
        return result

    def who(self, user, query="", filters=None, limit=10, expand=None):
        conn = self._conn()
        try:
            result = experience.who(conn, user, query, filters, self.config, as_of=self.as_of,
                                    limit=limit, expand=expand)
        finally:
            conn.close()
        ids = [f"{p['person_id']}:{e['matter_id']}" for p in result["people"]
               for e in p["evidence"]]
        self.audit.append("who", user, query, result["filters"], ids, access=result["access"],
                          relaxed=result["relaxed"] or bool(result["not_found"]))
        return result

    def document(self, user, doc_id):
        """Full text of one document, or None. Logged whether or not it was found;
        the log entry names the document only if the user was shown it."""
        conn = self._conn()
        try:
            doc = search.get_document(conn, user, doc_id, self.config)
        finally:
            conn.close()
        self.audit.append("open", user, "", {}, [doc["doc_id"]] if doc else [],
                          access="ok" if doc else "not found")
        return doc

    def suggest(self, user, prefix, limit=8):
        """Type-ahead. Permission-filtered like everything else; not written to the audit log."""
        conn = self._conn()
        try:
            return search.suggest(conn, user, prefix, limit, self.config)
        finally:
            conn.close()

    def person(self, person_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT person_id, name, office, practice, title, status "
                               "FROM people WHERE person_id = ?", (person_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return {"person_id": row[0], "name": row[1], "office": row[2], "practice": row[3],
                "title": row[4], "status": row[5]}

    def users(self):
        conn = self._conn()
        try:
            return [{"person_id": r[0], "name": r[1], "office": r[2], "practice": r[3],
                     "title": r[4], "status": r[5]} for r in conn.execute(
                "SELECT person_id, name, office, practice, title, status FROM people "
                "ORDER BY name, person_id")]
        finally:
            conn.close()
