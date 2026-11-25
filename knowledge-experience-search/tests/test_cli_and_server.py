import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from kx import config as cfg
from kx.__main__ import main
from kx.server import PRESETS, make_handler, page_html
from kx.service import Service


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
    assert wall["codenames"][0].lower() not in json.dumps(
        {k: v for k, v in denied.items() if k != "query"}).lower()


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


@pytest.fixture(scope="module")
def server(full_db_path, data_dir, tmp_path_factory, key):
    log = tmp_path_factory.mktemp("srv") / "audit.jsonl"
    service = Service(full_db_path, log, as_of=key["as_of"])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service, data_dir))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", httpd, log
    httpd.shutdown()
    httpd.server_close()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as res:
        body = res.read().decode("utf-8")
        return res.status, res.headers, body


def test_server_binds_to_loopback_only(server):
    _, httpd, _ = server
    assert httpd.server_address[0] == "127.0.0.1"


def test_server_serves_the_page_and_meta(server, manifest):
    base, _, _ = server
    status, headers, body = get(base, "/")
    assert status == 200 and "Knowledge and experience search" in body
    assert headers["Cache-Control"] == "no-store"
    status, _, body = get(base, "/api/meta")
    meta = json.loads(body)
    assert [u["person_id"] for u in meta["demo_users"]] == [u["person_id"] for u in manifest["demo_users"]]
    assert len(meta["people"]) == 120 and meta["presets"] == PRESETS


def test_server_search_changes_with_the_user_and_is_audited(server, manifest, key):
    base, _, log = server
    wall = manifest["walls"]["W1"]
    q = "project%20" + wall["codenames"][0].lower()
    _, _, denied = get(base, f"/api/search?user={wall['excluded'][0]}&q={q}&explain=1&limit=50")
    _, _, other = get(base, f"/api/search?user={key['eval_user']}&q={q}&explain=1&limit=50")
    denied, other = json.loads(denied), json.loads(other)
    walled_ids = {d for t in key["wall_tests"] if t["wall_id"] == "W1" for d in t["must_never_appear"]}
    assert {r["doc_id"] for r in other["results"]} & walled_ids
    assert not ({r["doc_id"] for r in denied["results"]} & walled_ids)
    assert "explain" in other["results"][0]
    from kx import audit
    users = [e["user"] for e in audit.read_entries(log)]
    assert wall["excluded"][0] in users and key["eval_user"] in users
    assert audit.verify(log)["ok"] is True


def test_server_filters_who_and_suggest(server, key):
    base, _, _ = server
    user = key["eval_user"]
    _, _, body = get(base, f"/api/search?user={user}&q=summary%20judgment&type=motion&filed=yes")
    result = json.loads(body)
    assert result["filters"] == {"doc_type": "motion", "was_filed": 1}
    assert result["results"] and all(r["doc_type"] == "motion" and r["was_filed"] for r in result["results"])
    _, _, body = get(base, f"/api/who?user={user}&q=asset%20purchase")
    assert json.loads(body)["people"]
    _, _, body = get(base, f"/api/suggest?user={user}&q=indemn")
    assert "indemnification" in json.loads(body)["suggestions"]


def test_server_without_a_user_returns_nothing(server):
    base, _, _ = server
    _, _, body = get(base, "/api/search?q=agreement")
    result = json.loads(body)
    assert result["access"] == "denied" and result["results"] == []


def test_server_errors_are_plain_json(server, key):
    base, _, _ = server
    with pytest.raises(urllib.error.HTTPError) as bad:
        get(base, f"/api/search?user={key['eval_user']}&q=memo&filed=perhaps")
    assert bad.value.code == 400 and "yes or no" in json.loads(bad.value.read())["error"]
    with pytest.raises(urllib.error.HTTPError) as missing:
        get(base, "/api/nothing")
    assert missing.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as post:
        urllib.request.urlopen(urllib.request.Request(base + "/api/search", data=b"x"), timeout=10)
    assert post.value.code == 501


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
