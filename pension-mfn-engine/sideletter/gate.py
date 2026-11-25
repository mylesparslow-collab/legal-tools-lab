"""Statutory gate: screens a draft side letter against rules loaded from rules/statutory_rules.json.

Statuses
  FLAG        screening pattern hit; quote and reason given
  MISSING     a clause the rule looks for was not found
  GAP         clause found but some statutory items are not named in it
  REVIEW      needs a person (interpretive rule, exemption claim, or outside the rule's stated scope)
  ADDRESSED   clause found and nothing was flagged (this is not a finding of compliance)
  NO_CLAUSE   no clause on the topic, and the rule only looks for red flags
  NOT_APPLICABLE  rule does not reach this investor type
"""
import csv
import json
import re
from datetime import date

from .quotes import norm, sentences, verify_quote


def load_rules(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def split_sections(text):
    """Sections start at lines like '4. Public Records.'"""
    parts = re.split(r"(?m)^(?=\d+\.\s+[A-Z])", text)
    out = []
    for p in parts:
        m = re.match(r"(\d+)\.\s+([^.\n]+)\.", p)
        if m:
            out.append({"ref": f"§ {m.group(1)}", "title": m.group(2).strip(), "text": norm(p)})
        elif p.strip():
            out.append({"ref": "preamble", "title": "Preamble", "text": norm(p)})
    return out


def load_registry(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _name_key(n):
    return re.sub(r"[^a-z]", "", n.lower())


def _finding(rule, status, **kw):
    f = {"rule_id": rule["id"], "title": rule["title"], "citation": rule["citation"],
         "verification_status": rule["verification_status"], "status": status,
         "section": kw.get("section"), "quote": kw.get("quote"), "why": kw.get("why", "")}
    return f


def _topic_sections(sections, patterns):
    rx = [re.compile(p, re.I) for p in patterns]
    return [s for s in sections if any(r.search(s["text"]) for r in rx)]


def _scope(rule, investor, fund):
    ap = rule["applies"]
    if investor["system_type"] not in ap["system_types"]:
        return _finding(rule, "NOT_APPLICABLE",
                        why=f"Reaches {' and '.join(ap['system_types'])} systems; this investor is a {investor['system_type']} system.")
    ft = ap.get("fund_types")
    if ft and fund["fund_type"] not in ft:
        return _finding(rule, "REVIEW",
                        why=f"Fund type '{fund['fund_type']}' is not one of the types the section's definition names ({', '.join(ft)}). Confirm whether the section applies before relying on it.")
    cutoff = ap.get("contract_on_or_after")
    if cutoff and date.fromisoformat(fund["subscription_date"]) < date.fromisoformat(cutoff):
        return _finding(rule, "REVIEW",
                        why=f"Contract predates {cutoff}. Check whether a new commitment brings it under the section; otherwise only the public fund's reasonable-efforts duty applies.")
    return None


def _flags(rule, secs, out):
    n = 0
    for s in secs:
        for rf in rule["screen"].get("red_flags", []):
            rx = re.compile(rf["pattern"], re.I)
            for sent in sentences(s["text"]):
                if rx.search(sent):
                    out.append(_finding(rule, "FLAG", section=f"{s['ref']} {s['title']}", quote=sent, why=rf["why"]))
                    n += 1
    return n


def run_gate(ruleset, investor, fund, doc_text, registry):
    sections = split_sections(doc_text)
    findings = []
    for rule in ruleset["rules"]:
        skip = _scope(rule, investor, fund)
        if skip:
            findings.append(skip)
            continue
        sc = rule["screen"]
        kind = sc["kind"]
        if kind == "manual":
            findings.append(_finding(rule, "REVIEW", why=sc["prompt"]))
        elif kind == "registry":
            findings.extend(_registry(rule, fund, doc_text, registry))
        elif kind == "required_sentence":
            hit = None
            for s in _topic_sections(sections, sc["topic"]):
                for sent in sentences(s["text"]):
                    if all(re.search(p, sent, re.I) for p in sc["all_of"]):
                        hit = (s, sent)
                        break
                if hit:
                    break
            if hit:
                findings.append(_finding(rule, "ADDRESSED", section=f"{hit[0]['ref']} {hit[0]['title']}", quote=hit[1],
                                         why="A sentence on this point was found. Read it; this is not a finding of compliance."))
            else:
                findings.append(_finding(rule, sc.get("severity_if_missing", "MISSING"),
                                         why="No sentence on this point was found in the draft."))
        elif kind in ("required_topic", "red_flag_only"):
            secs = _topic_sections(sections, sc["topic"])
            if not secs:
                if kind == "required_topic":
                    findings.append(_finding(rule, "MISSING", why="No clause on this topic was found in the draft."))
                else:
                    findings.append(_finding(rule, "NO_CLAUSE", why="No clause on this topic was found, so there was nothing to screen."))
                continue
            before = len(findings)
            _flags(rule, secs, findings)
            joined = " ".join(s["text"] for s in secs)
            missing = [k for k, pats in sc.get("coverage", {}).items()
                       if not any(re.search(p, joined, re.I) for p in pats)]
            if missing:
                findings.append(_finding(rule, "GAP", section=", ".join(s["ref"] for s in secs),
                                         why="Not named in the clause: " + "; ".join(missing) + "."))
            for ex in sc.get("expect_in_topic", []):
                if not re.search(ex["pattern"], joined, re.I):
                    findings.append(_finding(rule, "REVIEW", section=", ".join(s["ref"] for s in secs), why=ex["why_missing"]))
            if len(findings) == before:
                findings.append(_finding(rule, "ADDRESSED", section=", ".join(f"{s['ref']} {s['title']}" for s in secs),
                                         why="Clause found and no screening pattern hit. This is not a finding of compliance."))
        else:
            raise ValueError(f"unknown screen kind {kind}")
    # fail closed: every quoted finding must be verbatim in the draft
    for f in findings:
        if f["quote"] and not verify_quote(f["quote"], doc_text):
            raise AssertionError(f"quote not found in draft for {f['rule_id']}")
    return findings


def _registry(rule, fund, doc_text, registry):
    out = []
    reg = {_name_key(r["lobbyist_name"]): r for r in registry}
    agents = fund.get("placement_agents", [])
    if not agents:
        return [_finding(rule, "REVIEW", why="No placement agents are listed in the fund file. Confirm that none was used.")]
    for a in agents:
        named = a["name"] if verify_quote(a["name"], doc_text) else None
        row = reg.get(_name_key(a["name"]))
        where = "named in the draft" if named else "listed in the manager's disclosure but not named in the draft"
        if a.get("claims_exemption"):
            out.append(_finding(rule, "REVIEW", quote=named,
                                why=f"{a['name']} ({a['firm']}), {where}, is not treated as a placement agent under a claimed § {a['claims_exemption']} exemption. Confirm the facts behind the exemption."))
        elif row and row["status"].lower() == "active":
            out.append(_finding(rule, "ADDRESSED", quote=named,
                                why=f"{a['name']} ({a['firm']}), {where}, is active in the registry snapshot ({row['session']}, id {row['registry_id']})."))
        elif row:
            out.append(_finding(rule, "FLAG", quote=named,
                                why=f"{a['name']} ({a['firm']}), {where}, is in the registry snapshot with status '{row['status']}' ({row['session']})."))
        else:
            out.append(_finding(rule, "FLAG", quote=named,
                                why=f"{a['name']} ({a['firm']}), {where}, was not found in the registry snapshot."))
    return out
