"""Canonical schema.

Every source adapter must hand the indexer these records and nothing else.
The indexer, the permission model and the search code never see source
column names. See SWAP_IN_REAL_DATA.md for what each field must mean.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DOC_TYPES = (
    "brief", "motion", "agreement", "memo", "staff report",
    "opinion letter", "checklist", "form", "other",
)

# The only security values the permission model will ever grant on.
SECURITY_PUBLIC = "public"
SECURITY_RESTRICTED = "restricted"
KNOWN_SECURITY = (SECURITY_PUBLIC, SECURITY_RESTRICTED)

ROLE_LEAD = "lead"
ROLE_SUPPORT = "support"

STATUS_ACTIVE = "active"
STATUS_DEPARTED = "departed"


@dataclass(frozen=True)
class Person:
    person_id: str
    name: str
    office: str = ""
    practice: str = ""
    title: str = ""
    status: str = ""  # "active" or "departed"; anything else cannot search


@dataclass(frozen=True)
class Matter:
    matter_id: str
    name: str
    client_id: str = ""
    client_industry: str = ""
    practice: str = ""
    matter_type: str = ""
    jurisdiction: str = ""
    office: str = ""
    opened: str = ""
    closed: str = ""
    description: str = ""
    # "public" (whole firm), "restricted" (granted users and groups only).
    # Any other value, including empty, is treated as unknown: nobody sees it.
    security: str = ""


@dataclass(frozen=True)
class Grant:
    matter_id: str
    principal_type: str  # "user" or "group"
    principal_id: str


@dataclass(frozen=True)
class Wall:
    """An ethical wall: the named people are excluded from the named matters.

    ``excluded_person_ids`` set to None means the source could not tell us who
    is excluded. The matters are then hidden from everyone.
    """
    wall_id: str
    matter_ids: tuple
    excluded_person_ids: Optional[tuple]


@dataclass(frozen=True)
class PermissionSnapshot:
    """A complete, point-in-time statement of who may see what."""
    group_members: tuple  # of (group_id, person_id)
    grants: tuple         # of Grant
    walls: tuple          # of Wall


@dataclass(frozen=True)
class TeamMember:
    matter_id: str
    person_id: str
    role: str  # "lead" or "support"


@dataclass(frozen=True)
class TimeEntry:
    entry_id: str
    matter_id: str
    person_id: str
    work_date: str
    hours: float


@dataclass(frozen=True)
class Document:
    doc_id: str
    matter_id: str
    title: str
    body: str
    doc_type: str = "other"
    author_id: str = ""
    doc_date: str = ""
    family_id: str = ""      # shared by all versions of one document
    version_no: int = 1
    is_final: bool = False
    was_filed: bool = False
    model_form: bool = False
    reuse_count: int = 0
    modified: str = ""       # source change stamp, used for incremental sync
    # Documents inherit matter security. If the source says a document has
    # its own security, set this to anything other than "" or "inherit" and
    # the indexer will refuse to index it.
    security_override: str = ""


@dataclass(frozen=True)
class ChangeBatch:
    upserts: tuple            # of Document
    deleted_doc_ids: tuple    # of str
    cursor: str               # opaque; pass back to get the next batch
    rejected: tuple = field(default_factory=tuple)  # of (source key, reason)
