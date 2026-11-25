"""Seeded synthetic corpus generator.

Writes a folder that looks like an export from a document system: CSV and
JSON-lines files with their own column names (mapped to the canonical schema
by config/mapping.synthetic.json), plus ANSWER_KEY.json and manifest.json,
which are the generator's ground truth and are never read by the search code.

Every client, person, matter, place and document is invented.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import random
from collections import defaultdict
from pathlib import Path

from synth import vocab as V

SEED = 20260630
AS_OF = dt.date(2026, 6, 30)
TARGET_DOCS = 1500
N_MATTERS = 250
N_RESTRICTED = 14
N_NEAR_DUPS = 30


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _weighted(rng, weights: dict):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


class Generator:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self.seed = seed
        self.people = []
        self.matters = []
        self.docs = []
        self.team = []
        self.time = []
        self.grants = []
        self.walls = {}          # wall_id -> {"matters": [...], "excluded": [...]}
        self.group_members = []
        self.doc_seq = 0
        self.info = {}           # doc_id -> generator-only facts (topic, canonical, ...)

    # -- people ------------------------------------------------------------
    def make_people(self):
        rng = self.rng
        names = [(f, s) for f in V.FIRST_NAMES for s in V.SURNAMES]
        rng.shuffle(names)
        titles = ["Partner"] * 3 + ["Counsel"] * 2 + ["Associate"] * 6 + ["Paralegal"]
        n = 0
        for pkey, practice in V.PRACTICES.items():
            for i, title in enumerate(titles):
                n += 1
                first, last = names[n]
                if title == "Associate" and i >= 8:
                    office = rng.choice(V.NEW_OFFICES)
                else:
                    office = rng.choice(V.OFFICES)
                if title == "Counsel" and pkey in ("corp", "lit", "re") and i == 4:
                    title = "Knowledge lawyer"
                self.people.append({
                    "id": f"U{n:03d}", "name": f"{first} {last}", "office": office,
                    "pkey": pkey, "practice": practice["name"], "title": title, "status": "A"})
        # Six people have left the firm. Their work stays findable.
        leavers = rng.sample([p for p in self.people if p["title"] in ("Partner", "Associate")], 6)
        for p in leavers:
            p["status"] = "D"
        for p in self.people:
            self.group_members.append((f"practice:{p['pkey']}", p["id"]))
            self.group_members.append((f"office:{_slug(p['office'])}", p["id"]))

    def _by_practice(self, pkey, titles=None, active_only=False):
        return [p for p in self.people if p["pkey"] == pkey
                and (titles is None or p["title"] in titles)
                and (not active_only or p["status"] == "A")]

    # -- matters -----------------------------------------------------------
    def make_matters(self):
        rng = self.rng
        clients = []
        stems = list(V.CLIENT_STEMS)
        rng.shuffle(stems)
        for i in range(80):
            stem = stems[i % len(stems)]
            suffix = V.CLIENT_SUFFIXES[(i // len(stems) + i) % len(V.CLIENT_SUFFIXES)]
            clients.append({"id": f"C{i + 1:03d}", "name": f"{stem} {suffix}",
                            "industry": rng.choice(V.INDUSTRIES)})
        pkeys = list(V.PRACTICES)
        type_weights = [8, 7, 6, 3, 1]
        for i in range(N_MATTERS):
            pkey = pkeys[i % len(pkeys)]
            practice = V.PRACTICES[pkey]
            client = rng.choice(clients)
            mtype = rng.choices(practice["matter_types"], weights=type_weights)[0]
            opened = dt.date(2017, 1, 1) + dt.timedelta(days=rng.randrange(0, 3350))
            closed = opened + dt.timedelta(days=rng.randrange(90, 560))
            topics = rng.sample(list(practice["topics"]), 2)
            lead_pool = self._by_practice(pkey, ("Partner",))
            if opened.year >= 2024:
                lead_pool = [p for p in lead_pool if p["status"] == "A"] or lead_pool
            lead = rng.choice(lead_pool)
            support_pool = [p for p in self._by_practice(pkey) if p["id"] != lead["id"]
                            and (opened.year < 2024 or p["status"] == "A")]
            support = rng.sample(support_pool, rng.randint(2, 4))
            self.matters.append({
                "id": f"M{i + 1:04d}", "pkey": pkey, "practice": practice["name"],
                "client": client, "name": f"{client['name']}: {mtype}", "mtype": mtype,
                "forum": rng.choice(V.FORUMS), "office": lead["office"],
                "opened": opened, "closed": closed if closed <= AS_OF else None,
                "end": min(closed, AS_OF), "topics": topics, "security": "P",
                "lead": lead["id"], "support": [p["id"] for p in support], "codename": None,
                "description": f"{_cap(mtype)} for a client in the {client['industry']} sector, "
                               f"centred on {topics[0]}.",
            })

    def _team_ids(self, m):
        return [m["lead"]] + m["support"]

    def make_security(self):
        """Three ethical walls and a set of restricted matters, each with a project codename."""
        rng = self.rng
        codenames = list(V.CODENAMES)
        by_practice = defaultdict(list)
        for m in self.matters:
            if m["opened"].year >= 2022:
                by_practice[m["pkey"]].append(m)

        def take(pkey):
            m = by_practice[pkey].pop(rng.randrange(len(by_practice[pkey])))
            m["codename"] = codenames.pop(0)
            m["name"] = f"Project {m['codename']}"
            return m

        def exclude(m_list, count):
            pkey = m_list[0]["pkey"]
            on_team = {pid for m in m_list for pid in self._team_ids(m)}
            pool = [p["id"] for p in self._by_practice(pkey, active_only=True)
                    if p["id"] not in on_team]
            return sorted(rng.sample(pool, count))

        w1 = [take("corp")]
        w2 = [take("lit"), take("lit")]
        w3 = [take("fin")]
        # The second matter behind wall 2 is also restricted, with a grant to
        # the whole litigation group. Excluded people are in that group, so
        # the wall has to beat a group grant.
        w2[1]["security"] = "R"
        self.grants.append((w2[1]["id"], "G", "practice:lit"))
        for pid in self._team_ids(w2[1]):
            self.grants.append((w2[1]["id"], "U", pid))
        self.walls = {
            "W1": {"matters": [m["id"] for m in w1], "excluded": exclude(w1, 4)},
            "W2": {"matters": [m["id"] for m in w2], "excluded": exclude(w2, 4)},
            "W3": {"matters": [m["id"] for m in w3], "excluded": exclude(w3, 3)},
        }
        group_grant_practices = ["corp", "fin", "re"]
        pkeys = list(V.PRACTICES)
        for i in range(N_RESTRICTED):
            pkey = pkeys[i % len(pkeys)]
            m = take(pkey)
            m["security"] = "R"
            for pid in self._team_ids(m):
                self.grants.append((m["id"], "U", pid))
            if pkey in group_grant_practices and i < len(pkeys):
                self.grants.append((m["id"], "G", f"practice:{pkey}"))

    def make_team_and_time(self):
        rng = self.rng
        n = 0
        for m in self.matters:
            span = max(1, (m["end"] - m["opened"]).days)
            for pid in self._team_ids(m):
                role = "L" if pid == m["lead"] else "S"
                self.team.append((m["id"], pid, role))
                for _ in range(rng.randint(3, 10)):
                    n += 1
                    day = m["opened"] + dt.timedelta(days=rng.randrange(span))
                    hours = round(rng.uniform(0.5, 7.5) * (1.3 if role == "L" else 1.0), 1)
                    self.time.append((f"T{n:06d}", m["id"], pid, day.isoformat(), hours))

    # -- documents ---------------------------------------------------------
    def _body(self, m, topic, doc_type, mention_topic=True, canary=None):
        rng = self.rng
        practice = V.PRACTICES[m["pkey"]]
        terms = practice["topics"][topic]
        other_topics = [t for t in practice["topics"] if t != topic]
        label = V.DOC_LABELS[doc_type].lower()

        def fill(template, a=None, b=None, x=None):
            return template.format(
                doc=label, topic=topic, a=a, b=b, x=x, mt=m["mtype"], forum=m["forum"],
                industry=m["client"]["industry"], n=rng.randint(2, 9))

        paragraphs = []
        opening = rng.choice(V.OPENING_SENTENCES if mention_topic else V.OPENING_WITHOUT_TOPIC)
        first = [fill(opening)]
        if canary:
            first.append(f"Internal reference: Project {canary}.")
        paragraphs.append(first)
        for _ in range(rng.randint(3, 5)):
            sentences = []
            for _ in range(rng.randint(2, 3)):
                roll = rng.random()
                if roll < 0.62:
                    a, b = rng.sample(terms, 2)
                    sentences.append(_cap(fill(rng.choice(V.TOPIC_SENTENCES), a=a, b=b)))
                elif roll < 0.85:
                    sentences.append(rng.choice(V.GENERIC_SENTENCES))
                else:
                    x = rng.choice(practice["topics"][rng.choice(other_topics)])
                    sentences.append(fill(rng.choice(V.CROSS_SENTENCES), x=x))
            paragraphs.append(sentences)
        return "\n\n".join(" ".join(p) for p in paragraphs)

    def _title(self, m, topic, doc_type, canary=None, force_canary=False):
        rng = self.rng
        label = V.DOC_LABELS[doc_type]
        terms = V.PRACTICES[m["pkey"]]["topics"][topic]
        roll = rng.random()
        if roll < 0.40:
            title, has_topic = f"{label}: {topic}", True
        elif roll < 0.62:
            title, has_topic = f"{label} on {topic} ({m['mtype']})", True
        elif roll < 0.82:
            a, b = rng.sample(terms, 2)
            title, has_topic = f"{label}: {a} and {b}", False
        else:
            title, has_topic = f"{_cap(topic)}: {label.lower()} for {m['forum']}", True
        if canary and (rng.random() < 0.6 or force_canary):
            title = f"Project {canary} - {title}"
        return title, has_topic

    def _new_doc(self, m, topic, doc_type, canary=None, force_canary=False):
        rng = self.rng
        self.doc_seq += 1
        doc_id = f"D{self.doc_seq:05d}"
        title, has_topic = self._title(m, topic, doc_type, canary, force_canary)
        body = self._body(m, topic, doc_type, mention_topic=has_topic or rng.random() < 0.7,
                          canary=canary)
        span = max(1, (m["end"] - m["opened"]).days)
        date = m["opened"] + dt.timedelta(days=rng.randrange(span))
        final = rng.random() < 0.9
        filed = final and doc_type in ("brief", "motion") and rng.random() < 0.7
        doc = {
            "DocId": doc_id, "MatterNo": m["id"], "DocName": title, "Text": body,
            "Class": V.DOC_CODES[doc_type], "Author": rng.choice(self._team_ids(m)),
            "EditDate": date.isoformat(), "FamilyNum": "", "Version": 1,
            "Final": "Y" if final else "N", "Filed": "Y" if filed else "N", "ModelForm": "N",
            "ReuseCount": rng.choice([0, 0, 0, 0, 0, 1, 1, 2, 3]) if final else 0,
            "Modified": date.isoformat() + "T00:00:00", "DocSecurity": "",
        }
        self.docs.append(doc)
        self.info[doc_id] = {"topic": topic, "doc_type": doc_type, "pkey": m["pkey"],
                             "matter": m["id"], "canonical": doc_id, "kind": "base"}
        return doc

    def make_documents(self):
        rng = self.rng
        walled = {mid for w in self.walls.values() for mid in w["matters"]}
        for m in self.matters:
            practice = V.PRACTICES[m["pkey"]]
            count = 8 if m["id"] in walled else rng.randint(3, 7)
            for n in range(count):
                topic = m["topics"][0] if rng.random() < 0.7 else m["topics"][1]
                doc_type = _weighted(rng, practice["doc_types"])
                # At least two titles in a confidential matter carry its codename.
                self._new_doc(m, topic, doc_type, canary=m["codename"], force_canary=n < 2)

    def _reword(self, text: str, changes: int) -> str:
        """Change a few scattered words so the copy is close but not identical."""
        rng = self.rng
        words = text.split(" ")
        swaps = ["revised", "updated", "agreed", "current", "final", "amended", "internal"]
        for idx in rng.sample(range(8, len(words) - 1), min(changes, max(0, len(words) - 9))):
            if words[idx].isalpha() and len(words[idx]) > 3:
                words[idx] = rng.choice(swaps)
        return " ".join(words)

    def make_near_duplicates(self):
        """Forms reused on another matter with light edits."""
        rng = self.rng
        matters = {m["id"]: m for m in self.matters}
        w_public = [mid for w in ("W1", "W3") for mid in self.walls[w]["matters"]]
        base = [d for d in self.docs if d["Final"] == "Y"]

        def copy_into(src, target):
            self.doc_seq += 1
            doc_id = f"D{self.doc_seq:05d}"
            date = target["opened"] + dt.timedelta(
                days=rng.randrange(max(1, (target["end"] - target["opened"]).days)))
            title, text = src["DocName"], src["Text"]
            source_code = matters[src["MatterNo"]]["codename"]
            if source_code:
                # The lawyer reusing a document from a confidential matter
                # removes the project name. The copy must not carry it out.
                title = title.replace(f"Project {source_code} - ", "")
                text = text.replace(f" Internal reference: Project {source_code}.", "")
            doc = dict(src, DocId=doc_id, MatterNo=target["id"],
                       DocName=title + " (adapted)",
                       Text=self._reword(text, 5), Author=rng.choice(self._team_ids(target)),
                       EditDate=date.isoformat(), Modified=date.isoformat() + "T00:00:00",
                       ModelForm="N", ReuseCount=0)
            self.docs.append(doc)
            src["ReuseCount"] = int(src["ReuseCount"]) + 1
            self.info[doc_id] = dict(self.info[src["DocId"]], matter=target["id"],
                                     canonical=self.info[src["DocId"]]["canonical"],
                                     kind="near_duplicate", copy_of=src["DocId"])
            return doc

        planted = []
        # Four copies of open documents sit behind a wall; two walled
        # documents have open copies. Collapse must not reveal either.
        for i in range(4):
            target = matters[w_public[i % len(w_public)]]
            pool = [d for d in base if self.info[d["DocId"]]["pkey"] == target["pkey"]
                    and matters[d["MatterNo"]]["codename"] is None]
            planted.append(copy_into(rng.choice(pool), target))
        for i in range(2):
            source_matter = matters[w_public[i % len(w_public)]]
            pool = [d for d in base if d["MatterNo"] == source_matter["id"]
                    and self.info[d["DocId"]]["kind"] == "base"]
            targets = [m for m in self.matters if m["pkey"] == source_matter["pkey"]
                       and m["codename"] is None]
            planted.append(copy_into(rng.choice(pool), rng.choice(targets)))
        while len(planted) < N_NEAR_DUPS:
            src = rng.choice(base)
            if self.info[src["DocId"]]["kind"] != "base" or matters[src["MatterNo"]]["codename"]:
                continue
            targets = [m for m in self.matters if m["pkey"] == self.info[src["DocId"]]["pkey"]
                       and m["id"] != src["MatterNo"] and m["codename"] is None]
            planted.append(copy_into(src, rng.choice(targets)))

    def make_drafts(self):
        """Earlier versions of final documents, until the corpus reaches its target size."""
        rng = self.rng
        finals = [d for d in self.docs if d["Final"] == "Y"
                  and self.info[d["DocId"]]["kind"] == "base"]
        rng.shuffle(finals)
        fam = 0
        for final in finals:
            remaining = TARGET_DOCS - len(self.docs)
            if remaining <= 0:
                break
            n_drafts = min(remaining, rng.randint(1, 3))
            fam += 1
            family = f"F{fam:04d}"
            final["FamilyNum"] = family
            final["Version"] = n_drafts + 1
            final_date = dt.date.fromisoformat(final["EditDate"])
            for v in range(1, n_drafts + 1):
                self.doc_seq += 1
                doc_id = f"D{self.doc_seq:05d}"
                paragraphs = final["Text"].split("\n\n")
                text = "\n\n".join(paragraphs[:-1]) if len(paragraphs) > 3 and v == 1 else final["Text"]
                date = final_date - dt.timedelta(days=(n_drafts + 1 - v) * rng.randint(2, 9))
                draft = dict(final, DocId=doc_id, Text=self._reword(text, 3 + (n_drafts - v)),
                             Version=v, Final="N", Filed="N", ModelForm="N", ReuseCount=0,
                             EditDate=date.isoformat(), Modified=date.isoformat() + "T00:00:00")
                self.docs.append(draft)
                self.info[doc_id] = dict(self.info[final["DocId"]], kind="draft",
                                         canonical=self.info[final["DocId"]]["canonical"])

    # -- ground truth ------------------------------------------------------
    def _pick_demo_users(self):
        granted_users = {g[2] for g in self.grants if g[1] == "U"}
        excluded = {pid for w in self.walls.values() for pid in w["excluded"]}
        matters = {m["id"]: m for m in self.matters}
        newcomer = next(p for p in self.people
                        if p["pkey"] == "priv" and p["title"] == "Associate"
                        and p["status"] == "A" and p["office"] in V.NEW_OFFICES
                        and p["id"] not in granted_users and p["id"] not in excluded)
        w1_matter = matters[self.walls["W1"]["matters"][0]]
        departed = next(p for p in self.people if p["status"] == "D")
        name = {p["id"]: p["name"] for p in self.people}
        users = [
            {"person_id": newcomer["id"], "label": "New associate, no special access",
             "note": "Sees every firm-wide matter. Not on any restricted team. Not behind a wall."},
            {"person_id": self.walls["W1"]["excluded"][0], "label": "Excluded by wall W1",
             "note": f"Walled from Project {w1_matter['codename']}. Searches run as this user "
                     "must show no trace of that matter."},
            {"person_id": w1_matter["lead"], "label": "Lead on the matter behind wall W1",
             "note": f"Leads Project {w1_matter['codename']} and sees its documents."},
            {"person_id": self.walls["W2"]["excluded"][0], "label": "Excluded by wall W2",
             "note": "In the litigation group, which has a grant on one of the two walled "
                     "matters. The wall still wins."},
            {"person_id": departed["id"], "label": "Has left the firm",
             "note": "Not active, so every query returns nothing."},
        ]
        for u in users:
            u["name"] = name[u["person_id"]]
        return users, newcomer["id"]

    def build_answer_key(self):
        rng = random.Random(self.seed + 1)
        matters = {m["id"]: m for m in self.matters}
        demo_users, eval_user = self._pick_demo_users()
        groups = defaultdict(set)
        for g, pid in self.group_members:
            groups[pid].add(g)

        def can_see(pid, m):
            for w in self.walls.values():
                if m["id"] in w["matters"] and pid in w["excluded"]:
                    return False
            if m["security"] == "P":
                return True
            return any(g[0] == m["id"] and ((g[1] == "U" and g[2] == pid) or
                                            (g[1] == "G" and g[2] in groups[pid]))
                       for g in self.grants)

        visible = [d for d in self.docs if can_see(eval_user, matters[d["MatterNo"]])]
        units = defaultdict(set)  # (pkey, topic, doc_type) -> canonical ids with a visible member
        for d in visible:
            i = self.info[d["DocId"]]
            units[(i["pkey"], i["topic"], i["doc_type"])].add(i["canonical"])
        by_id = {d["DocId"]: d for d in self.docs}
        usable = sorted(k for k, v in units.items() if 5 <= len(v) <= 10)
        rng.shuffle(usable)
        queries = []

        def add(category, query, key, **extra):
            queries.append(dict({"id": f"Q{len(queries) + 1:02d}", "category": category,
                                 "query": query, "as_user": eval_user,
                                 "topic": key[1], "doc_type": key[2],
                                 "relevant": sorted(units[key])}, **extra))

        pool = list(usable)
        for key in pool[:14]:
            add("topic and document type", f"{key[1]} {key[2]}", key)
        for key in pool[14:20]:
            add("topic with a type filter", f'{key[1]} type:"{key[2]}"', key)
        for key in pool[20:25]:
            term = rng.choice(V.PRACTICES[key[0]]["topics"][key[1]][:3])
            add("exact phrase", f'"{term}" {key[2]}', key)
        # Best example: plant exactly one model form among the relevant documents.
        best_keys = [k for k in pool[25:] if k[2] in ("agreement", "form", "checklist", "memo")][:6]
        for key in best_keys:
            candidates = sorted(c for c in units[key]
                                if can_see(eval_user, matters[by_id[c]["MatterNo"]])
                                and by_id[c]["Final"] == "Y")
            gold = rng.choice(candidates)
            for c in units[key]:
                by_id[c]["ModelForm"] = "N"
            by_id[gold]["ModelForm"] = "Y"
            by_id[gold]["ReuseCount"] = rng.randint(8, 30)
            add("best example", f"{key[1]} {key[2]}", key, best=gold)
        used = {(q["topic"], q["doc_type"]) for q in queries}
        for pkey, topic, template in V.MISMATCH_QUERIES:
            options = sorted((k for k in units if k[0] == pkey and k[1] == topic),
                             key=lambda k: (-len(units[k]), k))
            key = options[0]
            add("different vocabulary", template.format(type=key[2]), key)

        # A scattering of other model forms, away from the keyed sets.
        keyed = {c for q in queries for c in q["relevant"]}
        others = [d for d in self.docs if d["Final"] == "Y" and d["DocId"] not in keyed
                  and self.info[d["DocId"]]["kind"] == "base"
                  and self.info[d["DocId"]]["doc_type"] in ("form", "checklist", "agreement")]
        for d in rng.sample(others, 40):
            d["ModelForm"] = "Y"
            d["ReuseCount"] = rng.randint(4, 25)
        # Drafts copy their final's flags at creation; make sure no draft is a model form.
        for d in self.docs:
            if self.info[d["DocId"]]["kind"] != "base":
                d["ModelForm"] = "N"

        status = {p["id"]: p["status"] for p in self.people}

        def control_for(m):
            """An active team member who can open the matter."""
            return next(pid for pid in self._team_ids(m)
                        if status[pid] == "A" and can_see(pid, m))

        wall_tests = []
        for wall_id, w in sorted(self.walls.items()):
            for mid in w["matters"]:
                m = matters[mid]
                hidden = sorted(d["DocId"] for d in self.docs if d["MatterNo"] == mid)
                wall_tests.append({
                    "id": f"{wall_id}-{mid}", "wall_id": wall_id, "matter_id": mid,
                    "canary_term": m["codename"].lower(),
                    "queries": [m["codename"], f"project {m['codename']}", m["topics"][0],
                                f"{m['topics'][0]} {m['mtype']}"],
                    "denied_users": w["excluded"], "must_never_appear": hidden,
                    "control_user": control_for(m),
                })
        restricted_tests = []
        for m in self.matters:
            if m["security"] == "R" and not any(m["id"] in w["matters"] for w in self.walls.values()):
                outsiders = [p["id"] for p in self.people
                             if p["status"] == "A" and not can_see(p["id"], m)]
                restricted_tests.append({
                    "id": f"R-{m['id']}", "matter_id": m["id"],
                    "canary_term": m["codename"].lower(),
                    "queries": [m["codename"], m["topics"][0]],
                    "denied_users": sorted(rng.sample(outsiders, 3)),
                    "must_never_appear": sorted(d["DocId"] for d in self.docs
                                                if d["MatterNo"] == m["id"]),
                    "control_user": control_for(m),
                })
        equivalents = {doc_id: i["canonical"] for doc_id, i in self.info.items()
                       if i["canonical"] != doc_id}
        key = {
            "about": "Ground truth written by the generator. A document is relevant to a query "
                     "when its main topic and document type are the ones the query was built "
                     "from. Drafts and adapted copies count as their final or original "
                     "(see equivalents). The search code never reads this file.",
            "seed": self.seed, "as_of": AS_OF.isoformat(), "eval_user": eval_user,
            "queries": queries, "wall_tests": wall_tests, "restricted_tests": restricted_tests,
            "equivalents": equivalents,
        }
        manifest = {
            "about": "Generator facts for the demo and tests. Not read by the search code.",
            "seed": self.seed, "as_of": AS_OF.isoformat(),
            "counts": {"documents": len(self.docs), "matters": len(self.matters),
                       "people": len(self.people), "practices": len(V.PRACTICES),
                       "offices": len(V.OFFICES), "time_entries": len(self.time),
                       "restricted_matters": sum(1 for m in self.matters if m["security"] == "R"),
                       "walls": len(self.walls),
                       "draft_documents": sum(1 for i in self.info.values() if i["kind"] == "draft"),
                       "planted_near_duplicates": sum(1 for i in self.info.values()
                                                      if i["kind"] == "near_duplicate")},
            "walls": {wid: {"matters": w["matters"], "excluded": w["excluded"],
                            "codenames": [matters[mid]["codename"] for mid in w["matters"]]}
                      for wid, w in sorted(self.walls.items())},
            "restricted_matters": sorted(m["id"] for m in self.matters if m["security"] == "R"),
            "demo_users": demo_users,
            "near_duplicates": sorted([doc_id, i["copy_of"]] for doc_id, i in self.info.items()
                                      if i["kind"] == "near_duplicate"),
        }
        return key, manifest

    # -- output ------------------------------------------------------------
    def write(self, out_dir):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        def write_csv(name, header, rows):
            with open(out / name, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(header)
                w.writerows(rows)

        key, manifest = self.build_answer_key()
        write_csv("people.csv", ["UserId", "FullName", "Office", "Dept", "Title", "Status"],
                  [(p["id"], p["name"], p["office"], p["practice"], p["title"], p["status"])
                   for p in self.people])
        write_csv("group_members.csv", ["GroupCode", "UserId"], sorted(self.group_members))
        write_csv("matters.csv",
                  ["MatterNo", "MatterName", "ClientNo", "Industry", "PracticeArea", "MatterType",
                   "Forum", "Office", "OpenDate", "CloseDate", "Description", "SecurityCode"],
                  [(m["id"], m["name"], m["client"]["id"], m["client"]["industry"], m["practice"],
                    m["mtype"], m["forum"], m["office"], m["opened"].isoformat(),
                    m["closed"].isoformat() if m["closed"] else "", m["description"], m["security"])
                   for m in self.matters])
        write_csv("matter_access.csv", ["MatterNo", "GranteeKind", "Grantee"], sorted(set(self.grants)))
        write_csv("walls.csv", ["WallId", "MatterNo"],
                  [(wid, mid) for wid, w in sorted(self.walls.items()) for mid in w["matters"]])
        write_csv("wall_members.csv", ["WallId", "ExcludedUserId"],
                  [(wid, pid) for wid, w in sorted(self.walls.items()) for pid in w["excluded"]])
        write_csv("matter_team.csv", ["MatterNo", "UserId", "Role"], self.team)
        write_csv("time_entries.csv", ["EntryId", "MatterNo", "UserId", "WorkDate", "Hours"], self.time)
        with open(out / "documents.jsonl", "w", encoding="utf-8") as fh:
            for d in sorted(self.docs, key=lambda d: d["DocId"]):
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
        (out / "deletions.jsonl").write_text("", encoding="utf-8")
        with open(out / "ANSWER_KEY.json", "w", encoding="utf-8") as fh:
            json.dump(key, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        with open(out / "manifest.json", "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        return manifest


def generate(out_dir, seed: int = SEED) -> dict:
    g = Generator(seed)
    g.make_people()
    g.make_matters()
    g.make_security()
    g.make_team_and_time()
    g.make_documents()
    g.make_near_duplicates()
    g.make_drafts()
    return g.write(out_dir)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "synthetic"
    print(json.dumps(generate(target)["counts"], indent=1))
