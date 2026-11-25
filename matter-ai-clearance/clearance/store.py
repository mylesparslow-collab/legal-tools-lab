"""Load the data files: clients, terms documents, matters, policy."""
import json
from pathlib import Path

from . import DATA
from . import clauses


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Store:
    def __init__(self, data_dir=None):
        self.dir = Path(data_dir) if data_dir else DATA
        raw = load_json(self.dir / "clients.json")
        self.clients = {c["id"]: c for c in raw["clients"]}
        self.other_parties = {p["id"]: p for p in raw.get("other_parties", [])}
        self._scan_cache = {}

    # documents -----------------------------------------------------------
    def all_document_entries(self, include_pending=True):
        out = []
        for owner in list(self.clients.values()) + list(self.other_parties.values()):
            for d in owner.get("documents", []):
                out.append(dict(d, owner_id=owner["id"]))
            if include_pending:
                for d in owner.get("pending_documents", []):
                    out.append(dict(d, owner_id=owner["id"], pending=True))
        return out

    def document_path(self, document_id):
        return self.dir / "terms" / (document_id + ".txt")

    def document_text(self, document_id):
        return self.document_path(document_id).read_text(encoding="utf-8")

    def scan(self, document_id, patterns):
        key = (document_id, id(patterns))
        if key not in self._scan_cache:
            self._scan_cache[key] = clauses.classify_document(document_id, self.document_text(document_id), patterns)
        return self._scan_cache[key]

    # parties -------------------------------------------------------------
    def party_record(self, party_id):
        if party_id in self.clients:
            return dict(self.clients[party_id], role="client")
        if party_id in self.other_parties:
            return self.other_parties[party_id]
        raise KeyError("unknown party: %s" % party_id)

    def party_summary(self, party_id, document_ids, patterns):
        """Scan the given documents and roll them up for one party.

        Analyst dismissals and analyst scope notes recorded on the party are applied here and
        listed in the result. A scope note limits one clause to named data classes, or to tools
        that are not on the party's approved list. The tool never infers scope by itself.
        """
        rec = self.party_record(party_id)
        results = []
        dismissed = []
        rules = rec.get("analyst_dismissals", [])
        scopes = rec.get("analyst_scopes", [])
        for doc_id in document_ids:
            res = self.scan(doc_id, patterns)
            kept = []
            for h in res["hits"]:
                d = next((r for r in rules if r["document_id"] == h["document_id"] and r["class"] == h["class"]
                          and h["quote"].startswith(r["quote_starts"])), None)
                if d:
                    dismissed.append(dict(h, dismissed_by=d["by"], dismissed_on=d["date"], reason=d["reason"]))
                    continue
                sc = next((r for r in scopes if r["document_id"] == h["document_id"] and r["class"] == h["class"]
                           and h["quote"].startswith(r["quote_starts"])), None)
                if sc:
                    h = dict(h, scope={k: sc[k] for k in ("data_classes", "only_tools_off_approved_list") if k in sc},
                             scope_recorded_by=sc["by"], scope_recorded_on=sc["date"], scope_reason=sc["reason"])
                kept.append(h)
            results.append(dict(res, hits=kept, silent=not kept))
        summary = clauses.summarize_party(party_id, rec["name"], results, patterns)
        summary["role"] = rec.get("role", "client")
        summary["party_short"] = rec.get("short_name", rec["name"])
        summary["dismissed"] = dismissed
        return summary

    # matters -------------------------------------------------------------
    def matter_ids(self):
        return sorted(p.stem for p in (self.dir / "matters").glob("*.json"))

    def matter(self, matter_id_or_path):
        p = Path(matter_id_or_path)
        if not p.exists():
            p = self.dir / "matters" / (str(matter_id_or_path) + ".json")
        return load_json(p)

    def matters_for_client(self, client_id):
        return [m for m in (self.matter(i) for i in self.matter_ids()) if m["client_id"] == client_id]


def load_policy(path=None):
    policy = load_json(path or DATA / "policy.json")
    ids = [r["id"] for r in policy["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids in policy")
    for r in policy["rules"]:
        for field in ("id", "text", "owner_role", "review_date", "decision"):
            if not r.get(field):
                raise ValueError("rule %s is missing %s" % (r.get("id"), field))
        if r["decision"] not in policy["decision_precedence"]:
            raise ValueError("rule %s has unknown decision %s" % (r["id"], r["decision"]))
    return policy
