"""An adapter over records already in memory. Used by tests and small examples."""
from __future__ import annotations

from typing import Optional

from kx.schema import ChangeBatch, PermissionSnapshot
from sources.base import SourceAdapter, SourceError


class MemoryAdapter(SourceAdapter):
    def __init__(self, people=(), matters=(), group_members=(), grants=(), walls=(),
                 team=(), time_entries=(), documents=(), deleted_doc_ids=(),
                 permissions_available=True):
        self._people = list(people)
        self._matters = list(matters)
        self.group_members = list(group_members)
        self.grants = list(grants)
        self.walls = list(walls)
        self._team = list(team)
        self._time = list(time_entries)
        self.documents = list(documents)
        self.deleted_doc_ids = list(deleted_doc_ids)
        self.permissions_available = permissions_available

    def people(self):
        return list(self._people)

    def matters(self):
        return list(self._matters)

    def permissions(self) -> PermissionSnapshot:
        if not self.permissions_available:
            raise SourceError("permission data is not available")
        return PermissionSnapshot(tuple(self.group_members), tuple(self.grants), tuple(self.walls))

    def matter_team(self):
        return list(self._team)

    def time_entries(self):
        return list(self._time)

    def document_changes(self, cursor: Optional[str]) -> ChangeBatch:
        cur = cursor or ""
        ups = tuple(d for d in self.documents if cursor is None or d.modified >= cur)
        new_cursor = max([d.modified for d in self.documents] + [cur])
        return ChangeBatch(ups, tuple(self.deleted_doc_ids), new_cursor)
