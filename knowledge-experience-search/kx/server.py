"""Local web UI. Standard library only, bound to 127.0.0.1.

Who is asking: a server-side session (kx/session.py). The sign-in step here
is a demo user picker that stands in for the firm's single sign-on. After
sign-in the browser holds only an opaque cookie; the person a query runs as
is looked up on the server. No endpoint reads a user id from the URL.

Every data endpoint goes through kx.service.Service, which is
permission-filtered. There is no endpoint that returns a matter, and the one
that returns a document by id answers "not found" in exactly the same bytes
whether the document does not exist or the user may not open it.
"""
from __future__ import annotations

import json
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from kx.search import FILTER_ALIASES, QueryError
from kx.session import SessionStore

WEB_DIR = Path(__file__).resolve().parent / "web"
SNAPSHOT_MARK = "/*__SNAPSHOT__*/"
COOKIE = "kx_session"
LOCAL_HOSTS = ("127.0.0.1", "localhost")
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")

# Example queries offered to every user. They must not name anything
# confidential: this list is the same for everyone, walled or not.
PRESETS = {
    "search": ["earn-out provisions agreement", "indemnification cap and basket agreement",
               '"forum selection clause" type:motion', "preliminary injunction brief",
               "restraint of trade memo", "tenancy transfer consent agreement",
               "indemnifcation basket memo"],
    "who": ["asset purchase", "loan workout", "zoning entitlement", "charitable planning",
            "redundancy programme"],
}


class BadRequest(ValueError):
    pass


def load_demo_meta(data_dir) -> dict:
    path = Path(data_dir) / "manifest.json"
    if not path.exists():
        return {"demo_users": []}
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    return {"demo_users": manifest.get("demo_users", []), "as_of": manifest.get("as_of")}


def page_html(snapshot: dict | None = None) -> str:
    html = (WEB_DIR / "app.html").read_text(encoding="utf-8")
    if snapshot is None:
        return html.replace(SNAPSHOT_MARK, "")
    payload = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    return html.replace(SNAPSHOT_MARK, f"window.KX_SNAPSHOT = {payload};")


def _whole_number(params, name, default, low, high):
    raw = params.get(name)
    if raw is None or raw == "":
        return default
    if not raw.isdigit():
        raise BadRequest(f"{name} must be a whole number")
    return max(low, min(high, int(raw)))


def make_handler(service, data_dir, sessions: SessionStore | None = None):
    demo = load_demo_meta(data_dir)
    sessions = sessions or SessionStore()

    class Handler(BaseHTTPRequestHandler):
        server_version = "kx-demo"
        sys_version = ""
        store = sessions

        def version_string(self):
            return "kx-demo"   # no interpreter or library version in the Server header

        def log_message(self, fmt, *args):  # quiet; queries are in the audit log
            pass

        # -- plumbing ----------------------------------------------------------
        def _send(self, status, body: bytes, content_type: str, extra=()):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            if content_type.startswith("text/html"):
                self.send_header("Content-Security-Policy", CSP)
            for name, value in extra:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, status=200, extra=()):
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", extra)

        def _local(self) -> bool:
            """Refuse requests addressed to any other host name (DNS rebinding)."""
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host in LOCAL_HOSTS

        def _token(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                return None
            return cookie[COOKIE].value if COOKIE in cookie else None

        def _person_id(self):
            return self.store.resolve(self._token())

        # -- routes ------------------------------------------------------------
        def do_GET(self):
            if not self._local():
                return self._json({"error": "Forbidden"}, 403)
            url = urlparse(self.path)
            params = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    return self._send(200, page_html().encode("utf-8"), "text/html; charset=utf-8")
                if url.path == "/api/meta":
                    # Before sign-in: the staff directory for the demo picker.
                    pid = self._person_id()
                    return self._json({"signed_in": service.person(pid) if pid else None,
                                       "demo_users": demo["demo_users"],
                                       "people": service.users(), "presets": PRESETS})
                if url.path not in ("/api/search", "/api/who", "/api/suggest", "/api/document"):
                    return self._json({"error": "Not found"}, 404)
                user = self._person_id()
                if user is None:
                    return self._json({"error": "Sign in first."}, 401)
                # The user comes from the session only. A "user" parameter, if
                # someone adds one, is not read.
                query = params.get("q", "")
                filters = {k: v for k, v in params.items() if k.lower() in FILTER_ALIASES and v}
                expand = None if params.get("expand", "") in ("", "on", "1") else False
                if url.path == "/api/search":
                    return self._json(service.search(
                        user, query, filters, limit=_whole_number(params, "limit", 10, 1, 50),
                        offset=_whole_number(params, "offset", 0, 0, 100000),
                        explain=params.get("explain") == "1", expand=expand))
                if url.path == "/api/who":
                    return self._json(service.who(
                        user, query, filters, limit=_whole_number(params, "limit", 10, 1, 50),
                        expand=expand))
                if url.path == "/api/suggest":
                    return self._json({"suggestions": service.suggest(user, query)})
                doc = service.document(user, params.get("id", ""))
                if doc is None:
                    return self._json({"error": "Not found"}, 404)
                return self._json(doc)
            except (QueryError, BadRequest) as exc:
                return self._json({"error": str(exc)}, 400)
            except Exception:
                # Say nothing specific: an error message must not become a side channel.
                return self._json({"error": "The request could not be completed."}, 500)

        def do_POST(self):
            if not self._local():
                return self._json({"error": "Forbidden"}, 403)
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
                return self._json({"error": "Forbidden"}, 403)
            url = urlparse(self.path)
            try:
                if url.path == "/api/signout":
                    self.store.revoke(self._token())
                    return self._json({"signed_in": None}, extra=[
                        ("Set-Cookie", f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")])
                if url.path != "/api/signin":
                    return self._json({"error": "Not found"}, 404)
                if "application/json" not in (self.headers.get("Content-Type") or ""):
                    return self._json({"error": "Send JSON."}, 400)
                length = int(self.headers.get("Content-Length") or 0)
                if length > 4096:
                    return self._json({"error": "Request too large."}, 400)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                    person_id = body.get("person_id") if isinstance(body, dict) else None
                except ValueError:
                    person_id = None
                person = service.person(person_id) if isinstance(person_id, str) else None
                if person is None:
                    return self._json({"error": "Unknown person."}, 400)
                # DEMO STAND-IN. A real deployment reaches this point only
                # after the firm's identity provider has authenticated the user.
                self.store.revoke(self._token())
                token = self.store.issue(person["person_id"])
                return self._json({"signed_in": person}, extra=[
                    ("Set-Cookie", f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict")])
            except Exception:
                return self._json({"error": "The request could not be completed."}, 500)

        def _not_allowed(self):
            return self._json({"error": "Method not allowed"}, 405)

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _not_allowed

    return Handler


def serve(service, data_dir, port: int = 8765):
    meta = load_demo_meta(data_dir)
    if meta.get("as_of") and service.as_of is None:
        service.as_of = meta["as_of"]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service, data_dir))
    print(f"Serving on http://127.0.0.1:{httpd.server_address[1]}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
