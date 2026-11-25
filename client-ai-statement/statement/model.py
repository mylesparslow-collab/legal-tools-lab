"""Loading and validating the inputs: registry, statement inputs, client-terms record, libraries."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LIVE_STATUSES = ("pilot", "production")
DATA_TYPES = ("public", "firm_internal", "client_confidential", "personal_data", "health_information", "none")
AI_USE = ("permitted", "permitted_with_consent", "prohibited")
DISCLOSURE_METHODS = {
    "matter_start_notice": "by written notice at the start of a matter where a tool will be used",
    "invoice_narrative": "in the narrative of the invoice entry for the AI-assisted work",
    "on_request": "when you ask",
}
DATA_TYPE_PHRASES = {
    "client_confidential": "client confidential information",
    "personal_data": "personal data",
    "health_information": "health information",
    "firm_internal": "firm internal information",
    "public": "public information",
}


class InputError(ValueError):
    """An input file is malformed. The build stops; nothing is written."""


_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
          "boolean": bool, "null": type(None)}


def _is_type(value, name: str) -> bool:
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def validate_schema(value, schema: dict, path: str = "$") -> list[str]:
    """Validate against the subset of JSON Schema that registry.schema.json uses."""
    errors: list[str] = []
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        if not any(_is_type(value, t) for t in types):
            return [f"{path}: expected {' or '.join(types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{path}: {value!r} is not a date (YYYY-MM-DD)")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        for i, item in enumerate(value):
            errors += validate_schema(item, schema.get("items", {}), f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing '{req}'")
        for k, v in value.items():
            if k in props:
                errors += validate_schema(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unknown field '{k}'")
    return errors


def load_json(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise InputError(f"{path}: not valid JSON ({e})")


def registry_schema() -> dict:
    return load_json(DATA_DIR / "registry.schema.json")


def load_claims() -> dict:
    return load_json(DATA_DIR / "claims.json")


def load_options() -> dict:
    return load_json(DATA_DIR / "draft_options.json")


def load_banned() -> dict:
    return load_json(DATA_DIR / "banned_words.json")


def validate_registry(reg: dict) -> None:
    errors = validate_schema(reg, registry_schema())
    if not errors:
        ids = [t["id"] for t in reg["tools"]]
        errors += [f"duplicate tool id '{i}'" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if errors:
        raise InputError("registry does not match the registry schema:\n  " + "\n  ".join(errors))


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def parse_date(text: str, what: str) -> date:
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        raise InputError(f"{what}: {text!r} is not a date (YYYY-MM-DD)")


_INPUT_KEYS = {"version", "name_vendors", "tool_categories", "contact", "opt_out_role", "draft_options",
               "approval", "exclude_claims", "notes"}


def validate_inputs(inputs: dict) -> None:
    """Statement inputs: the facts and choices the registry schema has no field for."""
    errors = [f"unknown field '{k}'" for k in inputs if k not in _INPUT_KEYS]
    if not isinstance(inputs.get("version"), str) or not inputs.get("version", "").strip():
        errors.append("'version' is required (a short string such as '1.0')")
    cats = inputs.get("tool_categories", {})
    if not isinstance(cats, dict):
        errors.append("'tool_categories' must be an object keyed by registry tool id")
    else:
        for tid, c in cats.items():
            if not (isinstance(c, dict) and str(c.get("category", "")).strip() and str(c.get("use", "")).strip()):
                errors.append(f"tool_categories.{tid}: needs non-empty 'category' and 'use'")
    contact = inputs.get("contact")
    if not (isinstance(contact, dict) and str(contact.get("role", "")).strip() and str(contact.get("channel", "")).strip()):
        errors.append("'contact' needs 'role' (a role, not a person's name) and 'channel'")
    if not str(inputs.get("opt_out_role", "")).strip():
        errors.append("'opt_out_role' is required (the role a client writes to)")
    if not isinstance(inputs.get("draft_options"), dict):
        errors.append("'draft_options' is required: one chosen option id per topic")
    appr = inputs.get("approval", {})
    if not isinstance(appr, dict) or any(k not in ("approved_by", "approved_on", "content_hash") for k in appr):
        errors.append("'approval' may only hold approved_by, approved_on and content_hash")
    elif appr.get("approved_on"):
        try:
            date.fromisoformat(appr["approved_on"])
        except ValueError:
            errors.append("approval.approved_on is not a date (YYYY-MM-DD)")
    if not isinstance(inputs.get("exclude_claims", []), list):
        errors.append("'exclude_claims' must be a list of claim ids")
    if "name_vendors" in inputs and not isinstance(inputs["name_vendors"], bool):
        errors.append("'name_vendors' must be true or false")
    if errors:
        raise InputError("statement inputs are not valid:\n  " + "\n  ".join(errors))


_CLIENT_KEYS = {"client_ref", "terms_source", "terms_date", "ai_use", "consent_on_file", "disclosure_required",
                "disclosure_method", "tools_prohibited", "data_restrictions", "notes"}


def validate_client(client: dict, registry: dict) -> None:
    """Client-terms record. See README for the format."""
    errors = [f"unknown field '{k}'" for k in client if k not in _CLIENT_KEYS]
    for k in ("client_ref", "terms_source", "terms_date", "ai_use"):
        if not str(client.get(k, "")).strip():
            errors.append(f"missing '{k}'")
    if client.get("terms_date"):
        try:
            date.fromisoformat(client["terms_date"])
        except ValueError:
            errors.append("'terms_date' is not a date (YYYY-MM-DD)")
    if client.get("ai_use") and client["ai_use"] not in AI_USE:
        errors.append(f"'ai_use' must be one of {list(AI_USE)}")
    consent = client.get("consent_on_file")
    if consent is not None:
        if not isinstance(consent, dict) or set(consent) - {"date", "note"}:
            errors.append("'consent_on_file' must be null or an object with 'date' and optional 'note'")
        else:
            try:
                date.fromisoformat(consent.get("date", ""))
            except (TypeError, ValueError):
                errors.append("consent_on_file.date is not a date (YYYY-MM-DD)")
    if not isinstance(client.get("disclosure_required", False), bool):
        errors.append("'disclosure_required' must be true or false")
    if client.get("disclosure_required"):
        if client.get("disclosure_method") not in DISCLOSURE_METHODS:
            errors.append(f"'disclosure_method' must be one of {sorted(DISCLOSURE_METHODS)} when disclosure is required")
    known = {t["id"] for t in registry["tools"]}
    prohibited = client.get("tools_prohibited", [])
    if not isinstance(prohibited, list):
        errors.append("'tools_prohibited' must be a list of registry tool ids")
    else:
        for tid in prohibited:
            if tid not in known:
                errors.append(f"tools_prohibited: '{tid}' is not a tool id in the registry")
    restricted = client.get("data_restrictions", [])
    if not isinstance(restricted, list):
        errors.append("'data_restrictions' must be a list of data types")
    else:
        for d in restricted:
            if d not in ("client_confidential", "personal_data", "health_information"):
                errors.append(f"data_restrictions: '{d}' must be client_confidential, personal_data or health_information")
    if errors:
        raise InputError("client-terms record is not valid:\n  " + "\n  ".join(errors))


def client_restricted_ids(client: dict | None, registry: dict) -> list[str]:
    """Ids of tools in use that the client's terms rule out or restrict.

    - AI use prohibited, or consent required and none on file: every tool in use.
    - Otherwise: tools the client names, plus tools approved for a data type the client bars.
    """
    if not client:
        return []
    in_use = [t for t in registry["tools"] if t["status"] in LIVE_STATUSES]
    consent = (client.get("consent_on_file") or {}).get("date")
    if client.get("ai_use") == "prohibited" or (client.get("ai_use") == "permitted_with_consent" and not consent):
        return [t["id"] for t in in_use]
    named = set(client.get("tools_prohibited", []))
    barred = set(client.get("data_restrictions", []))
    return [t["id"] for t in in_use if t["id"] in named or barred & set(t["data_boundary"]["data_allowed"])]
