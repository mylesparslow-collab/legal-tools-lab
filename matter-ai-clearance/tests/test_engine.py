"""Clearance engine: evaluator, precedence, default-deny, and each sample situation."""
import copy
import inspect
import itertools

import pytest

from clearance import engine
from clearance.store import load_policy

from conftest import by_id

CLEARED = ("ALLOWED", "ALLOWED_WITH_CONDITIONS")
PHI_LANE = {"suite-b.doc-summary", "review-d.review"}
MODES = ("block_feature", "exclude_class")


def with_mode(policy, mode, **rollup):
    """A copy of the policy with the roll-up option set explicitly, so no test leans on the default."""
    p = copy.deepcopy(policy)
    p["rollup"]["restricted_class_denied"] = mode
    p["rollup"].update(rollup)
    return p


# ----------------------------------------------------------------- evaluator

def test_evaluator_treats_missing_and_null_as_unknown():
    ctx = {"feature": {"baa": None, "web": False}}
    assert engine.lookup(ctx, "feature.baa") == "unknown"
    assert engine.lookup(ctx, "feature.nope.deeper") == "unknown"
    assert engine.test({"fact": "feature.baa", "op": "ne", "value": True}, ctx)
    assert engine.test({"fact": "feature.nope", "op": "is_unknown"}, ctx)
    assert not engine.test({"fact": "feature.web", "op": "ne", "value": False}, ctx)


def test_evaluator_is_strict_about_types():
    # The string "true" or the number 1 must not pass a check for boolean true.
    for v in ("true", "yes", 1, "unknown"):
        assert engine.test({"fact": "f.x", "op": "ne", "value": True}, {"f": {"x": v}})
    assert not engine.test({"fact": "f.x", "op": "ne", "value": True}, {"f": {"x": True}})


def test_evaluator_list_number_and_tree_operators():
    ctx = {"f": {"tools": ["a", "b"], "days": 30, "max": 7, "s": "unknown"}}
    assert engine.test({"fact": "f.tools", "op": "contains", "value": "a"}, ctx)
    assert engine.test({"fact": "f.s", "op": "not_contains", "value": "a"}, ctx)
    assert engine.test({"fact": "f.days", "op": "gt", "value_fact": "f.max"}, ctx)
    assert not engine.test({"fact": "f.s", "op": "gt", "value": 1}, ctx)
    assert engine.test({"all": [{"fact": "f.days", "op": "is_number"}, {"not": {"fact": "f.tools", "op": "is_unknown"}}]}, ctx)
    assert engine.test({"any": [{"fact": "f.days", "op": "eq", "value": 1}, {"fact": "f.tools", "op": "is_list"}]}, ctx)
    with pytest.raises(ValueError):
        engine.test({"fact": "f.days", "op": "roughly", "value": 1}, ctx)


def test_most_restrictive_decision_wins(policy):
    order = policy["decision_precedence"]
    assert order == ["NOT_ALLOWED", "HOLD_FOR_REVIEW", "ALLOWED_WITH_CONDITIONS", "ALLOWED"]
    for a, b in itertools.permutations(order, 2):
        assert engine.most_restrictive([a, b], order) == min(a, b, key=order.index)


# -------------------------------------------------------------------- policy

def test_every_rule_has_id_text_owner_and_review_date(policy):
    assert len(policy["rules"]) >= 30
    for r in policy["rules"]:
        assert r["id"].startswith("POL-") and len(r["text"]) > 20
        assert r["owner_role"] and len(r["review_date"]) == 10


def test_policy_loader_rejects_duplicates_and_missing_fields(tmp_path, policy):
    import json
    bad = copy.deepcopy(policy)
    bad["rules"].append(copy.deepcopy(bad["rules"][0]))
    p = tmp_path / "p.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_policy(p)
    bad = copy.deepcopy(policy)
    del bad["rules"][0]["owner_role"]
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_policy(p)


def test_engine_source_holds_no_rule_ids_or_clause_classes():
    src = inspect.getsource(engine)
    for token in ("POL-", "ai_prohibited", "consent_required", "baa_covers_feature", "no_training"):
        assert token not in src


def test_rule_text_changes_flow_through_without_code_changes(clear, policy):
    p = copy.deepcopy(policy)
    p["rules"] = [r for r in p["rules"] if r["id"] != "POL-CT-02"]
    assert clear("M-1007")["counts"]["NOT_ALLOWED"] == 10
    assert clear("M-1007", policy_=p)["counts"]["NOT_ALLOWED"] < 10


# ------------------------------------------------------------- client terms

def test_prohibiting_client_blocks_every_feature_and_quotes_the_clause(clear, store):
    rec = clear("M-1007")
    assert rec["counts"]["NOT_ALLOWED"] == len(rec["decisions"])
    assert rec["banner"] == "AI: not allowed on this matter (terms prohibit AI)"
    d = by_id(rec)["review-d.review"]
    assert d["rule_ids"] == ["POL-CT-02"]
    ev = d["drivers"][0]["evidence"]
    assert {e["document_id"] for e in ev} == {"orrinthe-ocg-2026", "orrinthe-el-2026"}
    for e in ev:
        assert store.document_text(e["document_id"])[e["start"]:e["end"]] == e["quote"]


def test_silent_client_on_plain_commercial_matter_is_allowed_within_lanes(clear):
    rec = clear("M-1003")
    d = by_id(rec)
    assert d["suite-b.doc-summary"]["decision"] == "ALLOWED"
    assert d["suite-b.doc-summary"]["rule_ids"] == ["POL-CT-16"]
    assert d["assistant-a.chat-web"]["decision"] == "NOT_ALLOWED"       # lane does not list client data
    assert d["research-c.brief-upload"]["decision"] == "NOT_ALLOWED"    # training terms unknown
    assert d["transcribe-e.dictation"]["decision"] == "NOT_ALLOWED"     # proposed tool
    assert rec["flags"] == {"needs_analyst_review": False, "unknown_inputs": []}


def test_consent_required_without_consent_is_not_allowed(clear):
    rec = clear("M-1009")
    assert rec["counts"]["NOT_ALLOWED"] == 10
    assert "POL-CT-03" in by_id(rec)["suite-b.doc-summary"]["rule_ids"]


def test_consent_on_file_clears_only_the_features_it_names(clear, store):
    m = store.matter("M-1009")
    m["consents"] = [{"from": "tessaly", "feature_ids": ["suite-b.doc-summary"], "reference": "Letter 7 (fictional)"}]
    d = by_id(clear(m))
    assert d["suite-b.doc-summary"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert any("Letter 7" in c["text"] for c in d["suite-b.doc-summary"]["conditions"])
    assert d["suite-b.email"]["decision"] == "NOT_ALLOWED"


def test_consent_from_the_wrong_party_does_not_count(clear, store):
    m = store.matter("M-1009")
    m["consents"] = [{"from": "marlowetind", "feature_ids": "all", "reference": "x"}]
    assert clear(m)["counts"]["NOT_ALLOWED"] == 10


def test_conditions_are_listed_for_notice_billing_and_review(clear):
    d = by_id(clear("M-1011"))["research-c.qa"]
    assert d["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert [c["short"] for c in d["conditions"]] == ["notice to Quillfether", "billing review", "attorney review"]
    assert d["rule_ids"] == ["POL-CT-05", "POL-CT-12", "POL-CT-13"]
    notice = next(c for c in d["conditions"] if c["rule_id"] == "POL-CT-05")
    assert "notice given: no" in notice["text"]
    drivers = {x["rule_id"]: x for x in d["drivers"]}
    assert "disclose on each invoice" in " ".join(e["quote"] for e in drivers["POL-CT-12"]["evidence"])


def test_conflicting_terms_are_flagged_and_nothing_is_cleared(clear):
    rec = clear("M-1010")
    assert rec["flags"]["needs_analyst_review"] is True
    assert rec["banner"].endswith("terms need analyst review")
    assert all(d["decision"] not in CLEARED for d in rec["decisions"])
    d = by_id(rec)["suite-b.doc-summary"]
    conflict = next(x for x in d["drivers"] if x["rule_id"] == "POL-CT-14")
    assert {e["class"] for e in conflict["evidence"]} >= {"ai_prohibited", "ai_permitted"}
    assert rec["terms"][0]["conflicts"]


def test_conflict_alone_holds_rather_than_picking_a_side(clear, policy):
    # Take away the prohibition rule: the conflict rule must still stop use, as a hold.
    p = copy.deepcopy(policy)
    p["rules"] = [r for r in p["rules"] if r["id"] != "POL-CT-02"]
    rec = clear("M-1010", policy_=p)
    assert by_id(rec)["suite-b.doc-summary"]["decision"] == "HOLD_FOR_REVIEW"
    assert by_id(rec)["suite-b.doc-summary"]["rule_ids"] == ["POL-CT-14"]


def test_ambiguous_terms_hold_for_review(clear):
    rec = clear("M-1012")
    d = by_id(rec)["review-d.review"]
    assert d["decision"] == "HOLD_FOR_REVIEW" and "POL-CT-15" in d["rule_ids"]
    assert rec["counts"]["ALLOWED"] == rec["counts"]["ALLOWED_WITH_CONDITIONS"] == 0


def test_terms_not_on_file_hold_for_review(clear):
    rec = clear("M-1016")
    assert by_id(rec)["suite-b.doc-summary"]["rule_ids"] == ["POL-CT-01"]
    assert rec["banner"] == "AI: on hold for review (client terms not on file)"


def test_approved_tools_only_blocks_tools_off_the_list(clear):
    d = by_id(clear("M-1001"))
    assert "POL-CT-08" in d["assistant-a.file-analysis"]["rule_ids"]
    assert d["assistant-a.file-analysis"]["decision"] == "NOT_ALLOWED"
    assert "POL-CT-08" not in d["suite-b.doc-summary"]["rule_ids"]


def test_approved_tools_only_with_no_list_on_file_is_a_hold(clear, store, monkeypatch):
    client = dict(store.clients["quenby"])
    client.pop("approved_tools")
    monkeypatch.setitem(store.clients, "quenby", client)
    m = store.matter("M-1001")
    m["data_flags"]["phi"] = "no"
    d = by_id(clear(m))["suite-b.doc-summary"]
    assert d["decision"] == "HOLD_FOR_REVIEW" and "POL-CT-07" in d["rule_ids"]


def test_retention_limit_recorded_by_analyst_is_enforced(clear, store):
    m = store.matter("M-1009")
    m["consents"] = [{"from": "tessaly", "feature_ids": "all", "reference": "x"}]
    d = by_id(clear(m))
    assert "POL-CT-10" in d["assistant-a.file-analysis"]["rule_ids"]     # 30 days against a limit of 0
    assert d["assistant-a.file-analysis"]["decision"] == "NOT_ALLOWED"
    assert "POL-CT-10" in d["suite-b.meeting-notes"]["rule_ids"]         # unknown retention
    assert d["review-d.review"]["decision"] == "ALLOWED_WITH_CONDITIONS"


def test_residency_clause_without_analyst_findings_is_a_hold(clear, store, monkeypatch):
    client = dict(store.clients["tessaly"])
    client.pop("analyst_findings")
    monkeypatch.setitem(store.clients, "tessaly", client)
    m = store.matter("M-1009")
    m["consents"] = [{"from": "tessaly", "feature_ids": "all", "reference": "x"}]
    d = by_id(clear(m))["review-d.review"]
    assert d["decision"] == "HOLD_FOR_REVIEW" and d["rule_ids"] == ["POL-CT-09"]


def test_analyst_scope_note_limits_a_clause_to_one_data_class(clear):
    d = by_id(clear("M-1001"))["suite-b.email"]
    # Clause 3.6 asks for written confirmation for patient information only.
    assert d["by_data_class"]["client_confidential"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert "POL-CT-03" not in d["by_data_class"]["client_confidential"]["rule_ids"]
    assert "POL-CT-03" in d["by_data_class"]["phi"]["rule_ids"]


# ------------------------------------------------- most restrictive source

def test_insurer_guidelines_layer_on_top_of_a_permissive_client(clear):
    without = clear("M-1006")
    with_insurer = clear("M-1005")
    assert without["counts"]["ALLOWED_WITH_CONDITIONS"] == 7
    assert with_insurer["counts"]["NOT_ALLOWED"] == 10
    d = by_id(with_insurer)["suite-b.doc-summary"]
    blocker = next(x for x in d["drivers"] if x["rule_id"] == "POL-CT-03")
    assert blocker["party_id"] == "marlowetind"
    assert blocker["evidence"][0]["document_id"] == "marlowetind-guidelines-2026"
    # The client's own letter permits AI. The stricter source still wins.
    assert "ai_permitted" in with_insurer["terms"][0]["classes"]


def test_insurer_consent_clears_the_insurer_requirement_only(clear, store):
    m = store.matter("M-1005")
    m["consents"] = [{"from": "marlowetind", "feature_ids": ["review-d.review"], "reference": "Claims approval 44 (fictional)"}]
    held = by_id(clear(m))["review-d.review"]
    # The insurer's guidelines also limit which tools may be used. With no list on file that is a hold.
    assert held["decision"] == "HOLD_FOR_REVIEW" and held["rule_ids"] == ["POL-CT-07"]
    m["additional_terms"][0]["approved_tools"] = ["review-d"]
    d = by_id(clear(m))
    assert d["review-d.review"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert d["suite-b.doc-summary"]["decision"] == "NOT_ALLOWED"


def test_co_counsel_protocol_is_read_as_a_second_source(clear):
    rec = clear("M-1015")
    assert [t["role"] for t in rec["terms"]] == ["client", "co_counsel"]
    assert rec["terms"][0]["status"] == "silent"
    assert rec["counts"]["ALLOWED"] == 0


# -------------------------------------------------------- protective orders

@pytest.mark.parametrize("mode", MODES)
def test_protective_order_overrides_client_consent(clear, policy, mode):
    """M-1008: the client consented to two features. The order bars outside vendors."""
    rec = clear("M-1008", policy_=with_mode(policy, mode))
    d = by_id(rec)
    for fid in ("suite-b.doc-summary", "review-d.review"):
        assert any(x["rule_id"] == "POL-CT-04" for x in d[fid]["drivers"])              # consent is on file
        assert d[fid]["by_data_class"]["client_confidential"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    blocked = d["suite-b.doc-summary"]
    assert blocked["by_data_class"]["protective_order_material"]["decision"] == "NOT_ALLOWED"
    assert "POL-PO-04" in blocked["by_data_class"]["protective_order_material"]["rule_ids"]
    po = next(x for x in blocked["drivers"] if x["rule_id"] == "POL-PO-04")
    assert "no outside vendor is listed" in po["evidence"][0]["quote"]
    # The firm-hosted feature is the only one that may receive order material, in either mode.
    assert d["review-d.review"]["by_data_class"]["protective_order_material"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert rec["banner"].endswith("no protective-order material in any tool except Review D")
    if mode == "block_feature":
        assert blocked["decision"] == "NOT_ALLOWED" and "order bars vendor processing" in blocked["reasons"]
    else:
        assert blocked["decision"] == "ALLOWED_WITH_CONDITIONS"
        assert "no protective-order material" in [c["short"] for c in blocked["conditions"]]


@pytest.mark.parametrize("mode", MODES)
def test_order_that_bars_ai_overrides_consent_for_every_feature(clear, store, policy, mode):
    m = store.matter("M-1008")
    m["protective_order"]["restrictions"]["ai_use"] = "prohibited"
    m["consents"] = [{"from": "tessaly", "feature_ids": "all", "reference": "Blanket consent (fictional)"}]
    rec = clear(m, policy_=with_mode(policy, mode))
    for d in rec["decisions"]:
        assert d["by_data_class"]["protective_order_material"]["decision"] == "NOT_ALLOWED"
        assert "POL-PO-02" in d["by_data_class"]["protective_order_material"]["rule_ids"]
    d = by_id(rec)["review-d.review"]
    assert any(x["rule_id"] == "POL-CT-04" for x in d["drivers"])
    if mode == "block_feature":
        assert rec["counts"]["NOT_ALLOWED"] == 10
        assert "protective order bars AI use" in rec["banner"]
    else:
        assert d["decision"] == "ALLOWED_WITH_CONDITIONS"
        assert "no protective-order material" in [c["short"] for c in d["conditions"]]
    assert rec["banner"].endswith("no protective-order material in any tool")


def test_order_silent_on_ai_holds_order_material(clear, policy):
    """M-1004. The hold must stay a hold: stricter roll-up must not turn it into a denial."""
    d = by_id(clear("M-1004", policy_=with_mode(policy, "block_feature")))["review-d.review"]
    assert d["by_data_class"]["protective_order_material"] == {"decision": "HOLD_FOR_REVIEW", "rule_ids": ["POL-PO-03"]}
    assert d["by_data_class"]["client_confidential"]["decision"] == "ALLOWED"
    assert d["decision"] == "HOLD_FOR_REVIEW" and d["rule_ids"] == ["POL-CT-16", "POL-PO-03"]
    assert d["reasons"] == ["protective order silent or not yet read for AI terms"]
    d = by_id(clear("M-1004", policy_=with_mode(policy, "exclude_class")))["review-d.review"]
    assert d["by_data_class"]["protective_order_material"] == {"decision": "HOLD_FOR_REVIEW", "rule_ids": ["POL-PO-03"]}
    assert d["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert d["pending_data_classes"] == ["protective_order_material"]
    assert any("until the hold is cleared" in c["text"] for c in d["conditions"])


def test_vendor_undertaking_decides_which_feature_gets_order_material(clear, store):
    d = by_id(clear("M-1013"))
    assert d["review-d.review"]["by_data_class"]["protective_order_material"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert "POL-PO-05" in d["suite-b.doc-summary"]["by_data_class"]["protective_order_material"]["rule_ids"]
    m = store.matter("M-1013")
    m["protective_order"]["restrictions"]["vendor_processing"] = "barred"
    d2 = by_id(clear(m))
    assert "POL-PO-04" in d2["suite-b.doc-summary"]["by_data_class"]["protective_order_material"]["rule_ids"]
    assert d2["review-d.review"]["by_data_class"]["protective_order_material"]["decision"] == "ALLOWED_WITH_CONDITIONS"


@pytest.mark.parametrize("field", ["ai_use", "vendor_processing", "no_retention_after_matter", "attorneys_eyes_only_tier"])
def test_unknown_order_term_never_clears_order_material(clear, store, field):
    m = store.matter("M-1013")
    m["protective_order"]["restrictions"][field] = "unknown"
    rec = clear(m)
    assert all(d["by_data_class"]["protective_order_material"]["decision"] not in CLEARED for d in rec["decisions"])
    assert "protective_order.restrictions." + field in rec["flags"]["unknown_inputs"]


@pytest.mark.parametrize("mode", MODES)
def test_unknown_whether_an_order_exists_holds_rather_than_denies(clear, store, policy, mode):
    """Rules for a class that may not even be present run on unknown facts. That is a hold, not a denial."""
    m = store.matter("M-1003")
    before = by_id(clear(m, policy_=with_mode(policy, mode)))
    m["protective_order"] = {"present": "unknown"}
    rec = clear(m, policy_=with_mode(policy, mode))
    assert rec["counts"]["ALLOWED"] == rec["counts"]["ALLOWED_WITH_CONDITIONS"] == 0
    for fid, d in by_id(rec).items():
        if before[fid]["decision"] == "ALLOWED":
            assert d["decision"] == "HOLD_FOR_REVIEW", fid
            assert "POL-PO-01" in d["rule_ids"] and "protective order status unknown" in d["reasons"]
        else:
            assert d["decision"] == "NOT_ALLOWED"      # already off for client data; unknown does not rescue it
        assert d["by_data_class"]["protective_order_material"]["decision"] not in CLEARED
    assert rec["counts"]["HOLD_FOR_REVIEW"] == 7


# ------------------------------------------------------- health-data lane

@pytest.mark.parametrize("mode", MODES)
def test_phi_matter_only_lane_features_may_receive_phi(clear, policy, mode):
    rec = clear("M-1001", policy_=with_mode(policy, mode))
    d = by_id(rec)
    ok = {x["feature_id"] for x in rec["decisions"] if x["by_data_class"]["phi"]["decision"] in CLEARED}
    assert ok == PHI_LANE
    assert "no PHI in any tool except Suite B documents, Review D" in rec["banner"]
    assert "PHI use logged" in [c["short"] for c in d["suite-b.doc-summary"]["conditions"]]
    assert "POL-PHI-03" in d["suite-b.email"]["by_data_class"]["phi"]["rule_ids"]          # connector on
    assert "POL-PHI-02" in d["suite-b.meeting-notes"]["by_data_class"]["phi"]["rule_ids"]  # agreement coverage unknown
    email = d["suite-b.email"]
    assert email["by_data_class"]["client_confidential"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    if mode == "block_feature":
        # Off for the whole matter: nobody has to keep PHI out of the email assistant by hand.
        assert email["decision"] == "NOT_ALLOWED" and "connectors or web access on" in email["reasons"]
        assert {x["feature_id"] for x in rec["decisions"] if x["decision"] in CLEARED} == PHI_LANE
    else:
        assert email["decision"] == "ALLOWED_WITH_CONDITIONS"
        assert "no PHI" in [c["short"] for c in email["conditions"]]


def test_phi_lane_feature_can_still_be_blocked_by_a_protective_order(clear, policy):
    rec = clear("M-1013", policy_=with_mode(policy, "block_feature"))
    d = by_id(rec)["suite-b.doc-summary"]
    assert d["by_data_class"]["phi"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert d["by_data_class"]["protective_order_material"]["decision"] == "NOT_ALLOWED"
    assert d["decision"] == "NOT_ALLOWED"
    assert {x["feature_id"] for x in rec["decisions"] if x["decision"] in CLEARED} == {"review-d.review"}
    assert "no PHI in any tool except Review D;" in rec["banner"]


@pytest.mark.parametrize("mode", MODES)
def test_phi_unknown_clears_nothing_and_holds_rather_than_denies(clear, policy, mode):
    rec = clear("M-1002", policy_=with_mode(policy, mode))
    assert rec["counts"] == {"ALLOWED": 0, "ALLOWED_WITH_CONDITIONS": 0, "HOLD_FOR_REVIEW": 3, "NOT_ALLOWED": 7}
    assert rec["flags"]["unknown_inputs"] == ["data_flags.phi"]
    assert "PHI status unknown" in rec["banner"]
    d = by_id(rec)
    # Suite B email is not approved for PHI. Whether PHI is present is unknown, so it is held, not denied.
    for fid in ("suite-b.doc-summary", "suite-b.email", "review-d.review"):
        assert d[fid]["decision"] == "HOLD_FOR_REVIEW" and "POL-PHI-01" in d[fid]["rule_ids"]
        assert d[fid]["by_data_class"]["phi"]["decision"] not in CLEARED
    # Features already off for client data stay off.
    assert d["assistant-a.file-analysis"]["by_data_class"]["client_confidential"]["decision"] == "NOT_ALLOWED"


@pytest.mark.parametrize("field,value", [
    ("baa_covers_feature", "unknown"), ("baa_covers_feature", False),
    ("used_for_training", "unknown"), ("used_for_training", "yes"),
    ("connectors_enabled", "unknown"), ("connectors_enabled", True),
    ("web_access_enabled", "unknown"), ("web_access_enabled", True),
    ("retention_class", "unknown"), ("retention_class", "vendor_default"),
    ("status", "proposed"),
])
def test_phi_lane_is_default_deny(clear, features, field, value):
    feats = copy.deepcopy(features)
    f = next(x for x in feats if x["id"] == "review-d.review")
    f[field] = value
    d = by_id(clear("M-1013", features_=feats))["review-d.review"]
    assert d["by_data_class"]["phi"]["decision"] == "NOT_ALLOWED"


def test_unknown_guard_holds_even_if_the_specific_phi_rules_are_deleted(clear, features, policy):
    p = copy.deepcopy(policy)
    p["rules"] = [r for r in p["rules"] if r["id"] not in ("POL-PHI-02", "POL-PHI-03", "POL-PHI-04")]
    feats = copy.deepcopy(features)
    next(x for x in feats if x["id"] == "review-d.review")["baa_covers_feature"] = "unknown"
    d = by_id(clear("M-1013", features_=feats, policy_=p))["review-d.review"]
    assert d["by_data_class"]["phi"] == {"decision": "HOLD_FOR_REVIEW", "rule_ids": ["POL-GUARD-01"]}
    guard = next(x for x in d["drivers"] if x["rule_id"] == "POL-GUARD-01")
    assert guard["unknown_facts"] == ["feature.baa_covers_feature"]


def test_no_matter_ever_clears_restricted_data_with_an_unknown_guard_fact(clear, store, policy, features):
    """Sweep: every sample matter, every feature, each guard fact set to unknown in turn."""
    checked = 0
    for mid in store.matter_ids():
        for dc, facts in policy["unknown_guard"]["facts"].items():
            for fact in facts:
                m = store.matter(mid)
                feats = copy.deepcopy(features)
                root, _, path = fact.partition(".")
                targets = [m] if root == "matter" else feats
                for t in targets:
                    cur = t
                    parts = path.split(".")
                    for part in parts[:-1]:
                        cur = cur.setdefault(part, {})
                    cur[parts[-1]] = "unknown"
                rec = clear(m, features_=feats)
                for d in rec["decisions"]:
                    if dc in d["by_data_class"]:
                        assert d["by_data_class"][dc]["decision"] not in CLEARED, (mid, fact, d["feature_id"])
                        checked += 1
    assert checked > 500


def test_sealed_material_is_off_everywhere_and_unknown_holds(clear, store):
    m = store.matter("M-1003")
    m["data_flags"]["sealed"] = "yes"
    rec = clear(m)
    assert all(d["by_data_class"]["sealed"]["decision"] == "NOT_ALLOWED" for d in rec["decisions"])
    assert "no sealed material in any tool" in rec["banner"]
    m["data_flags"]["sealed"] = "unknown"
    assert clear(m)["counts"]["ALLOWED"] == 0 and clear(m)["counts"]["ALLOWED_WITH_CONDITIONS"] == 0


# ------------------------------------------------------------------- rollup

def test_shipped_default_is_block_feature_and_both_options_are_documented():
    rollup = load_policy()["rollup"]
    assert rollup["restricted_class_denied"] == "block_feature"
    assert set(rollup["restricted_class_denied_options"]) == set(MODES)
    assert "exclude_class (opt-in)" in rollup["note"] and "by hand" in rollup["note"]


def test_rollup_block_feature_blocks_a_feature_that_is_off_for_a_restricted_class(clear, policy):
    d = by_id(clear("M-1013", policy_=with_mode(policy, "block_feature")))
    assert d["suite-b.email"]["decision"] == "NOT_ALLOWED"
    assert d["suite-b.email"]["conditions"] == [] and d["suite-b.email"]["excluded_data_classes"] == []
    assert d["review-d.review"]["decision"] == "ALLOWED_WITH_CONDITIONS"
    # No "keep it out" condition is ever issued in this mode.
    shorts = {c["short"] for x in d.values() for c in x["conditions"]}
    assert not {"no PHI", "no protective-order material"} & shorts


def test_rollup_exclude_class_keeps_the_feature_with_a_keep_out_condition(clear, policy):
    d = by_id(clear("M-1013", policy_=with_mode(policy, "exclude_class")))
    email = d["suite-b.email"]
    assert email["decision"] == "ALLOWED_WITH_CONDITIONS"
    assert email["excluded_data_classes"] == ["phi", "protective_order_material"]
    assert ["no PHI", "no protective-order material"] == [c["short"] for c in email["conditions"]][-2:]
    assert d["review-d.review"]["decision"] == "ALLOWED_WITH_CONDITIONS"


def test_neither_mode_ever_clears_a_restricted_class_the_other_denies(clear, store, policy):
    """The option changes the feature-level roll-up only. Per-class results are identical."""
    for mid in store.matter_ids():
        a = by_id(clear(mid, policy_=with_mode(policy, "block_feature")))
        b = by_id(clear(mid, policy_=with_mode(policy, "exclude_class")))
        order = policy["decision_precedence"]
        for fid in a:
            assert a[fid]["by_data_class"] == b[fid]["by_data_class"]
            # block_feature is never looser than exclude_class.
            assert order.index(a[fid]["decision"]) <= order.index(b[fid]["decision"]), (mid, fid)


def test_hold_propagates_applies_only_under_exclude_class(clear, policy):
    review = lambda p: by_id(clear("M-1004", policy_=p))["review-d.review"]["decision"]
    assert review(with_mode(policy, "exclude_class", hold_propagates=False)) == "ALLOWED_WITH_CONDITIONS"
    assert review(with_mode(policy, "exclude_class", hold_propagates=True)) == "HOLD_FOR_REVIEW"
    # Under block_feature a class hold always holds the feature, whatever this option says.
    assert review(with_mode(policy, "block_feature", hold_propagates=False)) == "HOLD_FOR_REVIEW"
    assert review(with_mode(policy, "block_feature", hold_propagates=True)) == "HOLD_FOR_REVIEW"


# ------------------------------------------------------------ record shape

def test_rules_past_review_date_are_flagged(clear):
    stale = clear("M-1004")["rules_past_review"]
    assert [s["rule_id"] for s in stale] == ["POL-PO-03", "POL-CT-12"]
    assert {s["rule_id"]: s["used_on_this_matter"] for s in stale} == {"POL-PO-03": True, "POL-CT-12": False}
    assert clear("M-1004", as_of="2026-01-01")["rules_past_review"] == []
    d = by_id(clear("M-1004"))["review-d.review"]
    assert next(x for x in d["drivers"] if x["rule_id"] == "POL-PO-03")["past_review_date"] is True


def test_every_decision_on_every_matter_cites_rules_and_a_valid_label(clear, store, policy):
    known = {r["id"] for r in policy["rules"]}
    for mid in store.matter_ids():
        rec = clear(mid)
        assert rec["banner"].startswith("AI: ") and "\n" not in rec["banner"]
        assert sum(rec["counts"].values()) == 10
        for d in rec["decisions"]:
            assert d["rule_ids"] and set(d["rule_ids"]) <= known
            assert d["decision_label"] in ("ALLOWED", "ALLOWED WITH CONDITIONS", "NOT ALLOWED", "HOLD FOR REVIEW")
            assert bool(d["conditions"]) == (d["decision"] == "ALLOWED_WITH_CONDITIONS")
            if d["decision"] in ("NOT_ALLOWED", "HOLD_FOR_REVIEW"):
                assert d["reasons"]


def test_sample_matters_cover_all_four_decisions(clear, store):
    seen = set()
    for mid in store.matter_ids():
        seen |= {d["decision"] for d in clear(mid)["decisions"]}
    assert seen == {"ALLOWED", "ALLOWED_WITH_CONDITIONS", "HOLD_FOR_REVIEW", "NOT_ALLOWED"}
