"""Apply a JSON mapping file to source rows.

The mapping says which source column feeds each canonical field, how coded
values translate, and which fields are required. Changing a source layout
means editing the JSON, not this code.
"""
from __future__ import annotations

import json
from pathlib import Path

_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f", ""}


class MappingError(Exception):
    pass


class RejectedRow(Exception):
    """One source row could not be mapped. Carries a reason for the sync report."""


def load_mapping(path) -> dict:
    with open(Path(path), encoding="utf-8") as fh:
        mapping = json.load(fh)
    if not isinstance(mapping, dict):
        raise MappingError("mapping file must be a JSON object")
    return mapping


def _convert(kind: str, value, field: str):
    if value is None:
        value = ""
    if kind == "int":
        try:
            return int(str(value).strip() or "0")
        except ValueError as exc:
            raise RejectedRow(f"{field}: not an integer: {value!r}") from exc
    if kind == "float":
        try:
            return float(str(value).strip() or "0")
        except ValueError as exc:
            raise RejectedRow(f"{field}: not a number: {value!r}") from exc
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        # An unrecognised flag is treated as not set. These flags only ever
        # raise a document's rank, so "not set" is the cautious reading.
        return False
    if kind == "str":
        return "" if value is None else str(value).strip()
    raise MappingError(f"unknown type {kind!r} for field {field}")


def map_row(row: dict, spec: dict) -> dict:
    """Return canonical field -> value for one source row, or raise RejectedRow."""
    fields = spec.get("fields", {})
    value_maps = spec.get("value_maps", {})
    defaults = spec.get("value_map_defaults", {})
    types = spec.get("types", {})
    out = {}
    for canonical, column in fields.items():
        value = row.get(column)
        if isinstance(value, str):
            value = value.strip()
        if canonical in value_maps:
            table = value_maps[canonical]
            key = "" if value is None else str(value)
            if key in table:
                value = table[key]
            elif canonical in defaults:
                value = defaults[canonical]
            # Otherwise the raw value passes through unchanged. For security
            # codes that means "unknown", which the permission model denies.
        if canonical in types:
            value = _convert(types[canonical], value, canonical)
        elif value is None:
            value = ""
        out[canonical] = value
    for name in spec.get("required", []):
        if out.get(name) in ("", None):
            raise RejectedRow(f"missing required field {name} (source column {fields.get(name)!r})")
    return out
