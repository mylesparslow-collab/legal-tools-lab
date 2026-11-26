"""Hash-chained ledger: appends, and detection of edits, removals and reordering."""
import json
import os
import shutil

import pytest

from conftest import FIX
from filingkit.ledger import GENESIS, Ledger, LedgerBroken, verify_ledger


def make(tmp_path, n=4):
    led = Ledger(str(tmp_path / "l.jsonl"))
    for i in range(n):
        led.append({"event": "test", "n": i}, now=f"2027-01-12T10:0{i}:00+00:00")
    return led


def lines(led):
    return open(led.path, encoding="utf-8").read().splitlines()


def rewrite(led, ls):
    with open(led.path, "w", encoding="utf-8") as f:
        f.write("\n".join(ls) + "\n")


def test_empty_ledger_is_ok(tmp_path):
    led = Ledger(str(tmp_path / "l.jsonl"))
    assert verify_ledger(led.path) == {"ok": True, "entries": 0, "head": GENESIS, "problems": []}


def test_chain_links_each_entry_to_the_one_before(tmp_path):
    led = make(tmp_path)
    e = led.entries()
    assert [x["seq"] for x in e] == [1, 2, 3, 4]
    assert e[0]["prev_hash"] == GENESIS
    assert all(e[i]["prev_hash"] == e[i - 1]["hash"] for i in range(1, 4))
    res = verify_ledger(led.path)
    assert res["ok"] and res["entries"] == 4 and res["head"] == e[-1]["hash"]


def test_edited_entry_is_detected(tmp_path):
    led = make(tmp_path)
    ls = lines(led)
    e = json.loads(ls[1])
    e["n"] = 99
    ls[1] = json.dumps(e)
    rewrite(led, ls)
    res = verify_ledger(led.path)
    assert not res["ok"]
    assert res["problems"][0]["line"] == 2 and "edited" in res["problems"][0]["problem"]


def test_edit_with_recomputed_hash_still_breaks_the_next_link(tmp_path):
    from filingkit.util import canonical_hash
    led = make(tmp_path)
    ls = lines(led)
    e = json.loads(ls[1])
    e["n"] = 99
    e["hash"] = canonical_hash({k: v for k, v in e.items() if k != "hash"})
    ls[1] = json.dumps(e)
    rewrite(led, ls)
    res = verify_ledger(led.path)
    assert not res["ok"] and any(p["line"] == 3 and "prev_hash" in p["problem"] for p in res["problems"])


def test_removed_entry_is_detected(tmp_path):
    led = make(tmp_path)
    ls = lines(led)
    del ls[1]
    rewrite(led, ls)
    res = verify_ledger(led.path)
    assert not res["ok"] and any("removed" in p["problem"] for p in res["problems"])


def test_reordered_entries_are_detected(tmp_path):
    led = make(tmp_path)
    ls = lines(led)
    ls[1], ls[2] = ls[2], ls[1]
    rewrite(led, ls)
    assert not verify_ledger(led.path)["ok"]


def test_removed_tail_needs_expected_head(tmp_path):
    led = make(tmp_path)
    head = led.head()
    rewrite(led, lines(led)[:-1])
    assert verify_ledger(led.path)["ok"]  # known limit of a bare hash chain
    res = verify_ledger(led.path, expect_head=head)
    assert not res["ok"] and "expected head" in res["problems"][0]["problem"]


def test_garbage_line_is_detected(tmp_path):
    led = make(tmp_path)
    with open(led.path, "a", encoding="utf-8") as f:
        f.write("not json\n")
    res = verify_ledger(led.path)
    assert not res["ok"] and "not valid JSON" in res["problems"][0]["problem"]


def test_missing_file_is_not_ok(tmp_path):
    assert not verify_ledger(str(tmp_path / "nope.jsonl"))["ok"]


def test_append_refuses_on_a_broken_chain(tmp_path):
    led = make(tmp_path)
    ls = lines(led)
    ls[0] = ls[0].replace('"n": 0', '"n": 5')
    rewrite(led, ls)
    with pytest.raises(LedgerBroken):
        led.append({"event": "more"})


def test_append_refuses_reserved_fields(tmp_path):
    led = make(tmp_path, 1)
    with pytest.raises(ValueError):
        led.append({"event": "x", "hash": "abc"})


def test_reads_a_ledger_written_by_the_existing_checker(tmp_path):
    src = os.path.join(FIX, "citecheck_ledger.sample.jsonl")
    res = verify_ledger(src)
    assert res["ok"] and res["entries"] == 19  # 1 machine check, 17 verifications, 1 certificate
    p = str(tmp_path / "copy.jsonl")
    shutil.copy(src, p)
    text = open(p, encoding="utf-8").read().replace("Fictional Counsel", "Another Person", 1)
    open(p, "w", encoding="utf-8").write(text)
    assert not verify_ledger(p)["ok"]
