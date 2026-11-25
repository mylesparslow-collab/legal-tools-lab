import csv
import json
import os
import re

from baseline import survey, survey_render
from baseline.pipeline import load_json


def defn(root):
    return load_json(os.path.join(root, "survey", "survey.json"))


def test_survey_has_12_to_15_questions_and_one_free_text(root):
    qs = defn(root)["questions"]
    assert 12 <= len(qs) <= 15
    assert [q["id"] for q in qs if q["type"] == "text"] == ["comments"]
    assert defn(root)["estimated_minutes"] < 5
    assert len({q["id"] for q in qs}) == len(qs)


def test_survey_covers_the_required_topics(root):
    by_id = {q["id"]: {str(o["id"]) for o in q.get("options", [])} for q in defn(root)["questions"]}
    assert {"role", "practice", "office", "used_7d", "used_30d", "days_per_week", "tasks", "output_destination",
            "check_frequency", "check_methods", "blockers", "confidence_rules", "comments"} <= set(by_id)
    assert {"drafting", "summarising", "research", "review", "email", "chronology", "other"} <= by_id["tasks"]
    assert {"internal_only", "client_work_product", "court_filing"} <= by_id["output_destination"]
    assert {"trust", "training", "client_restrictions", "unsure_allowed", "no_time"} <= by_id["blockers"]
    assert by_id["role"] == {"partner", "counsel", "associate", "paralegal", "staff"}
    assert {"assistant_a", "assistant_b", "none"} <= by_id["used_7d"] == by_id["used_30d"]


def test_every_choice_question_offers_a_way_to_say_none_or_not_applicable(root):
    for q in defn(root)["questions"]:
        if q["type"] == "multi":
            assert any(o.get("exclusive") for o in q["options"]), q["id"]


def test_survey_does_not_ask_for_identity(root):
    d = defn(root)
    text = json.dumps(d["questions"]).lower()
    for word in ("your name", "email address", "employee id", "person_id", "date of birth"):
        assert word not in text
    assert "does not ask for your name" in d["intro"]


def test_committed_html_and_markdown_match_the_definition(root):
    d = defn(root)
    with open(os.path.join(root, "survey", "survey.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(root, "survey", "SURVEY.md"), encoding="utf-8") as f:
        md = f.read()
    assert page == survey_render.render_html(d)
    assert md == survey_render.render_markdown(d)
    for q in d["questions"]:
        assert 'data-qid="%s"' % q["id"] in page
    assert "Known biases" in md and "Self-report inflates use" in md and "Non-response" in md


def test_survey_form_is_self_contained(root):
    with open(os.path.join(root, "survey", "survey.html"), encoding="utf-8") as f:
        page = f.read()
    assert not re.search(r'(src|href)\s*=\s*"(https?:)?//', page)
    assert "fetch(" not in page and "XMLHttpRequest" not in page
    assert "prefers-color-scheme: dark" in page and 'name="viewport"' in page
    assert "JSON.stringify" in page


def test_sample_responses_are_valid_and_anonymous(root, config):
    path = os.path.join(root, config["survey_responses"])
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert not {"person_id", "name", "email"} & set(header)
    responses, q = survey.clean_responses(survey.load_responses(path), defn(root))
    assert q["responses_read"] == q["responses_used"] == len(responses) > 100
    assert q["invalid_answers_removed"] == 0 and q["responses_missing_required"] == 0


def test_invalid_answers_are_removed_and_counted(root):
    raw = [{"role": "wizard", "practice": "Tax", "office": "Northgate", "used_7d": "assistant_a|teleport",
            "used_30d": "assistant_a", "blockers": "", "comments": "x"}]
    responses, q = survey.clean_responses(raw, defn(root))
    assert responses[0]["role"] is None and responses[0]["used_7d"] == ["assistant_a"]
    assert q["invalid_answers_removed"] == 2 and q["responses_missing_required"] == 1


def test_json_responses_saved_by_the_form_can_be_loaded(root, tmp_path):
    payload = {"survey_id": "adoption-baseline", "version": "1.0", "answers": {
        "role": "associate", "practice": "Tax", "office": "Northgate", "used_7d": ["assistant_b"],
        "used_30d": ["assistant_a", "assistant_b"], "days_per_week": "2_3", "tasks": ["email"],
        "output_destination": ["internal_only"], "check_frequency": "always", "check_methods": ["read_in_full"],
        "blockers": ["nothing"], "confidence_rules": "4", "confidence_skill": "3", "comments": ""}}
    (tmp_path / "response-abc.json").write_text(json.dumps(payload), encoding="utf-8")
    responses, q = survey.clean_responses(survey.load_responses(str(tmp_path)), defn(root))
    assert q["invalid_answers_removed"] == 0 and q["responses_missing_required"] == 0
    assert survey.claims_approved_7d(responses[0]) and survey.claims_approved_30d(responses[0])


def test_other_tool_alone_is_not_a_claim_of_approved_use():
    assert not survey.claims_approved_7d({"used_7d": ["other_tool"]})
    assert not survey.claims_approved_7d({"used_7d": ["none"]})


def test_gap_is_claimed_rate_minus_logged_rate_for_the_same_group(baseline):
    o = baseline["survey"]["overall"]
    assert o["gap_points"] == round(100 * (o["claimed"]["n"] / o["claimed"]["d"] - o["logged"]["n"] / o["logged"]["d"]), 1)
    week = {w["week"]: w for w in baseline["weekly_trend"]}[baseline["survey"]["survey_week"]]
    assert (o["logged"]["n"], o["logged"]["d"]) == (week["n"], week["d"])


def test_free_text_is_counted_but_never_reproduced(baseline, root, config):
    with open(os.path.join(root, config["survey_responses"]), newline="", encoding="utf-8") as f:
        comments = {r["comments"] for r in csv.DictReader(f) if r["comments"]}
    blob = json.dumps(baseline)
    assert baseline["survey"]["free_text_comments"] > 0
    assert not any(c in blob for c in comments)
