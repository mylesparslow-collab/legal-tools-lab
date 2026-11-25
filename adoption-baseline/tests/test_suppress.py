from baseline import pipeline
from baseline.suppress import cell, suppress_cells, suppress_counts
from helpers import make_analysis, person, use


def sizes(cells):
    return [c["people"] for c in cells]


def marks(cells):
    return [c["suppressed"] for c in cells]


def test_cells_under_the_threshold_are_withheld_with_all_their_numbers():
    out = suppress_cells([cell(2, 4), cell(10, 20), cell(1, 3)], 5)
    assert marks(out) == ["small_group", None, "small_group"]
    assert out[0] == {"n": None, "d": None, "people": None, "rate": None, "suppressed": "small_group"}


def test_one_small_cell_takes_the_next_smallest_with_it():
    out = suppress_cells([cell(10, 30), cell(2, 4), cell(5, 12), cell(8, 20)], 5)
    assert marks(out) == [None, "small_group", "complementary", None]


def test_complementary_suppression_continues_until_hidden_cells_cover_enough_people():
    out = suppress_cells([cell(1, 2), cell(1, 2), cell(5, 9), cell(9, 30)], 5)      # 2 + 2 = 4, still too few
    assert marks(out) == ["small_group", "small_group", "complementary", None]


def test_nothing_is_withheld_when_every_group_is_big_enough():
    assert marks(suppress_cells([cell(3, 5), cell(0, 6)], 5)) == [None, None]


def test_empty_groups_are_left_alone_and_do_not_hide_anyone():
    out = suppress_cells([cell(0, 0), cell(1, 3), cell(4, 8), cell(5, 9)], 5)
    assert marks(out) == [None, "small_group", "complementary", None]


def test_threshold_is_configurable():
    cells = [cell(1, 3), cell(4, 8), cell(5, 9)]
    assert marks(suppress_cells(cells, 3)) == [None, None, None]
    assert marks(suppress_cells(cells, 9)) == ["small_group", "small_group", None]


def test_multi_select_tallies_hide_small_counts_without_complementary():
    assert suppress_counts({"a": 3, "b": 40, "c": 0}, 5, partition=False) == {"a": None, "b": 40, "c": 0}
    assert suppress_counts({"a": 3, "b": 40, "c": 9}, 5, partition=True) == {"a": None, "b": 40, "c": None}


def test_breakdown_applies_suppression_and_keeps_the_total(tmp_path):
    rows = ([person("A%d" % i, practice="Big") for i in range(8)] + [person("B%d" % i, practice="Mid") for i in range(6)]
            + [person("C%d" % i, practice="Tiny") for i in range(2)])
    a = make_analysis(tmp_path, rows, [use("C0", "2026-09-29")])
    tb = a.breakdown("practice", "lawyers")
    got = {r["group"]: r["cells"]["weekly_active_latest"]["suppressed"] for r in tb["rows"]}
    assert got == {"Big": None, "Mid": "complementary", "Tiny": "small_group"}
    assert tb["total"]["cells"]["weekly_active_latest"]["d"] == 16


def walk(node, path=""):
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from walk(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, path + "/" + str(i))


def test_no_published_cell_in_the_sample_baseline_describes_fewer_than_five_people(baseline):
    thr = baseline["meta"]["suppression_threshold"]
    checked = 0
    for path, node in walk(baseline):
        if path.startswith("/data_quality") or not {"n", "d", "people", "suppressed"} <= set(node):
            continue
        checked += 1
        if node["suppressed"]:
            assert node["n"] is None and node["d"] is None and node["rate"] is None, path
        else:
            assert node["people"] == 0 or node["people"] >= thr, path
    assert checked > 100


def test_survey_tallies_never_publish_a_count_between_one_and_four(baseline):
    for q in baseline["survey"]["tallies"].values():
        assert all(v is None or v == 0 or v >= 5 for v in q["counts"].values())


def test_lowering_the_threshold_to_one_shows_every_group(config, root):
    cfg = dict(config, suppression_threshold=1)
    b = pipeline.build_baseline(cfg, root)
    assert all(not r["cells"]["weekly_active_last_4_weeks"]["suppressed"] for r in b["breakdowns"]["practice"]["rows"])
