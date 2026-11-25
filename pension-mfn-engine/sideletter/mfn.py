"""MFN compendium parsing, condition extraction, election eligibility and the election deadline.

Election rules come from the fund file (they are contract terms, not statute):
  - a provision is electable only if the investor's commitment (aggregated with affiliates if the fund
    agreement says so) is at least the commitment named in the provision's lead-in
  - a provision granted on account of a legal, tax or regulatory status is electable only if the
    investor has one of the statuses named
  - categories the fund agreement carves out of the MFN are not electable
Anything the parser cannot read with confidence is routed to REVIEW, never guessed.
"""
import re
from datetime import date, timedelta

from .quotes import norm, sentences, verify_quote

CATEGORIES = {
    "lpac_observer": "LPAC observer rights",
    "lpac_seat": "LPAC seat",
    "key_person": "Key-person triggers",
    "co_investment": "Co-investment",
    "excuse": "Excuse rights (ESG, sanctions, policy)",
    "management_fee": "Management fee",
    "carried_interest": "Carried interest and distributions",
    "public_records": "Public records and confidentiality",
    "reporting": "Reporting and fee transparency",
    "transfer": "Transfers",
    "indemnity_immunity": "Indemnity, immunity and forum",
    "tax": "Tax",
    "placement_agent": "Placement agents",
    "regulatory_status": "Regulatory status (ERISA, BHCA, insurance)",
    "other": "Other",
}

# first match wins
_CLASSIFY = [
    ("lpac_observer", r"observer"),
    ("lpac_seat", r"(appoint|designate)[^.]{0,80}(member|representative)[^.]{0,40}Advisory Committee"),
    ("placement_agent", r"placement agent"),
    ("key_person", r"Key Person"),
    ("co_investment", r"co-invest"),
    ("excuse", r"\bexcuse[d]?\b|sanction"),
    ("public_records", r"public records|freedom of information|Confidential Information|may disclose"),
    ("tax", r"UBTI|unrelated business taxable income|effectively connected"),
    ("regulatory_status", r"ERISA|plan assets|non-voting interest|statutory filings"),
    ("indemnity_immunity", r"indemnif|immunit|jurisdiction|jury"),
    ("management_fee", r"Management Fee"),
    ("carried_interest", r"Carried Interest|clawback|Preferred Return"),
    ("reporting", r"\breport(s|ing)?\b|fees and expenses|financial statements"),
    ("transfer", r"\bTransfer\b"),
    ("tax", r"\btax\b"),
]

_STATUS = [
    ("erisa", r"ERISA|Benefit Plan Investor"),
    ("governmental_plan", r"governmental plan"),
    ("public_records", r"public records|freedom of information|\bFOIA\b|open records"),
    ("bhca", r"Bank Holding Company Act|\bBHCA\b"),
    ("non_us", r"non-U\.S\.|organized outside the United States"),
    ("insurance", r"insurance company"),
    ("tax_exempt", r"tax-exempt|exempt from (U\.S\. )?federal income tax"),
    ("sovereign", r"sovereign immunity|Eleventh Amendment"),
]
_STATE = r"(?:instrumentality|agency|political subdivision|public pension (?:plan|fund|system)) of the State of ([A-Z][a-z]+(?: [A-Z][a-z]+)?)"
_MONEY = r"Commitments? (?:of at least|of not less than|equal to or greater than|equal to or in excess of|of) \$([\d,]+)"
_LEAD = r"^(Granted to|Available to|Applicable to)\b"


def parse_compendium(text):
    """Pages are marked '--- Page N ---'. Provisions start 'Provision N.' and do not cross pages."""
    provs = []
    chunks = re.split(r"(?m)^--- Page (\d+) ---\s*$", text)
    for i in range(1, len(chunks), 2):
        page = int(chunks[i])
        body = chunks[i + 1]
        for m in re.finditer(r"(?ms)^Provision (\d+)\.\s+(.*?)(?=^Provision \d+\.|\Z)", body):
            provs.append({"id": int(m.group(1)), "page": page, "text": norm(m.group(2))})
    ids = [p["id"] for p in provs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate provision numbers in compendium")
    return provs


def classify(text):
    for cat, pat in _CLASSIFY:
        m = re.search(pat, text, re.I if cat not in ("transfer",) else 0)
        if m:
            return cat, m.group(0)
    return "other", None


def extract_conditions(text):
    """Read election conditions from the provision's lead-in sentence. Every condition carries its quote."""
    sents = sentences(text)
    lead = sents[0] if sents and re.match(_LEAD, sents[0]) else None
    conds, notes = [], []
    if lead is None:
        notes.append("No 'Granted to / Available to' lead-in sentence; conditions could not be read.")
        body = text
    else:
        body = norm(text[len(lead):]) if text.startswith(lead) else text
        for m in re.finditer(_MONEY, lead):
            conds.append({"type": "min_commitment", "value": int(m.group(1).replace(",", "")), "quote": m.group(0)})
        if re.search(r"\$", re.sub(_MONEY, "", lead)):
            notes.append("A dollar amount in the lead-in was not read as a commitment threshold.")
        statuses, squotes = [], []
        for key, pat in _STATUS:
            m = re.search(pat, lead, re.I)
            if m:
                statuses.append(key)
                squotes.append(m.group(0))
        m = re.search(_STATE, lead)
        if m:
            statuses.append(f"state_entity:{m.group(1)}")
            squotes.append(m.group(0))
        if statuses:
            conds.append({"type": "status_any_of", "value": statuses, "quote": lead})
        if re.search(r"Initial Closing", lead):
            conds.append({"type": "initial_closing", "value": True, "quote": lead})
        if re.search(r"Affiliate of the General Partner|General Partner[’']s Affiliates", lead):
            conds.append({"type": "gp_affiliate", "value": True, "quote": lead})
        if not conds and not re.search(r"(one or more|each|any|all) Limited Partners?\.?$", lead):
            notes.append("Lead-in has qualifying language the parser does not recognise.")
    return {"lead_in": lead, "conditions": conds, "notes": notes, "body": body}


def aggregated_commitment(investor, terms):
    own = investor["commitment"]
    aff = sum(a["commitment"] for a in investor.get("affiliates", [])) if terms.get("aggregate_affiliates") else 0
    return own + aff


def decide(prov, investor, terms):
    ex = extract_conditions(prov["text"])
    cat, kw = classify(ex["body"] if ex["lead_in"] else prov["text"])
    total = aggregated_commitment(investor, terms)
    reasons, verdict = [], "ELECTABLE"
    if cat in terms.get("excluded_categories", []):
        verdict = "NOT_ELECTABLE"
        reasons.append({"text": f"Category '{CATEGORIES[cat]}' is carved out of the MFN by the fund agreement ({terms.get('clause_ref', 'MFN clause')}).", "quote": kw})
    for c in ex["conditions"]:
        if c["type"] == "min_commitment":
            ok = total >= c["value"]
            how = (f"${investor['commitment']:,} plus ${total - investor['commitment']:,} of affiliate commitments"
                   if total != investor["commitment"] else f"${total:,}")
            reasons.append({"text": f"Requires a commitment of at least ${c['value']:,}; investor counts {how} = ${total:,}. {'Met' if ok else 'Not met'}.", "quote": c["quote"]})
            if not ok:
                verdict = "NOT_ELECTABLE"
        elif c["type"] == "status_any_of":
            shared = [s for s in c["value"] if s in investor["statuses"]]
            reasons.append({"text": f"Granted on account of status ({', '.join(c['value'])}). Investor {'shares: ' + ', '.join(shared) if shared else 'has none of these'}.", "quote": c["quote"]})
            if not shared:
                verdict = "NOT_ELECTABLE"
        elif c["type"] == "initial_closing":
            ok = bool(investor.get("admitted_at_initial_closing"))
            reasons.append({"text": f"Limited to investors admitted at the Initial Closing. Investor was {'admitted then' if ok else 'not admitted then'}.", "quote": c["quote"]})
            if not ok:
                verdict = "NOT_ELECTABLE"
        elif c["type"] == "gp_affiliate":
            reasons.append({"text": "Granted to an affiliate of the General Partner.", "quote": c["quote"]})
            verdict = "NOT_ELECTABLE"
    if ex["notes"] and verdict == "ELECTABLE":
        verdict = "REVIEW"
    for n in ex["notes"]:
        reasons.append({"text": n, "quote": None})
    if not reasons:
        reasons.append({"text": "No conditions in the lead-in.", "quote": ex["lead_in"]})
    for r in reasons:  # fail closed
        if r["quote"] and not verify_quote(r["quote"], prov["text"]):
            raise AssertionError(f"quote not in provision {prov['id']}")
    return {"id": prov["id"], "page": prov["page"], "category": cat, "category_label": CATEGORIES[cat],
            "category_source": "keyword rule", "verdict": verdict, "reasons": reasons,
            "lead_in": ex["lead_in"], "text": prov["text"]}


def election_deadline(terms, delivery_date):
    """Deadline = delivery date + window. Day-count and roll-forward come from the fund file. No holiday calendar."""
    d0 = date.fromisoformat(delivery_date)
    n = terms["election_window_days"]
    if terms.get("day_type", "calendar") == "business":
        d = d0
        while n:
            d += timedelta(days=1)
            if d.weekday() < 5:
                n -= 1
        raw = rolled = d
    else:
        raw = rolled = d0 + timedelta(days=n)
        if terms.get("roll_forward_if_weekend"):
            while rolled.weekday() >= 5:
                rolled += timedelta(days=1)
    return {"delivery_date": d0.isoformat(), "raw_deadline": raw.isoformat(), "deadline": rolled.isoformat(),
            "rolled": raw != rolled, "window": f"{terms['election_window_days']} {terms.get('day_type', 'calendar')} days"}


def verify_model_items(items, provisions):
    """Bounded model layer. A model may propose a category and a supporting quote for a provision.
    An item is accepted only if the provision exists, the page matches, the category is one of the
    fixed set, and the quote is verbatim in that provision. Everything else is rejected with a reason."""
    by_id = {p["id"]: p for p in provisions}
    ok, bad = [], []
    for it in items:
        p = by_id.get(it.get("provision_id"))
        if p is None:
            bad.append({**it, "rejected": "no such provision"})
        elif it.get("page") != p["page"]:
            bad.append({**it, "rejected": f"page mismatch (provision is on page {p['page']})"})
        elif it.get("category") not in CATEGORIES:
            bad.append({**it, "rejected": "category not in the fixed list"})
        elif not verify_quote(it.get("quote", ""), p["text"]):
            bad.append({**it, "rejected": "quote not found verbatim in the provision"})
        else:
            ok.append(it)
    return ok, bad


def apply_model_items(decisions, accepted, terms, investor, provisions):
    """Accepted model categories replace the keyword category; eligibility is then recomputed by code."""
    by = {a["provision_id"]: a for a in accepted}
    out = []
    for d in decisions:
        a = by.get(d["id"])
        if a and a["category"] != d["category"]:
            d = dict(d, category=a["category"], category_label=CATEGORIES[a["category"]],
                     category_source="model, quote-verified", model_quote=a["quote"])
            excluded = a["category"] in terms.get("excluded_categories", [])
            d["reasons"] = [r for r in d["reasons"] if "carved out" not in r["text"]]
            if excluded:
                d["verdict"] = "NOT_ELECTABLE"
                d["reasons"].insert(0, {"text": f"Category '{d['category_label']}' is carved out of the MFN by the fund agreement.", "quote": a["quote"]})
            elif d["verdict"] == "NOT_ELECTABLE" and not any(("Not met" in r["text"]) or ("none of these" in r["text"]) or ("not admitted" in r["text"]) or ("affiliate of the General" in r["text"]) for r in d["reasons"]):
                d["verdict"] = "REVIEW"
                d["reasons"].append({"text": "Model re-categorised a provision the keyword rule had placed in a carved-out category. A person should decide.", "quote": None})
        out.append(d)
    return out
