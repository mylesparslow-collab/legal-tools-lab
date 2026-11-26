"""Permission model.

Rules, in the order they are applied:

1. The asking user must be a known, active person. Otherwise nothing is visible.
2. A matter is visible only if its security is exactly "public" or
   "restricted" and its permission data is complete (``acl_ok``).
3. A restricted matter needs a grant to the user or to a group the user is in.
4. An ethical wall exclusion removes the matter for that user. It beats
   every grant, including group grants and public access.
5. A document inherits the security of its matter. A document whose matter
   is missing is not visible to anyone.

Everything that reads documents, postings, matters-as-evidence or time
records must restrict itself with ``VISIBLE_CTE``. The filter is part of the
retrieval SQL: rows the user may not see are never fetched, so nothing can be
derived from them later. ``can_see_reference`` is a separate plain-Python
statement of the same rules, used by the tests to cross-check the SQL.

These rules are the firm's own permission data applied as given. This module
does not decide who should be walled from what.
"""
from __future__ import annotations

import datetime as _dt

from kx.schema import KNOWN_SECURITY, SECURITY_PUBLIC, STATUS_ACTIVE


class PermissionDataUnavailable(Exception):
    """Permission data is missing or too old. Queries must return nothing."""


# Named parameter :uid is the asking user. Use as:  WITH <VISIBLE_CTE> SELECT ...
VISIBLE_CTE = """
vis(matter_id) AS (
  SELECT m.matter_id
  FROM matters m
  WHERE EXISTS (SELECT 1 FROM people u
                WHERE u.person_id = :uid AND u.status = 'active')
    AND (SELECT value FROM meta WHERE key = 'acl_state') = 'ok'
    AND m.acl_ok = 1
    AND (
      m.security = 'public'
      OR (m.security = 'restricted' AND (
            EXISTS (SELECT 1 FROM matter_grants g
                    WHERE g.matter_id = m.matter_id
                      AND g.principal_type = 'user'
                      AND g.principal_id = :uid)
         OR EXISTS (SELECT 1 FROM matter_grants g
                    JOIN group_members gm ON gm.group_id = g.principal_id
                    WHERE g.matter_id = m.matter_id
                      AND g.principal_type = 'group'
                      AND gm.person_id = :uid)))
    )
    AND NOT EXISTS (SELECT 1 FROM wall_exclusions w
                    WHERE w.matter_id = m.matter_id AND w.person_id = :uid)
)
"""


def assert_usable(conn, now: _dt.datetime | None = None, max_age_hours=None) -> None:
    """Raise unless a complete permission snapshot has been applied recently enough."""
    rows = dict(conn.execute(
        "SELECT key, value FROM meta WHERE key IN ('acl_state', 'acl_synced_at')"))
    if rows.get("acl_state") != "ok":
        raise PermissionDataUnavailable("no complete permission snapshot has been applied")
    if max_age_hours is not None:
        stamp = rows.get("acl_synced_at")
        try:
            synced = _dt.datetime.fromisoformat(stamp)
        except (TypeError, ValueError) as exc:
            raise PermissionDataUnavailable("permission snapshot has no usable timestamp") from exc
        now = now or _dt.datetime.now(_dt.timezone.utc)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=_dt.timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=_dt.timezone.utc)
        if (now - synced).total_seconds() > float(max_age_hours) * 3600:
            raise PermissionDataUnavailable(
                f"permission snapshot is older than {max_age_hours} hours")


def user_can_search(conn, user_id: str) -> bool:
    row = conn.execute("SELECT status FROM people WHERE person_id = ?", (user_id,)).fetchone()
    return bool(row) and row[0] == STATUS_ACTIVE


def visible_matter_ids(conn, user_id: str) -> set:
    """The matters a user may see, by the SQL rule. For tests and reports."""
    rows = conn.execute(f"WITH {VISIBLE_CTE} SELECT matter_id FROM vis", {"uid": user_id})
    return {r[0] for r in rows}


def visible_doc_ids(conn, user_id: str) -> set:
    rows = conn.execute(
        f"WITH {VISIBLE_CTE} SELECT d.doc_id FROM docs d "
        "WHERE d.matter_id IN (SELECT matter_id FROM vis)", {"uid": user_id})
    return {r[0] for r in rows}


def can_see_reference(conn, user_id: str, matter_id: str) -> bool:
    """The same rules written step by step in Python. Not used for queries."""
    state = conn.execute("SELECT value FROM meta WHERE key = 'acl_state'").fetchone()
    if not state or state[0] != "ok":
        return False
    person = conn.execute("SELECT status FROM people WHERE person_id = ?", (user_id,)).fetchone()
    if person is None or person[0] != STATUS_ACTIVE:
        return False
    matter = conn.execute("SELECT security, acl_ok FROM matters WHERE matter_id = ?",
                          (matter_id,)).fetchone()
    if matter is None:
        return False
    security, acl_ok = matter
    if acl_ok != 1 or security not in KNOWN_SECURITY:
        return False
    excluded = conn.execute(
        "SELECT 1 FROM wall_exclusions WHERE matter_id = ? AND person_id = ?",
        (matter_id, user_id)).fetchone()
    if excluded:
        return False
    if security == SECURITY_PUBLIC:
        return True
    groups = {r[0] for r in conn.execute(
        "SELECT group_id FROM group_members WHERE person_id = ?", (user_id,))}
    for ptype, pid in conn.execute(
            "SELECT principal_type, principal_id FROM matter_grants WHERE matter_id = ?",
            (matter_id,)):
        if ptype == "user" and pid == user_id:
            return True
        if ptype == "group" and pid in groups:
            return True
    return False
