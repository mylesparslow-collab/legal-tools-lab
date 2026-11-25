"""Brown Act agenda checks: posting clocks, quorum by attendance mode, closed-session
descriptions, and item descriptions. Deterministic. Output is a list of findings for a
person to review; a 'pass' means the input met the coded rule, not that the meeting is lawful."""
import re
from datetime import datetime, timedelta

from .rules import brown_act, finding

ACTION_WORDS = ("approve", "adopt", "award", "authorize", "increase", "decrease", "terminate",
                "appoint", "execute", "amend", "accept", "ratify", "levy", "impose", "rescind")
PASSIVE_WORDS = ("discussion", "discuss", "update", "report", "presentation", "receive", "review", "information")
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion))?", re.I)


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def _hours(h):
    return f"{h:.1f}".rstrip("0").rstrip(".")


# ---------- posting clocks ----------

def check_clocks(a: dict) -> list:
    R = {c["id"]: c for c in brown_act()["clocks"]}
    m, p = a["meeting"], a.get("posting", {})
    start, mtype = _dt(m["start"]), m["type"]
    out = []

    def need(rule, when, label, required=True):
        if when is None:
            if required:
                out.append(finding("fail", rule["id"], f"{label}: no time recorded.", rule))
            return
        lead = (start - when).total_seconds() / 3600
        if lead >= rule["hours"]:
            out.append(finding("pass", rule["id"], f"{label} {_hours(lead)} hours before the meeting (needs {rule['hours']}).", rule))
        else:
            out.append(finding("fail", rule["id"], f"{label} {_hours(lead)} hours before the meeting. The rule is {rule['hours']} hours. "
                               f"Latest compliant time was {(start - timedelta(hours=rule['hours'])):%Y-%m-%d %H:%M}.", rule))

    if mtype == "regular":
        r = R["regular_agenda"]
        need(r, _dt(p.get("physical_posted_at")), "Agenda posted at a public location")
        if p.get("has_website", True):
            need(r, _dt(p.get("website_posted_at")), "Agenda posted on the website")
    elif mtype == "special":
        need(R["special_posting"], _dt(p.get("physical_posted_at")), "Call and notice posted at a public location")
        r = R["special_notice"]
        if p.get("has_website", True):
            need(r, _dt(p.get("website_posted_at")), "Notice posted on the website")
        if p.get("member_waivers_filed"):
            out.append(finding("info", "special_notice", "Written waivers of notice recorded for members.", r))
        else:
            need(r, _dt(p.get("members_notice_received_at")), "Written notice received by members")
        if p.get("media_requested_notice"):
            need(r, _dt(p.get("media_notified_at")), "Written notice received by media that asked for it")
    elif mtype in ("emergency", "dire_emergency"):
        if p.get("media_requested_notice"):
            if mtype == "emergency":
                need(R["emergency_media"], _dt(p.get("media_notified_at")), "Media notified")
            else:
                r = R["dire_emergency_media"]
                mn, bn = _dt(p.get("media_notified_at")), _dt(p.get("members_notified_at"))
                if mn is None:
                    out.append(finding("fail", r["id"], "Media notice: no time recorded.", r))
                else:
                    gap = abs((mn - bn).total_seconds()) / 60 if bn else None
                    out.append(finding("review", r["id"], "Media notified "
                               + (f"{gap:.0f} minutes from the member notice." if gap is not None else "but no member-notice time recorded.")
                               + " The text says 'at or near the time'; a person must judge whether this was near enough.", r))
        else:
            out.append(finding("info", "emergency_media", "No media outlet has asked for special-meeting notice, so the media notice step does not apply.", R["emergency_media"]))
        out.append(finding("info", "emergency_minutes", "After the meeting: " + R["emergency_minutes"]["what"] + ".", R["emergency_minutes"]))
    else:
        out.append(finding("review", "meeting_type", f"Unknown meeting type '{mtype}'. No clock checked."))

    if mtype == "regular":
        acc = brown_act()["accommodation_notice"]
        out.append(finding("pass" if a.get("accommodation_notice") else "fail", "accommodation_notice",
                           "Agenda includes the disability accommodation request information." if a.get("accommodation_notice")
                           else "Agenda does not say how, to whom and when to request a disability accommodation.", acc))
    return out


# ---------- quorum ----------

def quorum_needed(seats: int) -> int:
    return seats // 2 + 1


def just_cause_cap(meets_per_month: float) -> int:
    caps = brown_act()["modes"]["just_cause"]["annual_caps"]
    if meets_per_month <= 1:
        return caps["once_per_month_or_less"]
    if meets_per_month < 3:
        return caps["twice_per_month"]
    return caps["three_or_more_per_month"]


def check_quorum(a: dict) -> list:
    B = brown_act()
    M, common = B["modes"], B["alt_teleconference_common"]
    m = a["meeting"]
    seats = a["seats"]
    need = quorum_needed(seats)
    att = a.get("attendance", [])
    out = []
    by = lambda mode: [x for x in att if x["mode"] == mode]
    unknown = [x for x in att if x["mode"] not in M]
    for x in unknown:
        out.append(finding("review", "mode_unknown", f"{x['member']}: unknown attendance mode '{x['mode']}'."))
    present = [x for x in att if x["mode"] != "absent" and x["mode"] in M]
    inperson_equiv = by("in_person") + by("ada_remote")

    out.append(finding("info", "quorum_basis", f"{seats} seats, so a quorum is {need}. {len(present)} members participating.", B["quorum"]))
    if len(present) < need:
        out.append(finding("fail", "quorum_total", f"Only {len(present)} members participating; {need} needed.", B["quorum"]))
    else:
        out.append(finding("pass", "quorum_total", f"{len(present)} of {seats} participating meets the quorum of {need}.", B["quorum"]))

    # ADA accommodation: counts as in person
    for x in by("ada_remote"):
        r = M["ada_remote"]
        if not x.get("audio_visual", True) and not x.get("audio_only_disability_need"):
            out.append(finding("fail", "ada_av", f"{x['member']}: audio only, with no disability-related need to be off camera recorded.", r))
        if not x.get("adults_disclosed"):
            out.append(finding("review", "ada_adults", f"{x['member']}: before any action, must disclose whether adults are in the room and the general relationship.", r))
        out.append(finding("info", "ada_counts", f"{x['member']}: counted as attending in person at the meeting location. No location posting needed.", r))

    # Traditional teleconference
    tp = by("teleconf_posted")
    if tp:
        r = M["teleconf_posted"]
        for x in tp:
            for key, text in (("location_on_agenda", "location is not identified on the agenda"),
                              ("location_public", "location is not accessible to the public"),
                              ("agenda_posted_at_location", "agenda is not posted at the location")):
                if not x.get(key):
                    out.append(finding("fail", "teleconf_" + key, f"{x['member']}: teleconference {text}.", r))
        inside = [x for x in inperson_equiv if m.get("in_jurisdiction", True)] + [x for x in tp if x.get("location_in_jurisdiction")]
        lvl = "pass" if len(inside) >= need else "fail"
        out.append(finding(lvl, "teleconf_jurisdiction_quorum",
                           f"{len(inside)} members participating from inside the agency's territory; {need} needed when traditional teleconferencing is used.", r))

    # Alternative tracks under § 54953.8
    jc, em, other = by("just_cause"), by("emergency_remote"), by("other_54953_8")
    if jc or em or other:
        acc = m.get("public_remote_access")
        allowed = list(common["public_access"]["allowed"])
        if em and not jc and not other:
            allowed.append("phone_only")
        if acc in allowed:
            out.append(finding("pass", "alt_public_access", f"Public remote access recorded as '{acc}'.", common["public_access"]))
        else:
            out.append(finding("fail", "alt_public_access", f"Public remote access is '{acc}'. Needed: a two-way audiovisual platform, or two-way phone plus live webcast.", common["public_access"]))
        if not m.get("agenda_lists_remote_access"):
            out.append(finding("fail", "alt_agenda_access", "Agenda does not give the call-in or internet option for attending and commenting.", common["agenda_access_notice"]))
        for x in jc + em + other:
            if not x.get("adults_disclosed"):
                out.append(finding("review", "alt_adults", f"{x['member']}: before any action, must disclose whether adults are in the room and the general relationship.", common["adults_disclosure"]))
        out.append(finding("info", "alt_minutes", "Minutes must list each remote member and the provision relied on.", common["minutes_listing"]))

    if jc:
        r = M["just_cause"]
        start = _dt(m["start"])
        if start >= datetime.fromisoformat(r["sunset"]):
            out.append(finding("fail", "jc_sunset", f"§ 54953.8.3 is repealed as of {r['sunset']}. Meeting is on or after that date.", r))
        lvl = "pass" if len(inperson_equiv) >= need and m.get("in_jurisdiction", True) and m.get("open_to_public", True) else "fail"
        out.append(finding(lvl, "jc_inperson_quorum",
                           f"{len(inperson_equiv)} members in person at the single noticed location (disability-accommodation participants count as in person); {need} needed for anyone to use just cause.", r))
        cap = just_cause_cap(a.get("meets_per_month", 1))
        for x in jc:
            g = x.get("just_cause_ground")
            if g not in r["grounds"]:
                out.append(finding("fail", "jc_ground", f"{x['member']}: no listed just-cause ground recorded.", r))
            else:
                out.append(finding("info", "jc_ground", f"{x['member']}: ground is '{r['grounds'][g]}' (§ 54953.8.3(c)({g[1:]})). Minutes must name it.", r))
            if not x.get("audio_visual", True):
                out.append(finding("fail", "jc_av", f"{x['member']}: just cause requires both audio and video.", r))
            used = x.get("just_cause_uses_this_year", 0) + 1
            lvl = "pass" if used <= cap else "fail"
            out.append(finding(lvl, "jc_cap", f"{x['member']}: this would be use {used} this year; cap is {cap} for a body meeting {a.get('meets_per_month', 1)} time(s) a month.", r))

    if em:
        r = M["emergency_remote"]
        e = a.get("emergency", {})
        if not e.get("proclaimed"):
            out.append(finding("fail", "em_proclaimed", "No proclaimed state of emergency or local emergency recorded.", r))
        if e.get("first_teleconference_date") and e.get("last_findings_date"):
            days = (_dt(m["start"]).date() - _dt(e["last_findings_date"]).date()).days
            lvl = "pass" if days <= r["renewal_days"] else "fail"
            out.append(finding(lvl, "em_renewal", f"Last findings were {days} days before this meeting; renewal is required every {r['renewal_days']} days.", r))
        else:
            out.append(finding("review", "em_renewal", "No findings dates recorded. First use may be to decide whether meeting in person is unsafe.", r))

    for x in other:
        out.append(finding("review", "other_track", f"{x['member']}: relies on another § 54953.8 track. " + M["other_54953_8"]["what"], M["other_54953_8"]))
    if len({bool(tp), bool(jc), bool(em), bool(other)} - {False}) and sum(map(bool, (tp, jc, em, other))) > 1:
        out.append(finding("review", "mixed_modes", "More than one teleconference track is used at this meeting. § 54953.8(f) says the tracks are cumulative; how their quorum rules combine needs attorney review."))
    return out


# ---------- closed session descriptions ----------

def _norm(s):
    return re.sub(r"\s+", " ", s.replace("–", "—").replace(" - ", "—").replace("--", "—")).strip().upper()


def _norm_auth(s):
    s = re.sub(r"(?i)gov(?:ernment|['’]t|\.)?\s*code|section|§+|\s", "", s or "")
    return s.lower()


def check_closed_item(item: dict) -> list:
    S = brown_act()["closed_session_safe_harbors"]
    text, auth = item.get("text", ""), _norm_auth(item.get("authority"))
    T = _norm(text)
    label_of = lambda f: _norm(f["label"]).replace("— ", "—").replace(" —", "—")
    Tl = T.replace("— ", "—").replace(" —", "—")
    def related(x, y):  # same section, one cite possibly more specific than the other
        x, y = x.lower(), y.lower()
        short, long = sorted((x, y), key=len)
        return bool(short) and long.startswith(short) and (len(long) == len(short) or long[len(short)] == "(")
    cands = [f for f in S["forms"] if any(related(auth, c) for c in [f["authority"]] + f.get("alt_authority", []))]
    tag = f"Item {item.get('no', '?')}"
    if not cands:
        return [finding("review", "closed_no_form", f"{tag}: authority '{item.get('authority')}' has no coded § 54954.5 form. " + S["not_modeled"], S["standard"])]
    # prefer the form whose label appears in the text
    hit = [f for f in cands if label_of(f) in Tl]
    if len(hit) > 1:
        hit.sort(key=lambda f: -len(f["label"]))
        fielded = [f for f in hit if all(any(_norm(o) + ":" in T or _norm(o) in T for o in grp) for grp in f["fields"])]
        hit = fielded[:1] or hit[:1]
    out = []
    if not hit:
        f = cands[0]
        out.append(finding("review", "closed_label", f"{tag}: heading does not match the § 54954.5 form for § {f['authority']} ('{f['label']}'). "
                           "The form is optional, but without it the safe harbor may not apply.", f))
    else:
        f = hit[0]
    missing = []
    for grp in f["fields"]:
        found = next((o for o in grp if re.search(re.escape(_norm(o)) + r"[^:\n]*:\s*\S", T)), None)
        if not found:
            missing.append(" or ".join(grp))
        elif found in f.get("field_checks", {}):
            val = re.search(re.escape(found) + r"[^:\n]*:\s*(.+)", text, re.I)
            if val and not re.search(f["field_checks"][found], val.group(1), re.I):
                out.append(finding("review", "closed_field_value", f"{tag}: '{found}' should say whether instruction concerns price, terms of payment, or both.", f))
    if f.get("needs_number") and not missing:
        grp = f["fields"][0][0]
        val = re.search(re.escape(grp) + r"[^:\n]*:\s*(.+)", text, re.I)
        if not (val and re.search(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", val.group(1), re.I)):
            out.append(finding("review", "closed_number", f"{tag}: the form calls for the number of potential cases.", f))
    if missing:
        out.append(finding("fail", "closed_fields", f"{tag}: missing from the § 54954.5 form: {'; '.join(missing)}.", f))
    if f.get("reminder"):
        out.append(finding("info", "closed_reminder", f"{tag}: {f['reminder']}", f))
    if f.get("note") and re.search(r"cyber|ransomware|network|infrastructure", text + item.get("title", ""), re.I):
        out.append(finding("info", "closed_cyber", f"{tag}: {f['note']}", f))
    if not any(x["level"] in ("fail", "review") for x in out):
        out.append(finding("pass", "closed_ok", f"{tag}: matches the § 54954.5 form '{f['label']}'.", f))
    return out


# ---------- open-session descriptions ----------

def check_open_item(item: dict, meeting_type: str = "regular") -> list:
    B = brown_act()
    D = B["description"]
    desc = (item.get("description") or "").strip()
    words = re.findall(r"[A-Za-z0-9$%.,'’/-]+", desc)
    tag = f"Item {item.get('no', '?')}"
    out = []
    if len(words) < 4:
        out.append(finding("review", "desc_thin", f"{tag}: description is {len(words)} word(s) ('{desc}'). It may not tell the public what will be discussed.", D))
    elif len(words) > D["guideline_words"]:
        out.append(finding("info", "desc_long", f"{tag}: description is {len(words)} words. The statute says {D['guideline_words']} is generally enough; longer is allowed.", D))
    report = item.get("staff_report") or ""
    if report:
        rec = " ".join(re.findall(r"(?is)(?:recommend\w*|requested action|staff asks)[^.]*\.[^.]*\.", report)) or report
        d_low = desc.lower()
        acts = sorted({w for w in ACTION_WORDS if re.search(rf"\b{w}\w*", rec, re.I) and not re.search(rf"\b{w[:5]}", d_low)})
        passive = any(re.search(rf"\b{w}", d_low) for w in PASSIVE_WORDS) and not any(re.search(rf"\b{w[:5]}", d_low) for w in ACTION_WORDS)
        if acts and passive:
            out.append(finding("fail", "creep_action", f"{tag}: description reads as discussion only, but the staff report recommends action ({', '.join(acts)}).", D))
        elif acts:
            out.append(finding("review", "creep_action", f"{tag}: staff report recommends action not named in the description ({', '.join(acts)}).", D))
        money = {re.sub(r"\s", "", x) for x in MONEY.findall(report)} - {re.sub(r"\s", "", x) for x in MONEY.findall(desc)}
        if money and not MONEY.search(desc):
            out.append(finding("review", "creep_money", f"{tag}: staff report involves {', '.join(sorted(money)[:3])} but the description gives no amount.", D))
    if meeting_type == "special" and re.search(r"salar|compensation|fringe benefit|pay increase", desc + " " + report, re.I) \
            and re.search(r"general manager|executive|chief|director|board member|councilmember|superintendent", desc + " " + report, re.I) \
            and not re.search(r"\bbudget\b", desc, re.I):
        out.append(finding("fail", "special_pay", f"{tag}: appears to concern executive or board pay at a special meeting.", B["special_meeting_pay_bar"]))
    if not out:
        out.append(finding("pass", "desc_ok", f"{tag}: description is {len(words)} words; no mismatch with the staff report detected.", D))
    return out


def validate(a: dict) -> dict:
    sections = {"clocks": check_clocks(a), "quorum": check_quorum(a), "items": []}
    for it in a.get("items", []):
        fs = check_closed_item(it) if it.get("section") == "closed" else check_open_item(it, a["meeting"]["type"])
        sections["items"].extend(fs)
    allf = [f for v in sections.values() for f in v]
    counts = {k: sum(1 for f in allf if f["level"] == k) for k in ("fail", "review", "info", "pass")}
    return {"agency": a.get("agency"), "body": a.get("body"), "meeting": a["meeting"], "counts": counts, "sections": sections}
