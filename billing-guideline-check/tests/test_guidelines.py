import copy
import json
import os

import pytest

from billcheck import guidelines as G
from billcheck import intake
from billcheck.engine import CHECKS
from billcheck.model import DataError
from conftest import DATA, mk_rule


def raw(client):
    with open(os.path.join(DATA, "guidelines", client + ".json"), "r", encoding="utf-8") as handle:
        return G.loads(handle.read())


def doc(client):
    with open(os.path.join(DATA, "guideline_docs", client + ".txt"), "r", encoding="utf-8") as handle:
        return handle.read()


CLIENTS = ["brackenmoor", "luminqa", "ostervane", "pellwick", "quillfeather"]


def test_five_clients_on_file(guides):
    assert sorted(guides) == CLIENTS


@pytest.mark.parametrize("client", CLIENTS)
def test_guideline_file_is_valid(client):
    assert G.validate(raw(client)) == []


def test_schema_engine_and_rule_table_list_the_same_rule_types():
    with open(G.SCHEMA_PATH, "r", encoding="utf-8") as handle:
        schema = json.load(handle)
    enum = schema["properties"]["rules"]["items"]["properties"]["type"]["enum"]
    assert set(enum) == set(G.RULE_TYPES) == set(CHECKS)


def test_every_rule_type_is_used_by_at_least_one_client(guides):
    used = {r.type for g in guides.values() for r in g.rules}
    assert used == set(G.RULE_TYPES)


@pytest.mark.parametrize("client", CLIENTS)
def test_every_quote_is_verbatim_in_the_client_document(client, guides):
    text = " ".join(doc(client).split())
    for rule in guides[client].rules:
        assert rule.source_quote in text, rule.rule_id


@pytest.mark.parametrize("client", CLIENTS)
def test_every_source_ref_points_at_the_quoted_sentence(client, guides):
    for rule in guides[client].rules:
        assert intake.locate(doc(client), rule.source_quote) == rule.source_ref, rule.rule_id
        assert "page" in rule.source_ref


def test_missing_required_parameter_is_reported():
    data = raw("quillfeather")
    rule = next(r for r in data["rules"] if r["type"] == "daily_hour_cap")
    del rule["params"]["max_hours"]
    assert any("max_hours" in e for e in G.validate(data))


def test_unknown_parameter_is_reported():
    data = raw("pellwick")
    data["rules"][0]["params"]["surprise"] = 1
    assert any("unknown parameter 'surprise'" in e for e in G.validate(data))


def test_unknown_rule_type_and_bad_severity_are_reported():
    data = raw("pellwick")
    data["rules"][0]["type"] = "made_up"
    data["rules"][1]["severity"] = "fatal"
    errors = G.validate(data)
    assert any("made_up" in e for e in errors) and any("fatal" in e for e in errors)


def test_confirmed_rule_needs_a_name_and_date():
    data = raw("pellwick")
    del data["rules"][0]["confirmed_by"]
    data["rules"][1]["confirmed_on"] = "last week"
    errors = G.validate(data)
    assert any("confirmed_by" in e for e in errors) and any("confirmed_on" in e for e in errors)


def test_rule_without_quote_or_reference_is_rejected():
    data = {"client_id": "c", "client_name": "C", "document": "d", "rules": [mk_rule("duplicate_entries")]}
    data["rules"][0]["source_quote"] = " "
    del data["rules"][0]["source_ref"]
    errors = G.validate(data)
    assert any("source_quote" in e for e in errors) and any("source_ref" in e for e in errors)
    with pytest.raises(DataError):
        G.from_dict(data)


def test_repeated_rule_id_is_reported():
    data = raw("pellwick")
    data["rules"].append(copy.deepcopy(data["rules"][0]))
    assert any("repeated" in e for e in G.validate(data))


def test_code_table_says_how_far_it_was_checked_and_is_the_full_1997_set(data_dir):
    with open(os.path.join(data_dir, "utbms_sample_codes.json"), "r", encoding="utf-8") as handle:
        table = json.load(handle)
    assert "secondary source" in table["label"] and "not against the publisher's spreadsheets" in table["label"]
    assert "2026-11-26" in table["note"]
    # counts stated on the publisher's code set pages: 5 phases + 29 tasks, 11 activities, 24 expenses
    tasks = table["task_codes"]
    assert len([c for c in tasks if c.endswith("00")]) == 5 and len(tasks) == 34
    assert len(table["activity_codes"]) == 11 and len(table["expense_codes"]) == 24
    assert tasks["L330"] == "Depositions" and table["activity_codes"]["A105"] == "Communicate (in firm)"
