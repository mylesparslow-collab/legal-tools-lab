"""Content library: BM25 retrieval over past proposal answers.

Ranking prefers answers from winning proposals, recent ones and ones approved
by the practice lead. Answers past their review date are returned and marked
stale; they are never inserted automatically.
"""
import math
import re

from .facts import NUMBER_WORDS, join_list
from .util import parse_iso, tokens

OUTCOME_WEIGHT = {"won": 1.25, "pending": 1.0, "lost": 0.85}
APPROVED_WEIGHT = {True: 1.3, False: 0.7}
MATCH_WEIGHT = 1.2


class BM25:
    """Okapi BM25, standard library only."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.avgdl = (sum(len(d) for d in docs) / self.n) if self.n else 0.0
        self.tf, df = [], {}
        for d in docs:
            counts = {}
            for t in d:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query, i):
        if not self.n or not self.docs[i]:
            return 0.0
        tf, dl, s = self.tf[i], len(self.docs[i]), 0.0
        for t in set(query):
            f = tf.get(t)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def scores(self, query):
        return [self.score(query, i) for i in range(self.n)]


def is_stale(answer, as_of):
    return parse_iso(answer["review_by"]) < as_of


def recency_weight(answer, as_of):
    age_years = max(0.0, (as_of - parse_iso(answer["submitted"])).days / 365.25)
    return 1.0 / (1.0 + 0.15 * age_years)


def rank_answers(answers, qtype, query_text, rfp_meta, as_of):
    """Candidates of the given question type, best first.

    Each candidate: answer, bm25, score, factors, stale, reasons.
    """
    pool = [a for a in answers if a["question_type"] == qtype]
    if not pool:
        return []
    bm = BM25([tokens(a["question_text"] + " " + a["answer_text"] + " " + " ".join(a["tags"])) for a in pool])
    raw = bm.scores(tokens(query_text))
    top = max(raw) or 1.0
    out = []
    for a, r in zip(pool, raw):
        factors = {
            "text_match": round(0.2 + 0.8 * r / top, 3),
            "outcome": OUTCOME_WEIGHT.get(a["outcome"], 1.0),
            "recency": round(recency_weight(a, as_of), 3),
            "approved": APPROVED_WEIGHT[bool(a["approved"])],
            "agency_type": MATCH_WEIGHT if a["agency_type"] == rfp_meta["agency_type"] else 1.0,
            "practice": MATCH_WEIGHT if a["practice"] == rfp_meta["practice"] else 1.0,
        }
        score = 1.0
        for v in factors.values():
            score *= v
        reasons = ["%s proposal" % a["outcome"], "submitted %s" % a["submitted"],
                   "approved by %s" % a["approver"] if a["approved"] else "not approved by the practice lead"]
        if factors["agency_type"] > 1:
            reasons.append("same agency type")
        if factors["practice"] > 1:
            reasons.append("same practice")
        stale = is_stale(a, as_of)
        if stale:
            reasons.append("stale: review date %s has passed" % a["review_by"])
        out.append({"answer": a, "bm25": round(r, 4), "score": round(score, 4), "factors": factors,
                    "stale": stale, "reasons": reasons})
    out.sort(key=lambda c: (-c["score"], c["answer"]["id"]))
    return out


def fill_placeholders(text, ctx):
    """Fill the tagged placeholders in a library answer.

    ctx: agency, agency_short ('District'), governing_body, chief_exec, facts.
    Unknown placeholders are left in place so the fact guard can flag them.
    """
    facts = ctx["facts"]
    offices = [o["city"] for o in facts.get("offices", [])]
    n = len(offices)
    values = {
        "AGENCY": ctx["agency"],
        "AGENCY_SHORT": "the " + ctx["agency_short"],
        "GOVERNING_BODY": ctx.get("governing_body") or "governing body",
        "CHIEF_EXEC": ctx.get("chief_exec") or "chief executive",
        "FIRM_ATTORNEYS": str(facts.get("attorney_count", "")),
        "FIRM_FOUNDED": str(facts.get("founded_year", "")),
        "FIRM_OFFICE_COUNT": NUMBER_WORDS[n] if n <= 10 else str(n),
        "FIRM_OFFICES": join_list(offices),
        "FIRM_CLIENTS": str(facts.get("public_agency_clients", "")),
    }

    def sub(m):
        key = m.group(1)
        if key not in values or values[key] == "":
            return m.group(0)
        val = values[key]
        before = text[:m.start()].rstrip()
        if key == "AGENCY_SHORT" and (not before or before[-1] in ".?!:"):
            val = val[0].upper() + val[1:]
        return val

    return re.sub(r"\{([A-Z_]+)\}", sub, text)


def provenance(answer):
    return {"answer_id": answer["id"], "proposal_id": answer["proposal_id"], "submitted": answer["submitted"],
            "outcome": answer["outcome"], "approved": bool(answer["approved"]),
            "approver": answer["approver"], "review_by": answer["review_by"]}


def provenance_text(p):
    who = "approved by %s" % p["approver"] if p["approved"] else "NOT approved by the practice lead"
    return "Source: answer %s, proposal %s, submitted %s, outcome %s, %s, review by %s" % (
        p["answer_id"], p["proposal_id"], p["submitted"], p["outcome"], who, p["review_by"])
