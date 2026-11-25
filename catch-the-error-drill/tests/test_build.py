"""The build: source in, data.js out, and loud failure when the source is off."""
import hashlib
import json
import re
import shutil

import pytest

from conftest import KIT, ROOT, build_mod

CORPUS = KIT / "eval_harness" / "corpus"


def text_of(doc):
    return "\n".join(b["x"] for b in doc["blocks"])


def norm(s):
    from harness.textnorm import normalise
    return normalise(s)


def keys():
    return {p.name[:-9]: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CORPUS.glob("*.key.json"))}


# ---------- output is in sync with the source ----------

def test_data_js_is_up_to_date(data):
    assert (ROOT / "app" / "data.js").read_text(encoding="utf-8") == build_mod.render(data), \
        "app/data.js is stale; run python3 build.py"


def test_build_is_deterministic(data):
    assert build_mod.render(build_mod.build()) == build_mod.render(data)


def test_counts_account_for_all_90_defects(data):
    c = data["counts"]
    assert c == {"in_keys": 90, "scored": 89, "unscored": 1, "excluded": 0}
    assert sum(len(k["defects"]) for k in keys().values()) == 90
    assert len(data["docs"]) == 12


def test_document_hashes_match_source_files(data):
    for doc in data["docs"]:
        md = (CORPUS / f"{doc['id']}.md").read_bytes()
        kj = (CORPUS / f"{doc['id']}.key.json").read_bytes()
        assert doc["sha256"] == hashlib.sha256(md).hexdigest()
        assert doc["key_sha256"] == hashlib.sha256(kj).hexdigest()
        assert data["source"]["documents"][doc["id"]] == doc["sha256"]


def test_every_span_is_the_key_quote_word_for_word(docs):
    checked = 0
    for doc_id, key in keys().items():
        doc = docs[doc_id]
        text = text_of(doc)
        by_id = {d["id"]: d for d in doc["defects"] + doc["unscored"]}
        for kd in key["defects"]:
            got = sorted(norm(text[s:e]) for s, e in by_id[kd["id"]]["spans"])
            assert got == sorted(norm(q) for q in kd["quotes"])
            checked += len(got)
    assert checked == 96  # 89 anchored defects, 7 of them with two quotes


def test_each_quote_occurs_once_in_display_text(docs):
    for doc in docs.values():
        text = norm(text_of(doc))
        for d in doc["defects"]:
            for s, e in d["spans"]:
                assert text.count(norm(text_of(doc)[s:e])) == 1


def test_spans_stay_inside_one_block_and_do_not_overlap(docs):
    for doc in docs.values():
        spans = sorted((s, e, d["id"]) for d in doc["defects"] for s, e in d["spans"])
        for (s1, e1, _), (s2, _e2, _) in zip(spans, spans[1:]):
            assert e1 <= s2
        for s, e, _ in spans:
            assert "\n" not in text_of(doc)[s:e]


def test_block_offsets_are_contiguous(docs):
    for doc in docs.values():
        pos = 0
        for b in doc["blocks"]:
            assert b["s"] == pos
            pos += len(b["x"]) + 1


def test_display_text_keeps_every_word_of_the_source(docs):
    for doc in docs.values():
        raw = (CORPUS / f"{doc['id']}.md").read_text(encoding="utf-8")
        words = lambda s: re.findall(r"[A-Za-z0-9$%§]+", s)  # noqa: E731
        assert words(text_of(doc)) == words(raw.replace("|", " "))


def test_the_one_unscored_defect_is_the_unanchored_omission(docs):
    uns = [(d["id"], d["kind"], d["spans"]) for doc in docs.values() for d in doc["unscored"]]
    assert uns == [("lease-01-D1", "omission", [])]


# ---------- explanations come from the source, not from this tool ----------

def test_explanations_are_copied_verbatim_from_the_key(docs):
    for doc_id, key in keys().items():
        by_id = {d["id"]: d for d in docs[doc_id]["defects"] + docs[doc_id]["unscored"]}
        for kd in key["defects"]:
            d = by_id[kd["id"]]
            assert (d["why"], d["title"], d["authority"]) == (kd["why"], kd["title"], kd["authority"])


def test_catalog_rules_are_copied_verbatim_from_the_catalog(data):
    catalog = (CORPUS / "DEFECT_CATALOG.md").read_text(encoding="utf-8")
    assert len(data["catalog"]) >= 30
    for code, row in data["catalog"].items():
        assert f"| {code} | {row['rule']} |" in catalog


def test_every_authority_shown_is_in_the_verified_register(data):
    register = json.loads((KIT / "verified_authorities.json").read_text(encoding="utf-8"))["sections"]
    n = 0
    for doc in data["docs"]:
        for d in doc["defects"] + doc["unscored"]:
            assert d["read"], d["id"]
            for r in d["read"]:
                assert register[r["section"]]["read"] == r["date"]
                n += 1
    assert n >= 90


def test_defect_types_are_the_catalogs_kind_and_severity(docs):
    for doc in docs.values():
        for d in doc["defects"] + doc["unscored"]:
            want = "omission" if d["kind"] == "omission" else f"clause_{d['severity']}"
            assert d["type"] == want


def test_no_difficulty_labels_are_invented(data):
    blob = json.dumps({k: v for k, v in data.items() if k != "docs"}) + json.dumps(
        [[{k: v for k, v in d.items() if k not in ("why", "title")} for d in doc["defects"]] for doc in data["docs"]])
    assert not re.search(r"difficult|subtle|easy|hard\b", blob, re.I)


# ---------- excerpts, verify lists, sets ----------

def test_excerpts_fit_the_budget_and_hold_planted_defects(docs):
    for doc in docs.values():
        for name, budget in build_mod.EXCERPT_WORDS.items():
            ex = doc["excerpts"][name]
            assert 0.75 * budget <= ex["words"] <= budget
            assert len(ex["defects"]) >= 2
            rows = [r for r in doc["sections"] if ex["from"] <= r["sec"] <= ex["to"]]
            assert sum(r["words"] for r in rows) == ex["words"]
            by_id = {d["id"]: d for d in doc["defects"]}
            for did in ex["defects"]:
                for s, _e in by_id[did]["spans"]:
                    assert any(r["s"] <= s <= r["e"] for r in rows)


def test_verify_lists_mix_five_planted_and_five_unplanted(docs):
    for doc in docs.values():
        items = doc["verify"]
        assert len(items) == 10 and len({i["id"] for i in items}) == 10
        assert sum(1 for i in items if i["defect"]) == 5
        assert [i["s"] for i in items] == sorted(i["s"] for i in items)  # document order, so order is no clue


def test_unplanted_verify_statements_touch_no_planted_span(docs):
    for doc in docs.values():
        spans = [sp for d in doc["defects"] for sp in d["spans"]]
        for it in doc["verify"]:
            if it["defect"] is None:
                assert not any(s < it["e"] and it["s"] < e for s, e in spans)
                assert re.search(r"\d", text_of(doc)[it["s"]:it["e"]])


def test_planted_verify_statements_contain_the_defect_quote(docs):
    for doc in docs.values():
        by_id = {d["id"]: d for d in doc["defects"]}
        for it in doc["verify"]:
            if it["defect"]:
                s, e = by_id[it["defect"]]["spans"][0]
                assert it["s"] <= s and e <= it["e"]
                assert by_id[it["defect"]]["kind"] == "clause"


def test_sets_cover_each_area_length_and_rotation(data, docs):
    sets = data["sets"]
    assert len(sets) == 45 and len({s["id"] for s in sets}) == 45
    areas = {d["area"] for d in docs.values()}
    assert {s["area"] for s in sets} == areas | {"Mixed"}
    for s in sets:
        used = [e["doc"] for e in s["exercises"]]
        assert len(set(used)) == len(used), "a document never appears twice in one session"
        assert [e["mode"] for e in s["exercises"]] == ["spot", "verify", "review"][: len(used)]
        assert len(used) == (2 if s["length"] == 10 else 3)
        assert sum(e["minutes"] for e in s["exercises"]) <= s["length"] - 2
        if s["area"] != "Mixed":
            assert {docs[d]["area"] for d in used} == {s["area"]}
        else:
            assert len({docs[d]["area"] for d in used}) == len(used)


def test_rotations_use_each_document_in_each_role(data):
    for area in {s["area"] for s in data["sets"]} - {"Mixed"}:
        spot = {s["exercises"][0]["doc"] for s in data["sets"] if s["area"] == area and s["length"] == 30}
        review = {s["exercises"][2]["doc"] for s in data["sets"] if s["area"] == area and s["length"] == 30}
        assert len(spot) == 3 and spot == review


# ---------- markdown handling ----------

def test_parse_markdown_strips_bold_and_keeps_offsets():
    raw = "# Title\n\n_Fictional note._\n\n**1.1 Rent.** Tenant pays.\nBy: ______\n\n| A | B |\n| --- | --- |\n| 1 | **2** |\n\n---\n"
    blocks, rawmaps = build_mod.parse_markdown(raw, "t")
    assert [(b["t"], b["x"]) for b in blocks] == [
        ("h1", "Title"), ("p", "Fictional note."), ("p", "1.1 Rent. Tenant pays."), ("p", "By: ______"),
        ("th", "A"), ("th", "B"), ("td", "1"), ("td", "2"), ("hr", "")]
    assert blocks[1]["i"] == 1 and blocks[2]["b"] == [[0, 9]] and blocks[3]["c"] == 1
    for b, rm in zip(blocks, rawmaps):
        assert "".join(raw[i] for i in rm) == b["x"]


@pytest.mark.parametrize("raw", ["Fictional. **Unclosed bold", "Fictional. `code`", "> quoted", "Has *single* stars"])
def test_parse_markdown_refuses_markup_it_does_not_understand(raw):
    with pytest.raises(build_mod.BuildError):
        build_mod.parse_markdown(raw, "t")


# ---------- the build fails loudly on a bad source ----------

@pytest.fixture()
def kit_copy(tmp_path):
    kit = tmp_path / "kit"
    (kit / "eval_harness").mkdir(parents=True)
    shutil.copytree(KIT / "eval_harness" / "corpus", kit / "eval_harness" / "corpus")
    shutil.copytree(KIT / "eval_harness" / "harness", kit / "eval_harness" / "harness")
    shutil.copy(KIT / "authorities.py", kit / "authorities.py")
    shutil.copy(KIT / "verified_authorities.json", kit / "verified_authorities.json")
    return kit


def edit_key(kit, doc_id, fn):
    p = kit / "eval_harness" / "corpus" / f"{doc_id}.key.json"
    key = json.loads(p.read_text(encoding="utf-8"))
    fn(key)
    p.write_text(json.dumps(key), encoding="utf-8")


def test_copy_of_the_kit_builds_the_same_data(kit_copy, data):
    assert build_mod.build(kit_copy)["build"] == data["build"]


def test_build_fails_when_a_quote_is_not_in_the_document(kit_copy):
    edit_key(kit_copy, "emp-01", lambda k: k["defects"][0]["quotes"].__setitem__(0, k["defects"][0]["quotes"][0].replace(" ", "  x ", 1)))
    with pytest.raises(build_mod.BuildError, match="found 0 times"):
        build_mod.build(kit_copy)


def test_build_fails_when_a_quote_differs_by_one_character(kit_copy):
    def change(k):
        q = k["defects"][1]["quotes"][0]
        k["defects"][1]["quotes"][0] = q[:-1] + ("x" if q[-1] != "x" else "y")
    edit_key(kit_copy, "pw-01", change)
    with pytest.raises(build_mod.BuildError, match="found 0 times"):
        build_mod.build(kit_copy)


def test_build_fails_when_a_quote_occurs_twice(kit_copy):
    md = kit_copy / "eval_harness" / "corpus" / "lease-02.md"
    key = json.loads((kit_copy / "eval_harness" / "corpus" / "lease-02.key.json").read_text(encoding="utf-8"))
    quote = key["defects"][0]["quotes"][0]
    md.write_text(md.read_text(encoding="utf-8") + "\n\n" + quote + "\n", encoding="utf-8")
    with pytest.raises(build_mod.BuildError, match="found 2 times"):
        build_mod.build(kit_copy)


def test_build_fails_on_an_ellipsis_quote_rather_than_guessing(kit_copy):
    def change(k):
        q = k["defects"][0]["quotes"][0]
        k["defects"][0]["quotes"][0] = q[:30] + " [...] " + q[-30:]
    edit_key(kit_copy, "apa-01", change)
    with pytest.raises(build_mod.BuildError, match="ellipsis"):
        build_mod.build(kit_copy)


def test_build_fails_on_an_unknown_catalog_code(kit_copy):
    edit_key(kit_copy, "apa-02", lambda k: k["defects"][0].__setitem__("catalog_code", "Z9"))
    with pytest.raises(build_mod.BuildError, match="Z9"):
        build_mod.build(kit_copy)


def test_defect_with_unverified_authority_is_left_out_and_listed(kit_copy):
    edit_key(kit_copy, "emp-02", lambda k: k["defects"][0].__setitem__("authority", "Lab. Code § 99999"))
    out = build_mod.build(kit_copy)
    assert out["counts"]["excluded"] == 1 and out["counts"]["scored"] == 88
    assert out["excluded"][0]["id"] == "emp-02-D1" and "99999" in out["excluded"][0]["reason"]
    assert all(d["id"] != "emp-02-D1" for doc in out["docs"] for d in doc["defects"])


def test_cli_exits_nonzero_and_says_build_failed(kit_copy, monkeypatch, capsys):
    edit_key(kit_copy, "apa-02", lambda k: k["defects"][0].__setitem__("catalog_code", "Z9"))
    monkeypatch.setattr(build_mod, "DEFAULT_KIT", kit_copy)
    monkeypatch.setattr(build_mod.build, "__defaults__", (kit_copy,))
    assert build_mod.main([]) == 1
    assert "BUILD FAILED" in capsys.readouterr().err
