"""Statement builder: assemble the one-page statement from supported claims only."""
from __future__ import annotations

import copy
from datetime import date

from . import evidence, lint
from .model import (DATA_TYPE_PHRASES, DISCLOSURE_METHODS, LIVE_STATUSES, client_restricted_ids, load_claims,
                    load_options, sha256_json, validate_client, validate_inputs, validate_registry)

SCHEMA = "client-ai-statement/1"
TITLE = "How we use AI tools"
EMPTY_SECTION = "No statement under this heading as of this date."

# Hard ceiling on printed words (title, labels, sentences, footer). Chosen from a
# render test: a statement at this length fits one US Letter page at the
# stylesheet's fixed type size. The build fails above it; the type is not shrunk.
WORD_LIMIT = 620
PROPOSAL_TARGET = 120
PROPOSAL_MAX = 135


class BuildError(Exception):
    """The statement cannot be built as asked. Nothing is written."""


def count_words(text: str) -> int:
    return len(text.split())


def join_list(items: list[str], sep: str = ", ") -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return sep.join(items[:-1]) + (" and " if sep == ", " else sep) + items[-1]


def _unique(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s[:2] != s[:2].upper() else s


def make_context(registry: dict, inputs: dict, client: dict | None, as_of: date, scopes: dict) -> dict:
    ctx = {"registry": registry, "inputs": inputs, "client": client or {}, "as_of": as_of, "scopes": scopes}
    ctx["derived"] = {"client_restricted_ids": client_restricted_ids(client, registry)}
    return ctx


def base_slots(ctx: dict) -> dict:
    """Values that sentence templates can use. Everything here is computed from the inputs."""
    reg, inputs, client = ctx["registry"], ctx["inputs"], ctx["client"]
    cats = inputs.get("tool_categories", {})
    in_use = [t for t in reg["tools"] if t["status"] in LIVE_STATUSES]
    n = len(in_use)
    n_prod = sum(t["status"] == "production" for t in in_use)
    n_pilot = n - n_prod

    def label(t):  # how a tool is referred to in client-facing text
        cat = cats.get(t["id"], {}).get("category")
        if inputs.get("name_vendors"):
            return f"{t['name']} ({_lower_first(cat)})" if cat else t["name"]
        return f"the {_lower_first(cat)} tool" if cat else "a tool we have not yet categorized"

    if n == 1:
        rollout = "It is in firmwide use." if n_prod else "It is in a limited pilot."
    elif n_pilot == 0:
        rollout = "They are in firmwide use."
    elif n_prod == 0:
        rollout = "They are in a limited pilot."
    else:
        rollout = (f"{num_word(n_prod).capitalize()} {'is' if n_prod == 1 else 'are'} in firmwide use and "
                   f"{num_word(n_pilot)} {'is' if n_pilot == 1 else 'are'} in a limited pilot.")

    slots = {
        "tools_in_use_phrase": f"{num_word(n)} AI-assisted tool{'' if n == 1 else 's'}",
        "rollout_phrase": rollout,
        "category_list": join_list(_unique(_lower_first(cats[t["id"]]["category"]) for t in in_use if t["id"] in cats)),
        "use_list": join_list(_unique(cats[t["id"]]["use"] for t in in_use if t["id"] in cats), sep="; "),
        "tool_name_list": join_list([label(t) for t in in_use], sep="; "),
        "review_interval_days": reg.get("review_interval_days", ""),
        "ocg_check_max_age_days": reg.get("ocg_check_max_age_days", ""),
        "contact_role": inputs.get("contact", {}).get("role", ""),
        "contact_channel": inputs.get("contact", {}).get("channel", ""),
        "opt_out_role": inputs.get("opt_out_role", ""),
    }
    if client:
        by_id = {t["id"]: t for t in reg["tools"]}
        restricted = ctx["derived"]["client_restricted_ids"]
        k = len(restricted)
        slots.update({
            "client_ref": client["client_ref"],
            "client_terms_date": client["terms_date"],
            "client_terms_source": client["terms_source"],
            "client_consent_date": (client.get("consent_on_file") or {}).get("date", ""),
            "client_prohibited_list": join_list(_unique(label(by_id[i]) for i in client.get("tools_prohibited", []))),
            "client_restricted_data_list": join_list([DATA_TYPE_PHRASES[d] for d in client.get("data_restrictions", [])]),
            "client_restricted_phrase": "The tool" if k == 1 else f"Each of the {num_word(k)} tools",
            "client_disclosure_phrase": DISCLOSURE_METHODS.get(client.get("disclosure_method"), ""),
        })
    return slots


_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def num_word(n: int) -> str:
    """Counts of tools are spelled out up to ten. Day counts stay as digits."""
    return _WORDS[n] if 0 <= n <= 10 else str(n)


def result_slots(result: dict) -> dict:
    p = len(result["passing"])
    one = p == 1
    return {"pass": num_word(p), "Pass": num_word(p).capitalize(), "scope": num_word(len(result["scope"])),
            "are": "is" if one else "are",
            "have": "has" if one else "have", "do": "does" if one else "do"}


def render_text(template: str, slots: dict, result: dict | None = None) -> str:
    values = dict(slots)
    if result is not None:
        values.update(result_slots(result))
    try:
        return template.format_map(values)
    except KeyError as e:
        raise BuildError(f"template uses slot {e} that is not available: {template!r}")


def _enabled(claim: dict, ctx: dict):
    for cond in claim.get("enabled_if", []):
        ok, detail = evidence.eval_condition(ctx, cond, ctx)
        if ok is not True:
            return False, f"does not apply: {detail['expected']}"
    return True, ""


def _pick_option(topic_id: str, variant: str, inputs: dict, options: dict):
    topic = options["topics"][topic_id]
    if variant not in topic["required_for"]:
        return None
    chosen = inputs.get("draft_options", {}).get(topic_id)
    ids = [o["id"] for o in topic["options"]]
    if chosen not in ids:
        raise BuildError(f"statement inputs must choose a draft option for '{topic_id}' "
                         f"(one of {ids}); got {chosen!r}")
    return next(o for o in topic["options"] if o["id"] == chosen)


def content_hash(stmt: dict) -> str:
    body = [stmt["variant"], stmt["title"], stmt["subtitle"], stmt["footer"],
            [[sec["label"], [s["text"] for s in sec["sentences"]]] for sec in stmt["sections"]]]
    return sha256_json(body)


def build_statement(registry: dict, inputs: dict, as_of: date, client: dict | None = None,
                    claims: dict | None = None, options: dict | None = None,
                    word_limit: int = WORD_LIMIT) -> dict:
    """Build the statement record. Raises InputError or BuildError; never prints an unsupported claim."""
    claims = claims or load_claims()
    options = options or load_options()
    validate_registry(registry)
    validate_inputs(inputs)
    if client is not None:
        validate_client(client, registry)
    variant = "client" if client is not None else "firm"
    ctx = make_context(registry, inputs, client, as_of, claims["scopes"])
    slots = base_slots(ctx)
    excluded = set(inputs.get("exclude_claims", []))
    known_ids = {c["id"] for c in claims["claims"]}
    for cid in excluded - known_ids:
        raise BuildError(f"exclude_claims: '{cid}' is not a claim id")

    sections = [{"id": s["id"], "label": s["label"], "sentences": []}
                for s in claims["sections"] if variant == "client" or not s.get("client_only")]
    by_section = {s["id"]: s for s in sections}
    downgraded, omitted, not_applicable, chosen_options, warnings = [], [], [], [], []

    for claim in claims["claims"]:
        sec = by_section.get(claim["section"])
        if sec is None:
            continue
        cid = claim["id"]

        if claim.get("type") == "draft_option":
            if cid in excluded:
                raise BuildError(f"exclude_claims: '{cid}' is a draft-option topic; choose its 'say nothing' option instead")
            opt = _pick_option(claim["topic"], variant, inputs, options)
            if opt is None:
                continue
            record = {"topic": claim["topic"], "option_id": opt["id"], "name": opt["name"], "printed": opt["text"] is not None}
            chosen_options.append(record)
            if opt["text"] is None:
                continue
            result = None
            if "rule" in opt:
                result = evidence.evaluate_rule(opt["rule"], ctx)
                if not evidence.is_printable(result):
                    rows = result["failing"] + result["unknown"]
                    why = "; ".join(f"{r['entry']}: {r['expected']} (found {r['actual']!r})" for r in rows) or result["note"]
                    raise BuildError(f"draft option {opt['id']} for '{claim['topic']}' is {result['status']} by the registry: "
                                     f"{why}. Choose another option or fix the registry.")
            text = render_text(opt["text"], slots, result)
            sec["sentences"].append({
                "claim_id": cid, "variant_id": opt["id"], "kind": "draft_option", "text": text,
                "template": opt["text"], "short_template": opt.get("short"), "rule": opt.get("rule"),
                "universal": bool(result) and result["universal"], "evidence": result,
                "proposal_order": claim.get("proposal_order"),
            })
            continue

        if cid in excluded:
            not_applicable.append({"claim_id": cid, "section": sec["id"], "reason": "excluded in the statement inputs (exclude_claims)"})
            continue
        ok, why = _enabled(claim, ctx)
        if not ok:
            not_applicable.append({"claim_id": cid, "section": sec["id"], "reason": why})
            continue

        tried = []
        for v in claim["variants"]:
            result = evidence.evaluate_rule(v["rule"], ctx)
            if evidence.is_printable(result):
                text = render_text(v["text"], slots, result)
                kind = "evidence" if result["scope"] or "context" not in v["rule"] else "record"
                sec["sentences"].append({
                    "claim_id": cid, "variant_id": v["id"], "kind": kind, "text": text,
                    "template": v["text"], "short_template": v.get("short"), "rule": v["rule"],
                    "universal": result["universal"], "evidence": result,
                    "proposal_order": claim.get("proposal_order"),
                })
                if tried:
                    downgraded.append({"claim_id": cid, "section": sec["id"], "printed_variant": v["id"],
                                       "printed_text": text, "stronger": tried})
                break
            tried.append({"variant_id": v["id"], "template": v["text"], "result": result})
        else:
            if claim.get("alternative_note"):
                not_applicable.append({"claim_id": cid, "section": sec["id"], "reason": claim["alternative_note"]})
            else:
                omitted.append({"claim_id": cid, "section": sec["id"], "variants": tried})

    for sec in sections:
        if not sec["sentences"]:
            sec["sentences"].append({"claim_id": "(none)", "variant_id": "placeholder", "kind": "placeholder",
                                     "text": EMPTY_SECTION, "template": EMPTY_SECTION, "rule": None,
                                     "universal": False, "evidence": None, "proposal_order": None})
            warnings.append(f"Section '{sec['label']}' has no supported sentence; it prints: {EMPTY_SECTION}")

    org = registry["organization"]
    reg_age = (as_of - date.fromisoformat(registry["as_of"])).days
    if reg_age < 0:
        warnings.append(f"The registry is dated {registry['as_of']}, after the statement's as-of date {as_of.isoformat()}. "
                        "Registry dates after the as-of date are treated as CANNOT TELL.")
    elif reg_age > registry.get("review_interval_days", 180):
        warnings.append(f"The registry is dated {registry['as_of']}, {reg_age} days before the statement's as-of date. "
                        "Refresh the registry before issuing.")
    cats = inputs.get("tool_categories", {})
    for t in registry["tools"]:
        if t["status"] in LIVE_STATUSES and t["id"] not in cats:
            warnings.append(f"Tool '{t['id']}' is in use but has no category in the statement inputs; "
                            "the statement cannot list tool categories.")

    stmt = {
        "schema": SCHEMA, "variant": variant, "organization": org, "title": TITLE,
        "subtitle": (f"{org}. Statement for {client['client_ref']}." if client
                     else f"{org}. Statement for clients and proposals."),
        "as_of": as_of.isoformat(), "version": inputs["version"], "registry_as_of": registry["as_of"],
        "registry_sha256": sha256_json(registry),
        "footer": (f"As of {as_of.isoformat()}. Version {inputs['version']}. "
                   f"Based on the firm's AI tool registry dated {registry['as_of']}."),
        "sections": sections, "downgraded": downgraded, "omitted": omitted, "not_applicable": not_applicable,
        "draft_options": chosen_options, "warnings": warnings,
        "tools_in_use": [t["id"] for t in registry["tools"] if t["status"] in LIVE_STATUSES],
        "category_check": [{"id": t["id"], "status": t["status"], "registry_purpose": t["purpose"],
                            "category": cats.get(t["id"], {}).get("category"), "use": cats.get(t["id"], {}).get("use")}
                           for t in registry["tools"] if t["status"] in LIVE_STATUSES],
        "scopes": copy.deepcopy(claims["scopes"]),
        "inputs": copy.deepcopy(inputs), "client": copy.deepcopy(client),
    }

    stmt["content_hash"] = content_hash(stmt)
    appr = inputs.get("approval", {})
    by, on, h = appr.get("approved_by", ""), appr.get("approved_on", ""), appr.get("content_hash", "")
    approved = bool(by and on and h == stmt["content_hash"])
    if (by or on) and not approved:
        warnings.append("An approval is on file but does not match this text (content_hash differs or is blank). "
                        "The statement stays DRAFT until the General Counsel approves this exact text.")
    stmt["status"] = "APPROVED" if approved else "DRAFT"
    stmt["approval"] = {"approved_by": by, "approved_on": on, "content_hash": h} if approved else None
    stmt["status_line"] = (f"Approved for release on {on}." if approved
                           else "DRAFT. Not approved for release.")

    stmt["proposal"] = _proposal(stmt, slots)
    stmt["word_count"] = statement_word_count(stmt)
    stmt["word_limit"] = word_limit

    problems = lint.lint_statement(stmt)
    if problems:
        raise BuildError("banned-words check failed:\n  " + "\n  ".join(problems))
    if stmt["word_count"] > word_limit:
        raise BuildError(f"statement is {stmt['word_count']} words; the one-page limit is {word_limit}. "
                         "Shorten it (exclude_claims, shorter draft options, or name_vendors off). The type size is fixed.")
    return stmt


def statement_word_count(stmt: dict) -> int:
    parts = [stmt["title"], stmt["subtitle"], stmt["footer"], stmt["status_line"]]
    for sec in stmt["sections"]:
        parts.append(sec["label"])
        parts += [s["text"] for s in sec["sentences"]]
    return sum(count_words(p) for p in parts)


def _proposal(stmt: dict, slots: dict) -> dict:
    """Short paragraph for RFP responses: the proposal-ordered sentences that were printed, in short form."""
    candidates = sorted((s for sec in stmt["sections"] for s in sec["sentences"] if s.get("proposal_order")),
                        key=lambda s: s["proposal_order"])
    closing = f"Our one-page statement dated {stmt['as_of']} gives the detail."
    used, words = [], count_words(closing)
    for s in candidates:
        text = render_text(s["short_template"], slots, s["evidence"]) if s.get("short_template") else s["text"]
        if words + count_words(text) > PROPOSAL_MAX:
            continue
        words += count_words(text)
        used.append({"claim_id": s["claim_id"], "variant_id": s["variant_id"], "text": text,
                     "universal_supported": bool(s["universal"]) and (s["evidence"] or {}).get("status") == "SUPPORTED"})
    used.append({"claim_id": "(closing)", "variant_id": "closing", "text": closing, "universal_supported": False})
    text = " ".join(u["text"] for u in used)
    return {"text": text, "words": count_words(text), "target": PROPOSAL_TARGET, "max": PROPOSAL_MAX,
            "sentences": used, "status": stmt["status"]}
