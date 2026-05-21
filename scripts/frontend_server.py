#!/usr/bin/env python3
"""Локальний фронт + проксі /api → віддалений бекенд (без CORS у браузері)."""
import http.server
import os
import re
import urllib.error
import urllib.request

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def read_remote_api() -> str:
    env = os.environ.get("REMOTE_API", "").strip()
    if env:
        return env.rstrip("/")
    config_path = os.path.join(FRONTEND_DIR, "config.js")
    if os.path.isfile(config_path):
        text = open(config_path, encoding="utf-8").read()
        m = re.search(r'API_BASE:\s*["\']([^"\']+)["\']', text)
        if m:
            return m.group(1).rstrip("/")
    return "http://100.113.28.5:8000"


class FrontendHandler(http.server.SimpleHTTPRequestHandler):
    remote_api = "http://100.113.28.5:8000"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def _proxy(self, path: str) -> None:
        url = f"{self.remote_api}{path}"
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        headers = {}
        if self.headers.get("Content-Type"):
            headers["Content-Type"] = self.headers["Content-Type"]
        req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                ct = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ct)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_error(502, f"Проксі → {url}: {e}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy(self.path[4:])
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy(self.path[4:])
            return
        self.send_error(405)

    def log_message(self, format: str, *args) -> None:
        if args and args[0].startswith("GET /api"):
            print(f"[proxy] {args[0]} → {self.remote_api}")
        elif args and not args[0].startswith("GET /"):
            super().log_message(format, *args)


def main() -> None:
    port = int(os.environ.get("FRONTEND_PORT", "8080"))
    FrontendHandler.remote_api = read_remote_api()
    server = http.server.ThreadingHTTPServer(("", port), FrontendHandler)
    print(f"Фронтенд:  http://localhost:{port}")
    print(f"Проксі API: http://localhost:{port}/api → {FrontendHandler.remote_api}")
    server.serve_forever()


if __name__ == "__main__":
    main()
