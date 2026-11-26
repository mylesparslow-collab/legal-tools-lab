#!/usr/bin/env python3
"""Seeded synthetic data generator for the adoption baseline demo.

Writes a roster, two differently shaped usage exports, survey responses and an
answer key. Everything here is invented. The generator does not import the
analyser: the answer key is computed from the generator's own clean, latent
data, so tests can check that the analyser recovers it from the messy exports.

Run:  python generate_synthetic.py
"""
import csv
import json
import os
import random
from collections import defaultdict
from datetime import date, timedelta

SEED = 20261207
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample_data")

PERIOD_START = date(2026, 9, 7)     # Monday, ISO week 37
N_WEEKS = 13
PERIOD_END = PERIOD_START + timedelta(days=7 * N_WEEKS - 1)
HOLIDAY_WEEK_INDEX = 7              # eighth week, 2026-W44
SURVEY_WEEK_INDEX = 11              # 2026-W48
NEW_OFFICE = "Lakeshore"
NEW_OFFICE_START = date(2026, 10, 5)
OVERCLAIM_PRACTICE = "Real estate"
TOOL_A, TOOL_B = "Assistant A", "Assistant B"
LAWYER_ROLES = ("partner", "counsel", "associate")
ROLES = ("partner", "counsel", "associate", "paralegal", "staff")

# practice: (partner, counsel, associate, paralegal, staff), adoption propensity
PRACTICES = {
    "Corporate": ((9, 5, 24, 7, 11), 0.60),
    "Disputes": ((8, 5, 22, 7, 10), 0.85),
    "Real estate": ((6, 4, 16, 5, 9), 0.22),
    "Banking and finance": ((6, 4, 16, 4, 8), 0.55),
    "Employment": ((5, 3, 12, 4, 7), 0.50),
    "Tax": ((4, 2, 10, 3, 6), 0.45),
    "Intellectual property": ((4, 2, 10, 3, 6), 0.60),
    "Private client": ((4, 2, 9, 3, 6), 0.35),
    "Regulatory": ((3, 2, 9, 3, 5), 0.50),
    "Competition": ((1, 1, 2, 1, 2), 0.50),
}
# office: (lawyers, non-lawyers, utc offset used in Assistant A timestamps)
OFFICES = {
    "Northgate": (55, 28, "+00:00"),
    "Harbour Quay": (42, 22, "+00:00"),
    "Eastfield": (34, 18, "+08:00"),
    "Westbrook": (27, 14, "-05:00"),
    "Southmere": (22, 12, "+01:00"),
    "Lakeshore": (15, 7, "+01:00"),
    "Riverside": (11, 6, "+00:00"),
    "Midvale": (4, 3, "+01:00"),
}
ROLE_FACTOR = {"partner": 0.7, "counsel": 0.9, "associate": 1.1, "paralegal": 0.9, "staff": 0.5}
GIVEN = ["Alder", "Bryn", "Cass", "Devon", "Ellis", "Finley", "Gray", "Harper", "Indigo", "Jules",
         "Kit", "Lane", "Marlow", "Noor", "Oakley", "Perry", "Quinn", "Reese", "Sage", "Tate",
         "Umber", "Vale", "Wren", "Xan", "Yael", "Zephyr"]
A_ACTIONS = [("chat_message", 0.60), ("file_upload", 0.20), ("project_query", 0.12),
             ("web_search", 0.06), ("beta_canvas", 0.02)]
B_COLUMNS = ["Docs prompts", "Mail prompts", "Meetings prompts", "Sheets prompts"]
B_WEIGHTS = [0.45, 0.30, 0.15, 0.10]


def week_label(monday):
    y, w, _ = monday.isocalendar()
    return "%d-W%02d" % (y, w)


def mondays():
    return [PERIOD_START + timedelta(days=7 * i) for i in range(N_WEEKS)]


def on_leave(p, d):
    return any(a <= d <= b for a, b in p["leave"])


def eligible(p, monday):
    """Independent copy of the denominator rule, used only for the answer key."""
    sunday = monday + timedelta(days=6)
    if p["start"] > sunday:
        return False
    if p["end"] is not None and p["end"] < monday:
        return False
    return not all(on_leave(p, monday + timedelta(days=i)) for i in range(5))


def practice_on(p, d):
    current = p["practice_history"][0][1]
    for eff, name in p["practice_history"]:
        if eff is None or eff <= d:
            current = name
    return current


def build_people(rng):
    people = []
    n = 0
    for practice, (counts, _) in PRACTICES.items():
        for role, k in zip(ROLES, counts):
            for _ in range(k):
                n += 1
                people.append({"role": role, "practice": practice})
    rng.shuffle(people)
    for i, p in enumerate(people, 1):
        p["id"] = "SYN-%04d" % i
        p["name"] = "%s Sample-%04d" % (rng.choice(GIVEN), i)
        p["email"] = "syn%04d@firm.example" % i
    lawyers = [p for p in people if p["role"] in LAWYER_ROLES]
    others = [p for p in people if p["role"] not in LAWYER_ROLES]
    # Keep the tiny practice out of the tiny and new offices so each planted
    # feature can be read on its own.
    for group, idx in ((lawyers, 0), (others, 1)):
        rng.shuffle(group)
        group.sort(key=lambda p: p["practice"] == "Competition", reverse=True)
        slots = []
        for office, spec in OFFICES.items():
            slots += [office] * spec[idx]
        slots.sort(key=lambda o: list(OFFICES).index(o))
        for p, office in zip(group, slots):
            p["office"] = office
    people.sort(key=lambda p: p["id"])
    return people


def assign_employment(rng, people):
    weeks = mondays()
    for p in people:
        p["start"] = date(2015, 1, 5) + timedelta(days=rng.randrange(0, 4000))
        p["end"] = None
        p["leave"] = []
        p["practice_history"] = [(None, p["practice"])]
        if p["office"] == NEW_OFFICE:
            p["start"] = NEW_OFFICE_START
    pool = [p for p in people if p["office"] != NEW_OFFICE and p["practice"] != "Competition"
            and p["office"] != "Midvale"]
    rng.shuffle(pool)
    starters, leavers, long_leave, changers = pool[:6], pool[6:9], pool[9:15], None
    for p in starters:
        p["start"] = PERIOD_START + timedelta(days=rng.randrange(8, 60))
    for p in leavers:
        p["end"] = PERIOD_START + timedelta(days=rng.randrange(25, 70))
    for p in long_leave:
        p["leave"].append((date(2026, 8, 17), date(2026, 12, 18)))
    lawyers = [p for p in pool[15:] if p["role"] in LAWYER_ROLES]
    changers = lawyers[:3]
    targets = ["Corporate", "Disputes", "Banking and finance", "Tax"]
    for p in changers:
        new = rng.choice([t for t in targets if t != p["practice"]])
        p["practice_history"].append((date(2026, 10, 19), new))
    special = {p["id"] for p in starters + leavers + long_leave}
    for p in people:
        if p["id"] in special or p["office"] == NEW_OFFICE:
            continue
        hol = weeks[HOLIDAY_WEEK_INDEX]
        if rng.random() < 0.20:
            p["leave"].append((hol, hol + timedelta(days=4)))
        if rng.random() < 0.45:
            w = weeks[rng.choice([i for i in range(N_WEEKS) if i != HOLIDAY_WEEK_INDEX])]
            p["leave"].append((w, w + timedelta(days=4)))
        if rng.random() < 0.40:
            w = weeks[rng.randrange(N_WEEKS)]
            d0 = w + timedelta(days=rng.randrange(0, 4))
            p["leave"].append((d0, d0 + timedelta(days=1)))
        p["leave"].sort()
    return {"starters": starters, "leavers": leavers, "long_leave": long_leave, "changers": changers}


def assign_licences_and_behaviour(rng, people):
    for p in people:
        role, practice = p["role"], p["practice"]
        if role in LAWYER_ROLES:
            lic_a = practice == "Disputes" or rng.random() < 0.70
            lic_b = True
        elif role == "paralegal":
            lic_a, lic_b = rng.random() < 0.50, True
        else:
            lic_a, lic_b = rng.random() < 0.20, rng.random() < 0.60
        p["lic"] = {TOOL_A: lic_a, TOOL_B: lic_b}
        base = PRACTICES[practice][1] * ROLE_FACTOR[role]
        if p["office"] == NEW_OFFICE:
            base *= 0.3
        p["behaviour"] = {}
        for tool, factor in ((TOOL_A, 1.0), (TOOL_B, 0.6)):
            if not p["lic"][tool] or rng.random() >= min(0.95, base * factor):
                continue
            adopt = 0 if rng.random() < 0.55 else rng.randrange(1, 12)
            p["behaviour"][tool] = {"adopt": adopt, "p": rng.uniform(0.45, 0.95),
                                    "mean": rng.uniform(2.0, 8.0)}
    heavy_pool = [p for p in people if p["role"] == "associate" and p["lic"][TOOL_A]
                  and p["practice"] in ("Disputes", "Corporate") and p["office"] != NEW_OFFICE
                  and p["end"] is None and p["start"] < PERIOD_START
                  and not any((b - a).days > 30 for a, b in p["leave"])]
    heavy = rng.sample(heavy_pool, 8)
    for p in heavy:
        p["behaviour"][TOOL_A] = {"adopt": 0, "p": 1.0, "mean": 55.0, "heavy": True}
    unlicensed_pool = [p for p in people if not p["lic"][TOOL_A] and p["role"] in LAWYER_ROLES
                       and p["office"] != NEW_OFFICE and p["end"] is None
                       and p["start"] < PERIOD_START and TOOL_B not in p["behaviour"]]
    unlicensed = rng.sample(unlicensed_pool, 2)
    for p in unlicensed:
        p["behaviour"][TOOL_A] = {"adopt": 3, "p": 0.6, "mean": 3.0}
    return heavy, unlicensed


def simulate_usage(rng, people):
    """Latent truth: (person id, tool, date) -> list of feature labels, one per interaction."""
    usage = defaultdict(list)
    weeks = mondays()
    for p in people:
        for tool, b in p["behaviour"].items():
            for wi, monday in enumerate(weeks):
                if wi < b["adopt"]:
                    continue
                prob = b["p"] * (0.45 if wi == HOLIDAY_WEEK_INDEX and not b.get("heavy") else 1.0)
                if rng.random() >= prob:
                    continue
                days = [monday + timedelta(days=i) for i in range(5)]
                days = [d for d in days if d >= p["start"] and (p["end"] is None or d <= p["end"])
                        and not on_leave(p, d)]
                if not days:
                    continue
                n = max(1, int(round(rng.lognormvariate(0, 0.5) * b["mean"])))
                for _ in range(n):
                    d = rng.choice(days)
                    if tool == TOOL_A:
                        feat = rng.choices([a for a, _ in A_ACTIONS], [w for _, w in A_ACTIONS])[0]
                    else:
                        feat = rng.choices(B_COLUMNS, B_WEIGHTS)[0]
                    usage[(p["id"], tool, d)].append(feat)
    # Planted: a few people log use during a week of full leave.
    candidates = []
    for p in people:
        if not p["behaviour"] or any((b - a).days > 30 for a, b in p["leave"]):
            continue
        for wi, monday in enumerate(weeks):
            if p["start"] <= monday and p["end"] is None and all(
                    on_leave(p, monday + timedelta(days=i)) for i in range(5)):
                candidates.append((p, monday))
    rng.shuffle(candidates)
    leave_usage = candidates[:5]
    for p, monday in leave_usage:
        tool = sorted(p["behaviour"])[0]
        feat = "chat_message" if tool == TOOL_A else "Mail prompts"
        usage[(p["id"], tool, monday + timedelta(days=2))].append(feat)
    return usage, leave_usage


def write_roster(people):
    path = os.path.join(OUT, "roster.csv")
    cols = ["person_id", "name", "email", "role", "practice", "office", "licence_assistant_a",
            "licence_assistant_b", "start_date", "end_date", "leave_periods", "effective_from"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for p in people:
            leave = ";".join("%s/%s" % (a.isoformat(), b.isoformat()) for a, b in p["leave"])
            for eff, practice in p["practice_history"]:
                w.writerow([p["id"], p["name"], p["email"], p["role"], practice, p["office"],
                            "yes" if p["lic"][TOOL_A] else "no", "yes" if p["lic"][TOOL_B] else "no",
                            p["start"].isoformat(), p["end"].isoformat() if p["end"] else "",
                            leave, eff.isoformat() if eff else ""])


def email_variant(rng, email):
    kind = rng.randrange(3)
    if kind == 0:
        return email.upper()
    if kind == 1:
        local, dom = email.split("@")
        return local.capitalize() + "@" + dom.title()
    return " " + email + " "


def name_variant(rng, name):
    kind = rng.randrange(3)
    if kind == 0:
        return name.upper()
    if kind == 1:
        return name.lower()
    return " " + name.replace(" ", "  ") + " "


def write_export_a(rng, people, usage):
    """Assistant A: one row per interaction, ISO timestamp with offset, user by email."""
    by_id = {p["id"]: p for p in people}
    rows, key = [], {"duplicate": 0, "unknown_user": 0, "bad_date": 0, "missing_user": 0,
                     "outside_period": 0, "identifier_repaired": 0, "unmapped_feature": 0,
                     "usage_without_licence": 0}
    eid = [100000]

    def make(email, d, action, offset):
        eid[0] += 1
        ts = "%sT%02d:%02d:%02d%s" % (d.isoformat(), rng.randrange(7, 20), rng.randrange(60),
                                      rng.randrange(60), offset)
        return ["evt-%d" % eid[0], ts, email, action, "firm-main"]

    for (pid, tool, d), feats in sorted(usage.items()):
        if tool != TOOL_A:
            continue
        p = by_id[pid]
        offset = OFFICES[p["office"]][2]
        for feat in feats:
            email = p["email"]
            if rng.random() < 0.12:
                email = email_variant(rng, email)
                key["identifier_repaired"] += 1
            if feat == "beta_canvas":
                key["unmapped_feature"] += 1
            if not p["lic"][TOOL_A]:
                key["usage_without_licence"] += 1
            rows.append(make(email, d, feat, offset))
    clean = len(rows)
    for i in sorted(rng.sample(range(clean), 40), reverse=True):
        rows.insert(i + 1, list(rows[i]))
        key["duplicate"] += 1
    in_period = [PERIOD_START + timedelta(days=i) for i in range(7 * N_WEEKS)]
    for _ in range(25):
        who = rng.choice(["contractor.one@vendor.example", "temp.two@firm.example",
                          "syn9999@firm.example"])
        rows.insert(rng.randrange(len(rows)), make(who, rng.choice(in_period), "chat_message", "+00:00"))
        key["unknown_user"] += 1
    for bad in ["not a date", "2026-13-45T10:00:00+00:00", "", "31/31/2026", "2026-10-05 25:99",
                "tomorrow"]:
        r = make(rng.choice(people)["email"], PERIOD_START, "chat_message", "+00:00")
        r[1] = bad
        rows.insert(rng.randrange(len(rows)), r)
        key["bad_date"] += 1
    for _ in range(4):
        rows.insert(rng.randrange(len(rows)), make("", rng.choice(in_period), "chat_message", "+00:00"))
        key["missing_user"] += 1
    for _ in range(12):
        d = PERIOD_START - timedelta(days=rng.randrange(1, 8))
        rows.insert(0, make(rng.choice(people)["email"], d, "chat_message", "+00:00"))
        key["outside_period"] += 1
    with open(os.path.join(OUT, "assistant_a_events.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "timestamp", "user_email", "action", "workspace"])
        w.writerows(rows)
    key["rows_read"] = len(rows)
    key["rows_kept"] = clean
    return key


def write_export_b(rng, people, usage):
    """Assistant B: one row per user per day, feature counts in columns, user by display name."""
    by_id = {p["id"]: p for p in people}
    key = {"duplicate": 0, "conflicting_duplicate": 0, "unknown_user": 0, "bad_date": 0,
           "bad_count": 0, "zero_count": 0, "identifier_repaired": 0, "alternate_date_format": 0}
    rows = []

    def fmt_date(d, alt=False):
        return d.strftime("%d %b %Y") if alt else d.strftime("%d/%m/%Y")

    used_keys = set()
    for (pid, tool, d), feats in sorted(usage.items(), key=lambda kv: (kv[0][2], kv[0][0])):
        if tool != TOOL_B:
            continue
        p = by_id[pid]
        used_keys.add((pid, d))
        name = p["name"]
        if rng.random() < 0.20:
            name = name_variant(rng, name)
            key["identifier_repaired"] += 1
        alt = rng.random() < 0.10
        if alt:
            key["alternate_date_format"] += 1
        counts = [feats.count(c) for c in B_COLUMNS]
        rows.append([fmt_date(d, alt), name, p["practice_history"][0][1]] + counts)
    clean = len(rows)
    picks = sorted(rng.sample(range(clean), 15), reverse=True)
    for n, i in enumerate(picks):
        dup = list(rows[i])
        if n < 5:
            dup[3] = dup[3] + 7
            key["conflicting_duplicate"] += 1
        else:
            key["duplicate"] += 1
        rows.insert(i + 1, dup)
    in_period = [PERIOD_START + timedelta(days=i) for i in range(7 * N_WEEKS)]
    non_users = [p for p in people if TOOL_B not in p["behaviour"]]

    def free_slot():
        while True:
            p, d = rng.choice(non_users), rng.choice(in_period)
            if (p["id"], d) not in used_keys:
                used_keys.add((p["id"], d))
                return p, d

    for _ in range(12):
        who = rng.choice(["Contractor Sample-9001", "Visiting Sample-9002"])
        rows.insert(rng.randrange(len(rows)), [fmt_date(rng.choice(in_period)), who, "External", 2, 0, 0, 0])
        key["unknown_user"] += 1
    for bad in ["31/02/2026", "2026/10/05", "", "week 3", "00/10/2026"]:
        p, _ = free_slot()
        rows.insert(rng.randrange(len(rows)), [bad, p["name"], p["practice"], 1, 0, 0, 0])
        key["bad_date"] += 1
    for bad in ["n/a", "-3", "two"]:
        p, d = free_slot()
        rows.insert(rng.randrange(len(rows)), [fmt_date(d), p["name"], p["practice"], bad, 0, 0, 0])
        key["bad_count"] += 1
    for _ in range(30):
        p, d = free_slot()
        rows.insert(rng.randrange(len(rows)), [fmt_date(d), p["name"], p["practice"], 0, 0, "", 0])
        key["zero_count"] += 1
    with open(os.path.join(OUT, "assistant_b_daily.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Report date", "User", "Department"] + B_COLUMNS)
        w.writerows(rows)
    key["rows_read"] = len(rows)
    key["rows_kept"] = clean
    return key


def write_survey(rng, people, usage):
    monday = mondays()[SURVEY_WEEK_INDEX]
    week_days = {monday + timedelta(days=i) for i in range(7)}
    month_days = {monday + timedelta(days=6 - i) for i in range(30)}
    used = defaultdict(lambda: {"7": set(), "30": set()})
    for (pid, tool, d) in usage:
        if d in week_days:
            used[pid]["7"].add(tool)
        if d in month_days:
            used[pid]["30"].add(tool)
    tool_id = {TOOL_A: "assistant_a", TOOL_B: "assistant_b"}
    cols = ["response_id", "role", "practice", "office", "used_7d", "used_30d", "days_per_week",
            "tasks", "output_destination", "check_frequency", "check_methods", "blockers",
            "confidence_rules", "confidence_skill", "comments"]
    blocker_w = {"unsure_allowed": 0.42, "training": 0.30, "trust": 0.26, "no_time": 0.22,
                 "client_restrictions": 0.14, "no_relevant_tasks": 0.08}
    comments = ["", "", "", "", "Would like a short worked example for my practice.",
                "Unsure which matters allow it.", "Useful for first drafts.", "No comment."]
    rows = []
    for p in people:
        if not eligible(p, monday):
            continue
        true7 = {tool_id[t] for t in used[p["id"]]["7"]}
        true30 = {tool_id[t] for t in used[p["id"]]["30"]}
        if rng.random() >= (0.72 if true30 else 0.45):
            continue
        practice = practice_on(p, monday)
        claim7 = set(true7)
        over = 0.65 if practice == OVERCLAIM_PRACTICE else 0.10
        if not claim7 and rng.random() < over:
            claim7 = {"assistant_a"} if p["lic"][TOOL_A] else {"assistant_b"}
        elif claim7 and rng.random() < 0.03:
            claim7 = set()
        claim30 = set(true30) | claim7
        if rng.random() < 0.08:
            claim7.add("other_tool")
            claim30.add("other_tool")
        user = bool(claim30 - {"none"})
        days = rng.choice(["1", "2_3", "2_3", "4_5"]) if claim7 else ("1" if user and rng.random() < 0.5 else "0")
        if user:
            tasks = [t for t, w in (("drafting", .55), ("summarising", .6), ("research", .4), ("review", .3),
                                    ("email", .45), ("chronology", .15), ("other", .05)) if rng.random() < w] or ["summarising"]
            dest = ["internal_only"] + [d for d, w in (("client_work_product", .35), ("court_filing", .04))
                                        if rng.random() < w]
            check = rng.choices(["always", "usually", "sometimes", "rarely", "never"], [45, 30, 15, 7, 3])[0]
            methods = ["do_not_check"] if check == "never" else (
                [m for m, w in (("read_in_full", .8), ("compare_source", .5), ("verify_citations", .3),
                                ("colleague_review", .15)) if rng.random() < w] or ["read_in_full"])
        else:
            tasks, dest, check, methods = ["none"], ["not_applicable"], "not_applicable", ["not_applicable"]
        blockers = [b for b, w in blocker_w.items() if rng.random() < w * (0.6 if claim7 else 1.2)] or ["nothing"]
        rows.append([None, p["role"], practice, p["office"],
                     "|".join(sorted(claim7)) or "none", "|".join(sorted(claim30)) or "none", days,
                     "|".join(tasks), "|".join(dest), check, "|".join(methods), "|".join(blockers),
                     str(rng.choice([1, 2, 2, 3, 3, 3, 4, 4, 5]) if "unsure_allowed" in blockers else rng.choice([3, 4, 4, 5])),
                     str(rng.choice([3, 4, 4, 5]) if claim7 else rng.choice([1, 2, 2, 3, 3, 4])),
                     rng.choice(comments)])
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r[0] = "R%04d" % i
    with open(os.path.join(OUT, "survey_responses.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    blocker_counts = defaultdict(int)
    for r in rows:
        for b in r[11].split("|"):
            blocker_counts[b] += 1
    real = {k: v for k, v in blocker_counts.items() if k != "nothing"}
    return {"responses": len(rows), "top_blocker": max(real, key=real.get)}


def compute_truth(people, usage, heavy, unlicensed, groups, leave_usage):
    weeks = mondays()
    active_days = defaultdict(set)      # person -> dates with any use
    tool_days = defaultdict(set)        # (person, tool) -> dates
    for (pid, tool, d), feats in usage.items():
        active_days[pid].add(d)
        tool_days[(pid, tool)].add(d)
    weekly = []
    for monday in weeks:
        days = {monday + timedelta(days=i) for i in range(7)}
        den = [p for p in people if p["role"] in LAWYER_ROLES and eligible(p, monday)]
        num = [p for p in den if active_days[p["id"]] & days]
        weekly.append({"week": week_label(monday), "active": len(num), "eligible": len(den)})
    last30 = {PERIOD_END - timedelta(days=i) for i in range(30)}
    on_roster = [p for p in people if p["start"] <= PERIOD_END and (p["end"] is None or p["end"] >= PERIOD_END)]
    licences = {}
    for tool in (TOOL_A, TOOL_B):
        lic = [p for p in on_roster if p["lic"][tool]]
        licences[tool] = {
            "licensed": len(lic),
            "activated": sum(1 for p in lic if tool_days[(p["id"], tool)]),
            "unused_30_days": sum(1 for p in lic if not (tool_days[(p["id"], tool)] & last30)),
        }
    totals = defaultdict(int)
    for (pid, tool, d), feats in usage.items():
        totals[pid] += len(feats)
    lawyers_by = lambda k, v: sum(1 for p in on_roster if p["role"] in LAWYER_ROLES and p[k] == v)
    return {
        "seed": SEED,
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "people": len(people),
        "weekly_active_lawyers": weekly,
        "holiday_week": week_label(weeks[HOLIDAY_WEEK_INDEX]),
        "survey_week": week_label(weeks[SURVEY_WEEK_INDEX]),
        "licences": licences,
        "heavy_users": sorted(p["id"] for p in heavy),
        "top_8_by_interactions": sorted(sorted(totals, key=totals.get, reverse=True)[:8]),
        "unlicensed_assistant_a_users": sorted(p["id"] for p in unlicensed),
        "practice_changers": sorted(p["id"] for p in groups["changers"]),
        "usage_in_full_leave_weeks": len(leave_usage),
        "new_office": NEW_OFFICE,
        "new_office_start": NEW_OFFICE_START.isoformat(),
        "new_office_lawyers": lawyers_by("office", NEW_OFFICE),
        "overclaim_practice": OVERCLAIM_PRACTICE,
        "small_practice": {"name": "Competition", "lawyers": lawyers_by("practice", "Competition")},
        "small_office": {"name": "Midvale", "lawyers": lawyers_by("office", "Midvale")},
        "roster_people_with_no_usage": sum(1 for p in people if not active_days[p["id"]]),
        "total_interactions": sum(totals.values()),
    }


def write_answer_key_md(key):
    w = key["weekly_active_lawyers"]
    rate = lambda r: "%d of %d (%.0f%%)" % (r["active"], r["eligible"], 100.0 * r["active"] / r["eligible"])
    lines = [
        "# Answer key",
        "",
        "Planted truths in the synthetic data. Written by `generate_synthetic.py` (seed %d) from its own" % key["seed"],
        "clean data, before any mess is injected into the exports. The tests in",
        "`tests/test_planted_truths.py` check that the analyser recovers each one from the messy files.",
        "The machine-readable copy is `sample_data/answer_key.json`.",
        "",
        "All people, practices, offices and numbers are invented.",
        "",
        "## Structure planted on purpose",
        "",
        "1. A few heavy users. Eight associates log roughly ten times the typical volume in Assistant A:",
        "   %s. They are the top eight people by interactions." % ", ".join(key["heavy_users"]),
        "2. Many licensed non-users. Assistant A: %d licensed, %d activated, %d unused in the last 30 days."
        % (key["licences"]["Assistant A"]["licensed"], key["licences"]["Assistant A"]["activated"],
           key["licences"]["Assistant A"]["unused_30_days"]),
        "   Assistant B: %d licensed, %d activated, %d unused in the last 30 days."
        % (key["licences"]["Assistant B"]["licensed"], key["licences"]["Assistant B"]["activated"],
           key["licences"]["Assistant B"]["unused_30_days"]),
        "3. One practice high on survey and low in logs. In %s most non-users say they used an approved"
        % key["overclaim_practice"],
        "   tool in the last 7 days. It has the largest survey-minus-log gap of any practice.",
        "4. A new office with low use. Everyone in %s starts on %s, so they are not in the"
        % (key["new_office"], key["new_office_start"]),
        "   denominator before then, and adoption there is low. It is the lowest office that is not suppressed.",
        "5. A holiday week dip. %s has the lowest weekly active rate of the period, even after people on"
        % key["holiday_week"],
        "   leave for the whole week are removed from the denominator.",
        "6. Rising adoption. About 45% of eventual users start part-way through the period, so the last four",
        "   weeks are higher than the first six. The demo comparison should call this an increase.",
        "7. Survey non-response bias. People with logged use respond at about 72%, others at about 45%.",
        "   The firm-wide survey figure is therefore higher than the log figure even without over-claiming.",
        "8. Small groups. %s has %d lawyers and %s has %d lawyers. Both must be suppressed, and"
        % (key["small_practice"]["name"], key["small_practice"]["lawyers"],
           key["small_office"]["name"], key["small_office"]["lawyers"]),
        "   one further group in each table must be suppressed so the total does not reveal them.",
        "",
        "## Weekly active lawyers, any approved tool (true values)",
        "",
        "| ISO week | Active of eligible |",
        "|---|---|",
    ] + ["| %s | %s |" % (r["week"], rate(r)) for r in w] + [
        "",
        "## Mess injected into the exports (exact counts)",
        "",
        "| Item | Assistant A export | Assistant B export |",
        "|---|---|---|",
    ]
    a, b = key["exports"]["assistant_a_events"], key["exports"]["assistant_b_daily"]
    for label, k in [("Rows in file", "rows_read"), ("Rows that are real usage (should be kept)", "rows_kept"),
                     ("Exact duplicate rows", "duplicate"), ("Conflicting duplicate rows", "conflicting_duplicate"),
                     ("Rows for users not on the roster", "unknown_user"), ("Rows with an unreadable date", "bad_date"),
                     ("Rows with no user", "missing_user"), ("Rows with an unreadable count", "bad_count"),
                     ("Rows with zero interactions", "zero_count"), ("Rows outside the period", "outside_period"),
                     ("Kept rows whose email or name needed case or spacing repair", "identifier_repaired"),
                     ("Kept rows with a feature not in the mapping", "unmapped_feature"),
                     ("Kept rows for a user without a licence", "usage_without_licence"),
                     ("Kept rows in the second date format", "alternate_date_format")]:
        lines.append("| %s | %s | %s |" % (label, a.get(k, 0), b.get(k, 0)))
    lines += [
        "",
        "Conflicting duplicates are placed directly after the true row, so the documented rule (keep the",
        "first row for a key) keeps the true value. A real export gives no such guarantee.",
        "",
        "## Other planted roster facts",
        "",
        "- %d people changed practice on 2026-10-19: %s." % (len(key["practice_changers"]), ", ".join(key["practice_changers"])),
        "- %d lawyers without an Assistant A licence have Assistant A usage: %s."
        % (len(key["unlicensed_assistant_a_users"]), ", ".join(key["unlicensed_assistant_a_users"])),
        "- %d person-weeks have usage logged during a week of full leave. They are excluded from both the"
        % key["usage_in_full_leave_weeks"],
        "  numerator and the denominator for that week.",
        "- %d of %d people on the roster have no usage at all. They count as zero, not as missing."
        % (key["roster_people_with_no_usage"], key["people"]),
        "- The most common survey blocker is `%s`; %d responses were generated." % (key["survey"]["top_blocker"], key["survey"]["responses"]),
        "",
    ]
    with open(os.path.join(HERE, "ANSWER_KEY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(SEED)
    people = build_people(rng)
    groups = assign_employment(rng, people)
    heavy, unlicensed = assign_licences_and_behaviour(rng, people)
    usage, leave_usage = simulate_usage(rng, people)
    write_roster(people)
    key_a = write_export_a(rng, people, usage)
    key_b = write_export_b(rng, people, usage)
    survey = write_survey(rng, people, usage)
    key = compute_truth(people, usage, heavy, unlicensed, groups, leave_usage)
    key["exports"] = {"assistant_a_events": key_a, "assistant_b_daily": key_b}
    key["survey"] = survey
    with open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, indent=2)
        f.write("\n")
    write_answer_key_md(key)
    print("Wrote %d people, %d Assistant A rows, %d Assistant B rows, %d survey responses to %s"
          % (len(people), key_a["rows_read"], key_b["rows_read"], survey["responses"], OUT))


if __name__ == "__main__":
    main()
