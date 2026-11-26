"""HTTP-level tests: the real server on an ephemeral port.

The main check repeats the noninterference test through the web route. For a
user excluded by a wall, every response (status, headers, length, body) from
the server over the full index must be byte-identical to the response from a
server over an index that never held anything that user cannot see.

Byte-identity alone would miss a leak that both servers share (for example a
confidential name in static page data), so every response is also scanned for
the walled matters' code names.
"""
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import quote, urlencode

import pytest

from kx import acl, audit, index
from kx.server import COOKIE, PRESETS, make_handler
from kx.service import Service
from kx.session import SessionStore
from sources.memory import MemoryAdapter

VOLATILE = {"date", "set-cookie"}
DATA_PATHS = ("/api/search", "/api/who", "/api/suggest", "/api/document")


class Client:
    """A minimal browser: keeps the session cookie, returns raw responses."""

    def __init__(self, port):
        self.port, self.cookie = port, None

    def request(self, method, path, body=None, headers=None, cookie="session"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        send = {"Host": f"127.0.0.1:{self.port}"}
        if cookie == "session" and self.cookie:
            send["Cookie"] = f"{COOKIE}={self.cookie}"
        elif cookie not in ("session", None):
            send["Cookie"] = cookie
        send.update(headers or {})
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
            send.setdefault("Content-Type", "application/json")
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        if body is not None:
            send["Content-Length"] = str(len(body))
        for name, value in send.items():
            conn.putheader(name, value)
        conn.endheaders(body)
        res = conn.getresponse()
        data = res.read()
        out = {"status": res.status, "headers": [(k.lower(), v) for k, v in res.getheaders()],
               "body": data}
        conn.close()
        return out

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def sign_in(self, person_id):
        res = self.request("POST", "/api/signin", {"person_id": person_id})
        assert res["status"] == 200, res
        self.cookie = dict(res["headers"])["set-cookie"].split(";")[0].split("=", 1)[1]
        return res


def comparable(res):
    """Everything about a response except the clock and the random session token."""
    return (res["status"], [(k, v) for k, v in res["headers"] if k not in VOLATILE], res["body"])


def start(db_path, data_dir, log, as_of, sessions=None):
    service = Service(db_path, log, as_of=as_of)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service, data_dir, sessions))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


@pytest.fixture(scope="module")
def servers(full, full_db_path, canonical, data_dir, tmp_path_factory, key):
    """Factory: (client on the full index, client on an index that never held
    what the user cannot see, hidden document ids), both signed in as the user."""
    folder = tmp_path_factory.mktemp("http")
    running, cache = [], {}
    full_httpd = start(full_db_path, data_dir, folder / "full.jsonl", key["as_of"])
    running.append(full_httpd)

    def build(user_id):
        if user_id in cache:
            return cache[user_id]
        visible = acl.visible_matter_ids(full, user_id)
        perms = canonical["permissions"]
        adapter = MemoryAdapter(
            people=canonical["people"],
            matters=[m for m in canonical["matters"] if m.matter_id in visible],
            group_members=perms.group_members,
            grants=[g for g in perms.grants if g.matter_id in visible], walls=[],
            team=[t for t in canonical["team"] if t.matter_id in visible],
            time_entries=[t for t in canonical["time"] if t.matter_id in visible],
            documents=[d for d in canonical["documents"] if d.matter_id in visible])
        adapter.walls = [type(w)(w.wall_id, tuple(m for m in w.matter_ids if m in visible),
                                 w.excluded_person_ids)
                         for w in perms.walls if any(m in visible for m in w.matter_ids)]
        path = folder / f"clean_{user_id}.sqlite"
        conn = index.connect(path)
        index.Indexer(conn).sync(adapter, full=True)
        conn.close()
        httpd = start(path, data_dir, folder / f"clean_{user_id}.jsonl", key["as_of"])
        running.append(httpd)
        a, b = Client(full_httpd.server_address[1]), Client(httpd.server_address[1])
        a.sign_in(user_id)
        b.sign_in(user_id)
        hidden = sorted(d.doc_id for d in canonical["documents"] if d.matter_id not in visible)
        cache[user_id] = (a, b, hidden)
        return cache[user_id]

    build.full_port = full_httpd.server_address[1]
    build.full_log = folder / "full.jsonl"
    yield build
    for httpd in running:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="module")
def anon(servers):
    return Client(servers.full_port)


def wall_cases(key, manifest):
    """(excluded user, wall tests for that wall, code names) for each wall."""
    out = []
    for wall_id, wall in sorted(manifest["walls"].items()):
        tests = [t for t in key["wall_tests"] if t["wall_id"] == wall_id]
        out.append((wall["excluded"][0], tests, [c.lower() for c in wall["codenames"]]))
    return out


def probe_paths(full, key, tests, codenames, hidden):
    """Every kind of request the page makes, aimed at the walled material."""
    q = lambda **p: urlencode(p)
    paths = ["/", "/index.html", "/api/meta"]
    words = set(codenames) | {t["canary_term"] for t in tests}
    queries = [x for t in tests for x in t["queries"]]
    queries += [f"project {w}" for w in sorted(words)]
    queries += [w[:-2] + w[-1] for w in sorted(words)]            # a near-miss spelling
    queries += [item["query"] for item in key["queries"][::3]]    # ordinary work queries
    queries += ["agreement", "memo", "indemnifcation basket", "handing premises over to a new occupier"]
    for text in queries:
        paths.append("/api/search?" + q(q=text))
        paths.append("/api/search?" + q(q=text, explain=1, limit=50))
        paths.append("/api/search?" + q(q=text, expand="off", explain=1, limit=50))
        paths.append("/api/search?" + q(q=text, offset=5, limit=5))
    matter_rows = {r[0]: r for r in full.execute(
        "SELECT matter_id, matter_type, practice, jurisdiction, client_industry, name FROM matters")}
    for t in tests:
        _, mtype, practice, court, industry, name = matter_rows[t["matter_id"]]
        for flt in ({"mtype": mtype}, {"practice": practice}, {"jurisdiction": court},
                    {"industry": industry}, {"mtype": mtype, "after": "2020-01-01"}):
            paths.append("/api/search?" + q(q="", limit=50, **flt))      # facets and counts
            paths.append("/api/search?" + q(q="agreement", **flt))
            paths.append("/api/who?" + q(q="", **flt))
        for text in (mtype, name, practice, t["canary_term"], f"{mtype} {t['canary_term']}"):
            paths.append("/api/who?" + q(q=text))
            paths.append("/api/who?" + q(q=text, limit=50, expand="off"))
        word = t["canary_term"]
        for n in range(2, len(word) + 1):
            paths.append("/api/suggest?" + q(q=word[:n]))
        paths.append("/api/suggest?" + q(q=mtype[:4]))
    for doc_id in hidden:
        paths.append("/api/document?" + q(id=doc_id))
    walled = tests[0]["must_never_appear"][0]
    visible = full.execute("SELECT doc_id FROM docs ORDER BY doc_id").fetchall()
    paths += ["/api/document?" + q(id=r[0]) for r in visible[::97]]
    # Tricks: other spellings of the id, other routes to it, parameters that
    # might name a user, matter or document directly, and malformed requests.
    paths += [f"/api/document?id={walled.lower()}", f"/api/document?id=%20{walled}",
              f"/api/document?id={walled}%00", f"/api/document?id=D00001&id={walled}",
              f"/api/document?id={walled}&id=D00001", f"/api/document?doc_id={walled}",
              f"/api/document/{walled}", f"/api/documents/{walled}", f"/api/document?id[]={walled}",
              f"/api/document?id={quote(walled + chr(39) + ' OR 1=1 --')}", "/api/document",
              f"/api/doc?id={walled}", f"/api/snippet?id={walled}", f"/api/explain?id={walled}",
              f"/api/matter?id={tests[0]['matter_id']}", f"/api/matters/{tests[0]['matter_id']}",
              f"/api/search?q=agreement&matter={tests[0]['matter_id']}",
              f"/api/search?q=agreement&matter_id={tests[0]['matter_id']}",
              f"/api/search?q={walled}", f"/api/search?q=doc_id:{walled}",
              f"/api/search?q=matter:{tests[0]['matter_id']}",
              f"/api/who?q={tests[0]['matter_id']}", f"/api/suggest?q={walled[:4]}",
              f"/api//document?id={walled}", f"/api/./document?id={walled}",
              f"/api/search/../document?id={walled}", "/../data/synthetic/documents.jsonl",
              "/..%2f..%2fdata%2fsynthetic%2fdocuments.jsonl", "/data/synthetic/ANSWER_KEY.json",
              "/var/index.sqlite", "/api/audit", "/api/users", "/api/people", "/api/nothing",
              "/api/search?q=memo&limit=abc", "/api/search?q=memo&limit=-1",
              "/api/search?q=memo&offset=999999", "/api/search?q=memo&filed=perhaps",
              "/api/who?q=merger&type=memo", "/api/search", "/api/who", "/api/suggest",
              "/api/search?q=" + "a" * 3000, "/api/search?q=%ff%fe"]
    return paths


def test_excluded_user_gets_byte_identical_responses_on_every_endpoint(servers, full, key, manifest):
    compared = 0
    for user, tests, codenames in wall_cases(key, manifest):
        a, b, hidden = servers(user)
        assert hidden
        for path in probe_paths(full, key, tests, codenames, hidden):
            ra, rb = a.get(path), b.get(path)
            assert comparable(ra) == comparable(rb), (user, path)
            sizes = dict(ra["headers"])["content-length"], dict(rb["headers"])["content-length"]
            assert sizes[0] == sizes[1] == str(len(ra["body"]))
            compared += 1
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            for path in ("/api/search?q=memo", f"/api/document?id={hidden[0]}", "/"):
                assert comparable(a.request(method, path)) == comparable(b.request(method, path))
    assert compared > 800


def test_no_response_names_a_walled_matter_unless_the_user_typed_it(servers, full, key, manifest):
    for user, tests, codenames in wall_cases(key, manifest):
        a, _, hidden = servers(user)
        secrets = set(codenames) | {t["canary_term"].lower() for t in tests}
        for path in probe_paths(full, key, tests, codenames, hidden):
            body = a.get(path)["body"].decode("utf-8", "replace").lower()
            for word in secrets:
                typed = word in path.lower() or word[:-2] + word[-1] in path.lower()
                assert typed or word not in body, (user, path, word)


def test_page_and_directory_do_not_name_confidential_matters(anon, manifest, key):
    """Static page data is the same for everyone, so it must be clean for everyone."""
    words = {c.lower() for w in manifest["walls"].values() for c in w["codenames"]}
    words |= {t["canary_term"].lower() for t in key["wall_tests"] + key["restricted_tests"]}
    for path in ("/", "/api/meta"):
        body = anon.get(path, cookie=None)["body"].decode("utf-8").lower()
        assert not [w for w in words if w in body], path
    assert not [w for w in words if w in json.dumps(PRESETS).lower()]


def test_hidden_document_by_id_is_indistinguishable_from_a_document_that_does_not_exist(
        servers, key, manifest):
    for user, tests, _ in wall_cases(key, manifest):
        a, _, hidden = servers(user)
        missing = comparable(a.get("/api/document?id=D99999"))
        assert missing[0] == 404
        for doc_id in hidden:
            assert comparable(a.get("/api/document?id=" + doc_id)) == missing, (user, doc_id)
        # The control user for the same wall can open it.
        control = Client(servers.full_port)
        control.sign_in(tests[0]["control_user"])
        opened = control.get("/api/document?id=" + tests[0]["must_never_appear"][0])
        assert opened["status"] == 200 and json.loads(opened["body"])["body"]


def test_every_document_response_passes_the_visibility_filter(servers, full, key, manifest):
    """Ask for every document in the index by id; only visible ones come back."""
    user, _, _ = wall_cases(key, manifest)[0]
    a, _, hidden = servers(user)
    visible = acl.visible_matter_ids(full, user)
    for doc_id, matter_id in full.execute("SELECT doc_id, matter_id FROM docs ORDER BY doc_id"):
        res = a.get("/api/document?id=" + doc_id)
        assert (res["status"] == 200) == (matter_id in visible), doc_id
        if res["status"] == 200:
            assert json.loads(res["body"])["matter_id"] == matter_id
    assert set(hidden) == {r[0] for r in full.execute("SELECT doc_id, matter_id FROM docs")
                           if r[1] not in visible}


def test_there_is_no_route_that_returns_a_matter_or_a_document_outside_the_filter(servers, key):
    client = Client(servers.full_port)
    client.sign_in(key["eval_user"])
    allowed = {"/", "/index.html", "/api/meta", "/api/search", "/api/who", "/api/suggest",
               "/api/document"}
    guesses = ["/api/matter", "/api/matters", "/api/matter/M0001", "/api/documents", "/api/docs",
               "/api/doc", "/api/document/D00001", "/api/snippet", "/api/explain", "/api/facets",
               "/api/people", "/api/users", "/api/user", "/api/audit", "/api/index", "/api/acl",
               "/api/walls", "/api/admin", "/api", "/api/", "/static/app.html", "/app.html",
               "/kx/web/app.html", "/favicon.ico", "/data", "/output/demo.html"]
    for path in guesses:
        assert path not in allowed
        res = client.get(path + "?id=D00001&q=memo")
        assert res["status"] == 404 and json.loads(res["body"]) == {"error": "Not found"}, path


def test_data_endpoints_need_a_session(anon, key):
    expected = None
    for path in DATA_PATHS:
        for query in ("", "?q=memo", "?id=D00001", f"?q=memo&user={key['eval_user']}",
                      f"?user={key['eval_user']}&q=agreement&person_id={key['eval_user']}"):
            for cookie in (None, f"{COOKIE}=not-a-real-token", f"{COOKIE}={key['eval_user']}",
                           f"{COOKIE}=", "other=1", f"{COOKIE}=" + "x" * 5000):
                res = anon.get(path + query, cookie=cookie)
                assert res["status"] == 401, (path, query, cookie)
                expected = expected or comparable(res)
                assert comparable(res) == expected   # one answer, whatever was asked
    assert json.loads(expected[2]) == {"error": "Sign in first."}


def test_user_parameter_is_ignored_once_signed_in(servers, key, manifest):
    user, tests, _ = wall_cases(key, manifest)[0]
    a, _, _ = servers(user)
    control = tests[0]["control_user"]
    for path in ("/api/search?q=project+" + tests[0]["canary_term"],
                 "/api/search?q=earn-out+provisions&limit=50", "/api/who?q=stock+purchase",
                 "/api/suggest?q=" + tests[0]["canary_term"][:4],
                 "/api/document?id=" + tests[0]["must_never_appear"][0]):
        plain = comparable(a.get(path))
        for extra in (f"&user={control}", f"&user_id={control}", f"&person_id={control}",
                      f"&as={control}", f"&user={control}&user={control}"):
            assert comparable(a.get(path + extra)) == plain, (path, extra)
        spoofed = a.get(path, headers={"X-User": control, "X-Forwarded-User": control,
                                       "Authorization": "Bearer " + control})
        assert comparable(spoofed) == plain


def test_sign_in_rejects_unknown_people_and_malformed_requests(anon):
    bad = [({"person_id": "U999"}, {}), ({"person_id": ""}, {}), ({"person_id": None}, {}),
           ({"person_id": ["U001"]}, {}), ({"person_id": {"$ne": ""}}, {}), ({}, {}),
           ([], {}), (b"not json", {"Content-Type": "application/json"}),
           (b"person_id=U001", {"Content-Type": "application/x-www-form-urlencoded"}),
           (b'{"person_id": "U001"}', {"Content-Type": "text/plain"}),
           ({"person_id": "U001' OR '1'='1"}, {})]
    for body, headers in bad:
        res = anon.request("POST", "/api/signin", body, headers=headers, cookie=None)
        assert res["status"] == 400 and "set-cookie" not in dict(res["headers"]), body
    big = anon.request("POST", "/api/signin", b"{" + b" " * 5000 + b"}",
                       headers={"Content-Type": "application/json"}, cookie=None)
    assert big["status"] == 400
    assert anon.request("POST", "/api/search?q=memo", {"person_id": "U001"})["status"] == 404
    assert anon.request("GET", "/api/signin?person_id=U001")["status"] == 404


def test_session_cookie_is_opaque_http_only_and_ends_at_sign_out(servers, key):
    client = Client(servers.full_port)
    res = client.sign_in(key["eval_user"])
    cookie = dict(res["headers"])["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie
    assert key["eval_user"] not in cookie and len(client.cookie) >= 40
    assert client.cookie.encode() not in res["body"]
    other = Client(servers.full_port)
    other.sign_in(key["eval_user"])
    assert other.cookie != client.cookie
    meta = json.loads(client.get("/api/meta")["body"])
    assert meta["signed_in"]["person_id"] == key["eval_user"]
    assert client.get("/api/search?q=memo")["status"] == 200
    out = client.request("POST", "/api/signout")
    assert out["status"] == 200 and "Max-Age=0" in dict(out["headers"])["set-cookie"]
    assert client.get("/api/search?q=memo")["status"] == 401     # the old token is dead
    assert other.get("/api/search?q=memo")["status"] == 200      # other sessions are untouched


def test_sessions_expire():
    now = [1000.0]
    store = SessionStore(ttl_seconds=60, clock=lambda: now[0])
    token = store.issue("U001")
    assert store.resolve(token) == "U001" and store.resolve(token + "x") is None
    assert store.resolve(None) is None and store.resolve("") is None
    now[0] += 61
    assert store.resolve(token) is None
    assert "U001" not in json.dumps(list(store._sessions)) and token not in store._sessions


def test_departed_person_gets_nothing_through_any_endpoint(servers, manifest, full):
    departed = manifest["demo_users"][-1]["person_id"]
    assert full.execute("SELECT status FROM people WHERE person_id = ?",
                        (departed,)).fetchone()[0] == "departed"
    client = Client(servers.full_port)
    client.sign_in(departed)
    for q in ("agreement", "memo", "", "earn-out provisions"):
        result = json.loads(client.get("/api/search?" + urlencode({"q": q, "limit": 50}))["body"])
        assert result["access"] == "denied" and result["total"] == 0 and result["results"] == []
        assert all(v == [] for v in result["facets"].values())
        who = json.loads(client.get("/api/who?" + urlencode({"q": q or "merger"}))["body"])
        assert who["access"] == "denied" and who["people"] == []
    assert json.loads(client.get("/api/suggest?q=ag")["body"]) == {"suggestions": []}
    for (doc_id,) in full.execute("SELECT doc_id FROM docs ORDER BY doc_id LIMIT 40"):
        assert client.get("/api/document?id=" + doc_id)["status"] == 404
    # Empty-filter listing, which returns every visible document for an active user.
    listing = json.loads(client.get("/api/search?practice=Tax&limit=50")["body"])
    assert listing["total"] == 0


def test_requests_for_another_host_name_or_from_another_origin_are_refused(servers, key):
    client = Client(servers.full_port)
    client.sign_in(key["eval_user"])
    for host in ("evil.example", "evil.example:8765", "127.0.0.1.evil.example", ""):
        for path in ("/", "/api/meta", "/api/search?q=memo"):
            assert client.get(path, headers={"Host": host})["status"] == 403, (host, path)
    assert client.get("/api/search?q=memo", headers={"Host": "localhost:1"})["status"] == 200
    cross = client.request("POST", "/api/signin", {"person_id": key["eval_user"]},
                           headers={"Origin": "http://evil.example"})
    assert cross["status"] == 403 and "set-cookie" not in dict(cross["headers"])


def test_response_headers(servers, key):
    client = Client(servers.full_port)
    client.sign_in(key["eval_user"])
    for path in ("/", "/api/meta", "/api/search?q=memo", "/api/document?id=D99999", "/api/nothing"):
        headers = dict(client.get(path)["headers"])
        assert headers["cache-control"] == "no-store"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY" and headers["referrer-policy"] == "no-referrer"
        assert headers["server"] == "kx-demo"          # no interpreter or library version
        assert "access-control-allow-origin" not in headers
    page = dict(client.get("/")["headers"])
    assert "default-src 'none'" in page["content-security-policy"]
    assert "connect-src 'self'" in page["content-security-policy"]


def test_error_responses_are_plain_and_say_nothing_specific(servers, key):
    client = Client(servers.full_port)
    client.sign_in(key["eval_user"])
    bad = client.get("/api/search?q=memo&filed=perhaps")
    assert bad["status"] == 400 and "yes or no" in json.loads(bad["body"])["error"]
    assert json.loads(client.get("/api/search?q=memo&limit=abc")["body"]) == {
        "error": "limit must be a whole number"}
    assert client.get("/api/who?q=merger&type=memo")["status"] == 400
    for method in ("PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
        assert client.request(method, "/api/search?q=memo")["status"] == 405
    for res in (bad, client.get("/api/nothing"), client.get("/api/document?id=x")):
        text = res["body"].decode()
        assert "Traceback" not in text and "sqlite" not in text.lower() and ".py" not in text


def test_search_explain_filters_who_suggest_and_document_work_over_http(servers, key, manifest):
    client = Client(servers.full_port)
    client.sign_in(key["eval_user"])
    page = client.get("/")
    assert page["status"] == 200 and b"Knowledge and experience search" in page["body"]
    meta = json.loads(client.get("/api/meta")["body"])
    assert [u["person_id"] for u in meta["demo_users"]] == [u["person_id"] for u in manifest["demo_users"]]
    assert len(meta["people"]) == 120 and meta["presets"] == PRESETS
    result = json.loads(client.get("/api/search?q=summary%20judgment&type=motion&filed=yes&explain=1")["body"])
    assert result["filters"] == {"doc_type": "motion", "was_filed": 1} and result["user"] == key["eval_user"]
    assert result["results"] and all(r["doc_type"] == "motion" and r["was_filed"] for r in result["results"])
    assert "explain" in result["results"][0] and result["expansion"]["on"] is True
    off = json.loads(client.get("/api/search?q=summary%20judgment&expand=off")["body"])
    assert off["expansion"] == {"on": False, "used": [], "not_found": [], "corrected": [],
                                "related_terms": []}
    assert json.loads(client.get("/api/who?q=asset%20purchase")["body"])["people"]
    assert "indemnification" in json.loads(client.get("/api/suggest?q=indemn")["body"])["suggestions"]
    doc_id = result["results"][0]["doc_id"]
    doc = json.loads(client.get("/api/document?id=" + doc_id)["body"])
    assert doc["doc_id"] == doc_id and doc["title"] == result["results"][0]["title"] and doc["body"]


def test_queries_and_opened_documents_are_audited_under_the_session_user(servers, key, manifest):
    user, tests, _ = wall_cases(key, manifest)[0]
    a, _, hidden = servers(user)
    control = tests[0]["control_user"]
    a.get(f"/api/search?q=audit+marker+one&user={control}")
    a.get(f"/api/document?id={hidden[0]}&user={control}")
    entries = audit.read_entries(servers.full_log)
    assert audit.verify(servers.full_log)["ok"] is True
    marked = [e for e in entries if e["query"] == "audit marker one"]
    assert marked and all(e["user"] == user for e in marked)
    opened = [e for e in entries if e["action"] == "open" and e["user"] == user]
    assert opened and all(hidden[0] not in json.dumps(e) for e in opened)
    assert not [e for e in entries if e["user"] == control and e["query"] == "audit marker one"]


def test_server_binds_to_loopback_only(servers):
    from kx import server
    import inspect
    assert '("127.0.0.1", port)' in inspect.getsource(server.serve)
    assert "0.0.0.0" not in inspect.getsource(server)
