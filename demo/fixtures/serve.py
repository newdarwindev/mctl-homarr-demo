#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later; newdarwindev, 2026-11-01
"""Foreground, loopback-only synthetic board fixture. No Homarr access."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class BoardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/boards/demo":
            self.send_error(404)
            return
        body = Path(__file__).with_name("board.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("Synthetic board fixture: http://127.0.0.1:8765/boards/demo (Ctrl-C to stop)", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", 8765), BoardHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
