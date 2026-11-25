#!/usr/bin/env python3
"""Web UI and same-origin proxy for the existing watermark cleaner service.
API credentials are read only from the server environment and never enter HTML.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SERVICE_URL = os.environ.get("WATERMARKS_SERVICE_URL", "http://127.0.0.1:8765").rstrip("/")
API_KEY = os.environ.get("WATERMARKS_SERVER_API_KEY", "").strip()
MAX_BODY = 150 * 1024 * 1024

parts = urlsplit(SERVICE_URL)
if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password:
    raise SystemExit("WATERMARKS_SERVICE_URL must be an http(s) URL without embedded credentials")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"ok": True})
            return
        if self.path in ("/", "/index.html"):
            self.path = "/index.html"
            return super().do_GET()
        if self.path.startswith("/api/"):
            self._json(405, {"ok": False, "error": "Use POST for this endpoint."})
            return
        return self._json(404, {"ok": False, "error": "Not found."})

    def do_POST(self):
        routes = {"/api/inspect": "/inspect", "/api/clean": "/clean"}
        upstream = routes.get(self.path)
        if not upstream:
            self._json(404, {"ok": False, "error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "Upload is empty or exceeds the 100 MB file limit."})
            return
        if "application/json" not in self.headers.get("Content-Type", "").lower():
            self._json(415, {"ok": False, "error": "Expected a JSON request."})
            return
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get("file"), str) or not isinstance(payload.get("name"), str):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "The upload request is not valid."})
            return
        self._proxy(upstream, body)

    def _proxy(self, endpoint: str, body: bytes, max_reply: int = MAX_BODY):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if API_KEY:
            headers["Authorization"] = "Bearer " + API_KEY
        req = urllib.request.Request(SERVICE_URL + endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                status, data = response.status, response.read(max_reply + 1)
        except urllib.error.HTTPError as e:
            status, data = e.code, e.read(max_reply + 1)
        except (urllib.error.URLError, TimeoutError):
            self._json(502, {"ok": False, "error": "The cleaner service is unavailable. Check the server connection."})
            return
        if len(data) > max_reply:
            self._json(502, {"ok": False, "error": "The cleaner service response exceeded the size limit."})
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Never log request bodies or authorization headers.
        super().log_message(fmt, *args)


if __name__ == "__main__":
    host = os.environ.get("WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("WEB_PORT", "8080")))
    print("Nerry's Marks Cleaner listening on %s:%s" % (host, port), flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
