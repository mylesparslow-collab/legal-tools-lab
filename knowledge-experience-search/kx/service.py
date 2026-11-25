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
               reranker=None):
        conn = self._conn()
        try:
            result = search.search(conn, user, query, filters, self.config, limit=limit,
                                   offset=offset, explain=explain, as_of=self.as_of,
                                   reranker=reranker)
        finally:
            conn.close()
        self.audit.append("search", user, query, result["filters"],
                          [r["doc_id"] for r in result["results"]],
                          access=result["access"], relaxed=result["relaxed"])
        return result

    def who(self, user, query="", filters=None, limit=10):
        conn = self._conn()
        try:
            result = experience.who(conn, user, query, filters, self.config, as_of=self.as_of,
                                    limit=limit)
        finally:
            conn.close()
        ids = [f"{p['person_id']}:{e['matter_id']}" for p in result["people"]
               for e in p["evidence"]]
        self.audit.append("who", user, query, result["filters"], ids, access=result["access"])
        return result

    def suggest(self, user, prefix, limit=8):
        """Type-ahead. Permission-filtered like everything else; not written to the audit log."""
        conn = self._conn()
        try:
            return search.suggest(conn, user, prefix, limit, self.config)
        finally:
            conn.close()

    def users(self):
        conn = self._conn()
        try:
            return [{"person_id": r[0], "name": r[1], "office": r[2], "practice": r[3],
                     "title": r[4], "status": r[5]} for r in conn.execute(
                "SELECT person_id, name, office, practice, title, status FROM people "
                "ORDER BY name, person_id")]
        finally:
            conn.close()
