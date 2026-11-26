"""Build a baseline dict from config, roster, exports and survey responses."""
import json
import os
from datetime import date

from . import DEFINITIONS_VERSION
from . import ingest, survey as survey_mod, targets as targets_mod
from .metrics import Analysis, week_label
from .roster import load_roster, parse_iso


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def week_monday(label):
    """'2026-W48' -> the Monday of that ISO week."""
    year, _, week = label.partition("-W")
    return date.fromisocalendar(int(year), int(week), 1)


def run_ingest(config, base_dir, period_start, period_end, sources=None, roster_path=None):
    roster = load_roster(os.path.join(base_dir, roster_path or config["roster"]), config["tools"])
    pairs = []
    names = []
    for s in sources or config["sources"]:
        pairs.append((os.path.join(base_dir, s["file"]), ingest.load_mapping(os.path.join(base_dir, s["mapping"]))))
        names.append(s["file"])
    table, quality, unknown = ingest.ingest_all(pairs, roster, (period_start, period_end))
    for q, name in zip(quality["sources"], names):
        q["file"] = name
    return roster, table, quality, unknown


def build_baseline(config, base_dir, period_end=None, period_start=None, with_analysis=False):
    start = parse_iso(period_start or config["period_start"])
    end = parse_iso(period_end or config["period_end"])
    roster, table, quality, _ = run_ingest(config, base_dir, start, end)
    analysis = Analysis(roster, table, config, start, end)
    targets = load_json(os.path.join(base_dir, config["targets"])) if config.get("targets") else {}
    baseline = {
        "definitions_version": DEFINITIONS_VERSION,
        "meta": {
            "data_label": config.get("data_label", ""),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "weeks": [week_label(w) for w in analysis.weeks],
            "latest_week": week_label(analysis.weeks[-1]),
            "last_weeks": [week_label(w) for w in analysis.last_weeks],
            "tools": roster.tools,
            "lawyer_roles": sorted(analysis.lawyer_roles),
            "suppression_threshold": analysis.threshold,
            "regular_use": {"window_weeks": analysis.window, "min_active_weeks": analysis.min_active},
            "unused_licence_days": int(config.get("unused_licence_days", 30)),
            "compare_rules": config.get("compare", {}),
            "individual_level_output": False,
        },
        "headline": analysis.headline(),
        "weekly_trend": analysis.weekly_trend(),
        "tools": analysis.tools_table(),
        "breakdowns": {
            "practice": analysis.breakdown("practice", "lawyers"),
            "office": analysis.breakdown("office", "lawyers"),
            "role": analysis.breakdown("role", "all"),
        },
        "intensity": analysis.intensity(),
        "breadth": analysis.breadth(),
        "survey": None,
        "targets": targets_mod.evaluate(analysis, targets, quality),
        "data_quality": {"ingestion": quality, "roster": analysis.roster_quality()},
    }
    if config.get("survey_responses") and config.get("survey_definition"):
        label = config.get("survey_week") or week_label(analysis.weeks[-1])
        monday = week_monday(label)
        if monday in analysis.weeks:
            definition = survey_mod.load_definition(os.path.join(base_dir, config["survey_definition"]))
            raw = survey_mod.load_responses(os.path.join(base_dir, config["survey_responses"]))
            responses, sq = survey_mod.clean_responses(raw, definition)
            baseline["survey"] = survey_mod.survey_section(analysis, responses, definition, sq, monday)
        else:
            baseline["data_quality"]["survey_note"] = (
                "Survey week %s is outside this period, so the survey is not reported." % label)
    return (baseline, analysis) if with_analysis else baseline
