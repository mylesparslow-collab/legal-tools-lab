"""The one interface between this tool and any document system.

Nothing outside this package reads source files or calls a source API.
To test against a real system, write one new subclass of SourceAdapter and
a mapping file. Do not change kx/. SWAP_IN_REAL_DATA.md lists what each
method must return and the questions to settle with IT first.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from kx.schema import (ChangeBatch, Matter, PermissionSnapshot, Person,
                       TeamMember, TimeEntry)


class SourceError(Exception):
    """The source could not supply something the indexer needs.

    Raise this rather than returning a partial answer. The indexer rolls the
    whole sync back, so the last complete permission state stays in force.
    """


class SourceAdapter(ABC):
    """Read-only view of a document system in the canonical schema."""

    @abstractmethod
    def people(self) -> Iterable[Person]:
        """Everyone who may search or who appears as an author or timekeeper.
        Departed people must be included with status "departed"."""

    @abstractmethod
    def matters(self) -> Iterable[Matter]:
        """Every matter whose documents may be indexed, with its security mode."""

    @abstractmethod
    def permissions(self) -> PermissionSnapshot:
        """A complete snapshot: group membership, grants and ethical walls.

        Must be complete or raise SourceError. A partial snapshot would
        silently drop a wall."""

    @abstractmethod
    def matter_team(self) -> Iterable[TeamMember]:
        """Who worked on each matter and in what role."""

    @abstractmethod
    def time_entries(self) -> Iterable[TimeEntry]:
        """Time records. Only matter, person, date and hours are used."""

    @abstractmethod
    def document_changes(self, cursor: Optional[str]) -> ChangeBatch:
        """Documents created or changed, and documents deleted, since ``cursor``.

        ``cursor`` None means everything. The returned cursor is opaque to the
        indexer and is handed back on the next call."""

    def describe(self) -> str:
        return self.__class__.__name__
