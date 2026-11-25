"""Local web UI. Standard library only, bound to 127.0.0.1.

Demo only. The ``user`` parameter is taken from the request so the user
switcher can show the effect of permissions. A real deployment must take the
user from the firm's sign-in and must never accept it from the browser.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from kx.search import FILTER_ALIASES, QueryError

WEB_DIR = Path(__file__).resolve().parent / "web"
SNAPSHOT_MARK = "/*__SNAPSHOT__*/"

PRESETS = {
    "search": ["earn-out provisions agreement", "indemnification cap and basket agreement",
               '"forum selection clause" type:motion', "preliminary injunction brief",
               "borrowing base memo", "conditional use permit staff report", "project halcyon"],
    "who": ["asset purchase", "loan workout", "zoning entitlement", "charitable planning",
            "preliminary injunction"],
}


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


def make_handler(service, data_dir):
    demo = load_demo_meta(data_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = "kx-demo"

        def log_message(self, fmt, *args):  # quiet; queries are in the audit log
            pass

        def _send(self, status, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):
            url = urlparse(self.path)
            params = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    return self._send(200, page_html().encode("utf-8"), "text/html; charset=utf-8")
                if url.path == "/api/meta":
                    return self._json({"demo_users": demo["demo_users"], "people": service.users(),
                                       "presets": PRESETS})
                user = params.get("user", "")
                query = params.get("q", "")
                filters = {k: v for k, v in params.items() if k.lower() in FILTER_ALIASES and v}
                if url.path == "/api/search":
                    limit = max(1, min(50, int(params.get("limit", "10"))))
                    offset = max(0, int(params.get("offset", "0")))
                    return self._json(service.search(user, query, filters, limit=limit,
                                                     offset=offset,
                                                     explain=params.get("explain") == "1"))
                if url.path == "/api/who":
                    return self._json(service.who(user, query, filters))
                if url.path == "/api/suggest":
                    return self._json({"suggestions": service.suggest(user, query)})
                return self._json({"error": "Not found"}, 404)
            except (QueryError, ValueError) as exc:
                return self._json({"error": str(exc)}, 400)
            except Exception:
                # Say nothing specific: an error message must not become a side channel.
                return self._json({"error": "The request could not be completed."}, 500)

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
