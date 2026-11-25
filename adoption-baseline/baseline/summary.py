"""Plain-language summary sentences, built only from a baseline dict.

Every number in these sentences is read from baseline.json. Nothing is typed
in by hand, and a test checks the sentences against the file.
"""


def pct(rate):
    return "%d%%" % int(rate * 100 + 0.5)


def frac(c, unit=""):
    return "%s (%d of %d%s)" % (pct(c["rate"]), c["n"], c["d"], unit)


def _visible(rows, measure):
    return [(r["group"], r["cells"][measure]) for r in rows
            if not r["cells"][measure]["suppressed"] and r["cells"][measure]["rate"] is not None]


def _hidden(rows, measure):
    return sum(1 for r in rows if r["cells"][measure]["suppressed"])


def build_summary(b):
    """Return a list of {"id": ..., "text": ...}."""
    out = []
    add = lambda ident, text: out.append({"id": ident, "text": text})
    h, meta = b["headline"], b["meta"]
    w4 = h["weekly_active_last_4_weeks"]
    weeks = meta["last_weeks"]
    if w4["rate"] is not None:
        add("weekly_active", "Over the last %d weeks (%s to %s), %s of lawyers used an approved AI tool in a "
            "given week (%d of %d lawyer-weeks)." % (len(weeks), weeks[0], weeks[-1], pct(w4["rate"]), w4["n"], w4["d"]))
    latest = h["weekly_active_latest"]
    if latest["rate"] is not None:
        add("latest_week", "In the latest week, %s, %d of %d lawyers were active (%s)."
            % (meta["latest_week"], latest["n"], latest["d"], pct(latest["rate"])))
    reg = h["regular_use"]
    if reg["rate"] is not None:
        add("regular_use", "%d of %d lawyers (%s) are regular users: active in at least %d of the last %d weeks."
            % (reg["n"], reg["d"], pct(reg["rate"]), meta["regular_use"]["min_active_weeks"],
               meta["regular_use"]["window_weeks"]))
    trend = [w for w in b["weekly_trend"] if w["rate"] is not None]
    if len(trend) > 1:
        low = min(trend, key=lambda w: w["rate"])
        add("lowest_week", "The lowest week was %s at %s (%d of %d)." % (low["week"], pct(low["rate"]), low["n"], low["d"]))
    targets = b["targets"]["targets"]
    if targets:
        bits = ["%s target of %s, %s" % ("month %s" % t["due_month"] if t.get("due_month") is not None else t["label"],
                                         pct(t["threshold"]), t["status"]) for t in targets]
        add("targets", "Against the plan (programme month %s): %s." % (b["targets"]["programme_month"], "; ".join(bits)))
    gates = b["targets"]["gates"]
    if gates:
        bits = []
        for g in gates:
            name = g.get("practice") or g["label"]
            if g["status"] == "cannot tell":
                bits.append("%s cannot tell (%s)" % (name, g["reason"]))
            else:
                bits.append("%s %s at %s (%d of %d lawyer-weeks)" % (name, g["status"], pct(g["rate"]), g["n"], g["d"]))
        add("gates", "Pilot gate of %s of pilot-practice lawyers active weekly: %s."
            % (pct(gates[0]["threshold"]), "; ".join(bits)))
    m = "weekly_active_last_4_weeks"
    for dim, noun, plural in (("practice", "practice", "practices"), ("office", "office", "offices")):
        table = b["breakdowns"].get(dim)
        if not table:
            continue
        vis = _visible(table["rows"], m)
        if len(vis) < 2:
            continue
        lo = min(vis, key=lambda gc: gc[1]["rate"])
        hi = max(vis, key=lambda gc: gc[1]["rate"])
        text = "By %s, weekly use among lawyers runs from %s in %s (%d of %d lawyer-weeks) to %s in %s (%d of %d)." % (
            noun, pct(lo[1]["rate"]), lo[0], lo[1]["n"], lo[1]["d"], pct(hi[1]["rate"]), hi[0], hi[1]["n"], hi[1]["d"])
        k = _hidden(table["rows"], m)
        if k:
            text += " %d %s not shown because a group is too small to report." % (k, plural + " are" if k > 1 else noun + " is")
        add("range_" + dim, text)
    tools = [t for t in b["tools"] if not t["cells"]["unused_licences"]["suppressed"] and t["cells"]["unused_licences"]["d"]]
    if tools:
        bits = ["%d of %d %s licences (%s)" % (t["cells"]["unused_licences"]["n"], t["cells"]["unused_licences"]["d"],
                                              t["tool"], pct(t["cells"]["unused_licences"]["rate"])) for t in tools]
        add("unused_licences", "%s had no use in the last %d days." % (" and ".join(bits), tools[0]["window_days"]))
    inten = b["intensity"]["by_tool"].get("any approved tool")
    if inten and inten.get("median") is not None and inten.get("top_decile_share") is not None:
        add("intensity", "Use is concentrated: the median active person logged %s interactions in %d weeks, and the "
            "top tenth of users (%d people) account for %s of all interactions."
            % (num(inten["median"]), b["intensity"]["window_weeks"], inten["top_decile_people"], pct(inten["top_decile_share"])))
    s = b.get("survey")
    if s and s["overall"]["claimed"]["rate"] is not None and s["overall"]["logged"]["rate"] is not None:
        o = s["overall"]
        text = ("In the survey (%d responses), %s of responding lawyers (%d of %d) said they used an approved tool in "
                "the last 7 days. Logs for the same week, %s, show %s of all lawyers (%d of %d)."
                % (s["responses"], pct(o["claimed"]["rate"]), o["claimed"]["n"], o["claimed"]["d"], s["survey_week"],
                   pct(o["logged"]["rate"]), o["logged"]["n"], o["logged"]["d"]))
        rows = [r for r in s["by_practice"] if r["gap_points"] is not None]
        if rows:
            top = max(rows, key=lambda r: r["gap_points"])
            text += " The widest gap is in %s: %s claimed (%d of %d) against %s logged (%d of %d)." % (
                top["group"], pct(top["claimed"]["rate"]), top["claimed"]["n"], top["claimed"]["d"],
                pct(top["logged"]["rate"]), top["logged"]["n"], top["logged"]["d"])
        add("survey_gap", text)
        blockers = s["tallies"].get("blockers")
        if blockers:
            real = {k: v for k, v in blockers["counts"].items() if v is not None and k != "nothing"}
            if real and blockers["answered"]:
                k = max(real, key=real.get)
                add("top_blocker", "The most common limit on use reported in the survey is \"%s\" (%d of %d responses)."
                    % (blockers["labels"][k], real[k], blockers["answered"]))
    t = b["data_quality"]["ingestion"]["totals"]
    add("data_quality", "%d of %d export rows were dropped and %d were repaired. Each is itemised under data quality."
        % (t["rows_dropped"], t["rows_read"], t["rows_repaired"]))
    return out


def num(x):
    return ("%.1f" % x).rstrip("0").rstrip(".")
