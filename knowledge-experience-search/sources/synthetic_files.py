"""Adapter for the synthetic export written by synth/generate.py.

The export is a folder of CSV and JSON-lines files with its own invented
column names. config/mapping.synthetic.json maps those columns to the
canonical schema. This adapter is not modelled on any real product.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from kx.schema import (ChangeBatch, Document, Grant, Matter, PermissionSnapshot,
                       Person, TeamMember, TimeEntry, Wall)
from sources.base import SourceAdapter, SourceError
from sources.mapping import RejectedRow, load_mapping, map_row


class SyntheticFileAdapter(SourceAdapter):
    def __init__(self, data_dir, mapping_path):
        self.data_dir = Path(data_dir)
        self.mapping = load_mapping(mapping_path)
        self.rejected: list = []

    # -- file reading -----------------------------------------------------
    def _spec(self, name: str) -> dict:
        if name not in self.mapping:
            raise SourceError(f"mapping has no section {name!r}")
        return self.mapping[name]

    def _rows(self, name: str, required_file: bool = True):
        spec = self._spec(name)
        path = self.data_dir / spec["file"]
        if not path.exists():
            if required_file:
                raise SourceError(f"source file missing: {path.name}")
            return
        fmt = spec.get("format", "csv")
        with open(path, encoding="utf-8", newline="") as fh:
            if fmt == "csv":
                for row in csv.DictReader(fh):
                    yield row
            elif fmt == "jsonl":
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
            else:
                raise SourceError(f"unknown format {fmt!r} for {name}")

    def _mapped(self, name: str, required_file: bool = True, strict: bool = False):
        spec = self._spec(name)
        for i, row in enumerate(self._rows(name, required_file)):
            try:
                yield map_row(row, spec)
            except RejectedRow as exc:
                if strict:
                    # Permission rows are never skipped: a dropped row could
                    # be the one that excludes someone.
                    raise SourceError(f"{name} row {i + 1}: {exc}") from exc
                self.rejected.append((f"{name} row {i + 1}", str(exc)))

    # -- SourceAdapter ----------------------------------------------------
    def people(self):
        return [Person(**r) for r in self._mapped("people")]

    def matters(self):
        return [Matter(**r) for r in self._mapped("matters")]

    def permissions(self) -> PermissionSnapshot:
        members = tuple((r["group_id"], r["person_id"])
                        for r in self._mapped("group_members", strict=True))
        grants = tuple(Grant(**r) for r in self._mapped("grants", strict=True))
        wall_matters: dict = {}
        for r in self._mapped("walls", strict=True):
            wall_matters.setdefault(r["wall_id"], []).append(r["matter_id"])
        wall_people: dict = {}
        for r in self._mapped("wall_members", strict=True):
            wall_people.setdefault(r["wall_id"], []).append(r["person_id"])
        walls = []
        for wall_id, matter_ids in sorted(wall_matters.items()):
            excluded = wall_people.get(wall_id)
            walls.append(Wall(wall_id, tuple(matter_ids),
                              tuple(excluded) if excluded else None))
        for wall_id in wall_people:
            if wall_id not in wall_matters:
                raise SourceError(f"wall {wall_id} names people but no matters")
        return PermissionSnapshot(members, grants, tuple(walls))

    def matter_team(self):
        return [TeamMember(**r) for r in self._mapped("team")]

    def time_entries(self):
        return [TimeEntry(**r) for r in self._mapped("time_entries")]

    def document_changes(self, cursor: Optional[str]) -> ChangeBatch:
        before = len(self.rejected)
        newest = cursor or ""
        upserts = []
        for r in self._mapped("documents"):
            stamp = r.get("modified", "")
            # ">=" so that two changes with the same stamp are never missed.
            # Re-reading an unchanged document is harmless: the indexer
            # compares content hashes and skips it.
            if cursor is None or stamp >= cursor:
                upserts.append(Document(**r))
            if stamp > newest:
                newest = stamp
        deleted = []
        for r in self._mapped("deletions", required_file=False):
            stamp = r.get("deleted_at", "")
            if cursor is None or stamp >= cursor:
                deleted.append(r["doc_id"])
            if stamp > newest:
                newest = stamp
        return ChangeBatch(tuple(upserts), tuple(deleted), newest,
                           tuple(self.rejected[before:]))

    def describe(self) -> str:
        return f"synthetic files in {self.data_dir}"
