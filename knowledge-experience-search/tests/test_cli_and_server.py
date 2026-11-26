import json
import re
import pytest

from kx import config as cfg
from kx.__main__ import main
from kx.server import page_html


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory, data_dir):
    folder = tmp_path_factory.mktemp("cli")
    db, log = folder / "index.sqlite", folder / "audit.jsonl"
    assert main(["index", "--data", str(data_dir), "--db", str(db), "--log", str(log)]) == 0
    return db, log


def run(capsys, *argv):
    code = main(list(argv))
    return code, capsys.readouterr().out


def test_cli_index_reports_counts_and_is_incremental(cli_db, data_dir, capsys):
    db, log = cli_db
    code, out = run(capsys, "index", "--data", str(data_dir), "--db", str(db), "--log", str(log))
    report = json.loads(out)
    assert code == 0 and report["mode"] == "incremental"
    assert report["documents_added"] == 0 and report["index"]["documents"] == 1500
    assert report["permission_warnings"] == [] and report["documents_rejected"] == []


def test_cli_search_shows_results_explain_and_facets(cli_db, key, capsys):
    db, log = cli_db
    code, out = run(capsys, "search", "--db", str(db), "--log", str(log), "--user", key["eval_user"],
                    "--as-of", key["as_of"], "--explain", "earn-out", "provisions", "agreement")
    assert code == 0 and " 1. " in out and "why: text" in out
    assert "visible documents" in out and "Filters available in these results" in out


def test_cli_search_json_differs_by_user(cli_db, manifest, key, capsys):
    db, log = cli_db
    wall = manifest["walls"]["W1"]
    query = f"project {wall['codenames'][0].lower()}"
    common = ["search", "--db", str(db), "--log", str(log), "--as-of", key["as_of"], "--json",
              "--limit", "50"]
    _, as_denied = run(capsys, *common, "--user", wall["excluded"][0], query)
    _, as_other = run(capsys, *common, "--user", key["eval_user"], query)
    denied, other = json.loads(as_denied), json.loads(as_other)
    walled_ids = {d for t in key["wall_tests"] if t["wall_id"] == "W1" for d in t["must_never_appear"]}
    assert {r["doc_id"] for r in other["results"]} & walled_ids
    assert not ({r["doc_id"] for r in denied["results"]} & walled_ids)
    # The denied user's output is what any word found nowhere would produce.
    _, as_nonsense = run(capsys, *common, "--user", wall["excluded"][0], "project qqxyzzy")
    assert as_denied.replace(wall["codenames"][0].lower(), "WORD") == as_nonsense.replace("qqxyzzy", "WORD")


def test_cli_who_and_suggest(cli_db, key, capsys):
    db, log = cli_db
    code, out = run(capsys, "who", "--db", str(db), "--log", str(log), "--user", key["eval_user"],
                    "--as-of", key["as_of"], "asset", "purchase")
    assert code == 0 and "matching matter(s) this user can open" in out and " 1. " in out
    code, out = run(capsys, "suggest", "--db", str(db), "--log", str(log), "--user",
                    key["eval_user"], "indemn")
    assert "indemnification" in out.split()


def test_cli_audit_verify_and_report(cli_db, key, capsys):
    db, log = cli_db
    run(capsys, "search", "--db", str(db), "--log", str(log), "--user", key["eval_user"], "qqxyzzy")
    code, out = run(capsys, "audit", "verify", "--log", str(log))
    assert code == 0 and json.loads(out)["ok"] is True
    code, out = run(capsys, "audit", "report", "--log", str(log))
    assert "qqxyzzy" in out
    lines = log.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace(key["eval_user"], "U999")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, out = run(capsys, "audit", "verify", "--log", str(log))
    assert code == 1 and json.loads(out)["ok"] is False


def test_cli_bad_filter_exits_with_a_message(cli_db, key):
    db, log = cli_db
    with pytest.raises(SystemExit) as exc:
        main(["search", "--db", str(db), "--log", str(log), "--user", key["eval_user"],
              "--filter", "filed=perhaps", "memo"])
    assert "Could not run that query" in str(exc.value)


def test_page_is_self_contained():
    html = page_html()
    assert not re.search(r"""(src|href)\s*=\s*["'](https?:)?//""", html)
    assert "@import" not in html and "<link" not in html
    assert "prefers-color-scheme: dark" in html and 'name="viewport"' in html
    assert "/*__SNAPSHOT__*/" not in html


def test_snapshot_page_embeds_data_safely():
    snap = {"meta": {"demo_users": [], "people": [], "presets": {}},
            "search": {"u|q": {"message": "</script><script>alert(1)</script>"}}, "who": {}}
    html = page_html(snap)
    assert "window.KX_SNAPSHOT = " in html
    assert html.count("</script>") == 1   # the embedded text cannot close the script element
