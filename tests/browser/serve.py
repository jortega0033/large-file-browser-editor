"""Test-only harness server: the application plus the pages under tests/browser/.

    python -m tests.browser.serve --port 0

It subclasses the application's request handler, so every application route,
the Host and Origin checks, the body cap and the security headers are the real
ones, and the harness pages run under the real Content-Security-Policy. On top
of that it serves an explicit allowlist of files from this directory and two
test-only routes:

    GET  /tests/browser/now      the server's monotonic clock in milliseconds
    POST /tests/browser/report   a suite's JSON report, keyed by the body field "run"

Nothing in this module is part of ``line_editor`` and none of it is reachable on
the application server.
"""

import argparse
import os
import sys
import tempfile
import threading
import time

from line_editor import storage
from line_editor.app import BIND_HOST, CSP, HTML, AppServer, Handler
from line_editor.validation import ApiError

HARNESS_DIR = os.path.dirname(os.path.abspath(__file__))
PREFIX = "/tests/browser/"
JS = "text/javascript; charset=utf-8"

# Exact allowlist: request path -> (file name inside HARNESS_DIR, content type).
# A later ticket adds its page and scripts here. Python files are never listed.
HARNESS_FILES = {
    PREFIX + "selftest.html": ("selftest.html", HTML),
    PREFIX + "selftest.js": ("selftest.js", JS),
    PREFIX + "echo_worker.js": ("echo_worker.js", JS),
    PREFIX + "harness.js": ("harness.js", JS),
    PREFIX + "prng.js": ("prng.js", JS),
    PREFIX + "fixtures.js": ("fixtures.js", JS),
}
NOW_PATH = PREFIX + "now"
REPORT_PATH = PREFIX + "report"


class ReportBoard:
    """Reports in memory, keyed by run token. Never written to disk."""

    def __init__(self):
        self._lock = threading.Condition()
        self._state = {}  # token -> report dict once answered, else None

    def expect(self, token):
        with self._lock:
            self._state[token] = None

    def submit(self, token, report):
        """Store a report for an expected, unanswered token. False otherwise."""
        with self._lock:
            if token not in self._state or self._state[token] is not None:
                return False
            self._state[token] = report
            self._lock.notify_all()
            return True

    def wait(self, token, timeout, stop=None):
        """Return the report, or None on timeout or when ``stop()`` turns true."""
        deadline = time.monotonic() + timeout
        with self._lock:
            while self._state.get(token) is None:
                if stop is not None and stop():
                    return None
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._lock.wait(min(left, 0.2))
            return self._state[token]


class HarnessHandler(Handler):
    def _dispatch(self):
        self._check_host()
        path = self.path.split("?", 1)[0]
        if path in HARNESS_FILES:
            self._only("GET")
            self._serve_harness_file(path)
        elif path == NOW_PATH:
            self._only("GET")
            self._send_json(200, time.monotonic() * 1000.0)
        elif path == REPORT_PATH:
            self._only("POST")
            self._receive_report()
        else:
            super()._dispatch()

    def _only(self, method):
        if self.command != method:
            raise ApiError(
                405, "method_not_allowed", "Method not allowed.", headers={"Allow": method}
            )

    def _serve_harness_file(self, path):
        name, ctype = HARNESS_FILES[path]
        try:
            with open(os.path.join(HARNESS_DIR, name), "rb") as f:
                data = f.read()
        except OSError:
            raise ApiError(404, "not_found", "Not found.") from None
        headers = {"Content-Security-Policy": CSP} if ctype == HTML else None
        self._send(200, data, ctype, headers)

    def _receive_report(self):
        # Same guards as the API, in the same order: Host (done), Origin, content
        # type, Transfer-Encoding and Content-Length, the body cap, JSON syntax.
        self._check_origin()
        body = self._read_json_body()
        token = body.get("run") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise ApiError(400, "invalid_field", "The report needs a string field run.", field="run")
        if not self.server.reports.submit(token, body):
            raise ApiError(409, "unknown_run", "No run is waiting for this token.")
        self._send_json(200, {"status": "received"})


class HarnessServer(AppServer):
    def __init__(self, address, handler, store):
        self.reports = ReportBoard()
        super().__init__(address, handler, store)


def create_harness_server(data_dir, port=0):
    """Open a store in ``data_dir`` and bind 127.0.0.1:port with the harness handler."""
    return HarnessServer((BIND_HOST, port), HarnessHandler, storage.Store(data_dir))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tests.browser.serve")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    with tempfile.TemporaryDirectory(prefix="lfbe-harness-", ignore_cleanup_errors=True) as data_dir:
        try:
            server = create_harness_server(data_dir, args.port)
        except OSError as e:
            print(f"serve: cannot listen on port {args.port}: {e.strerror or e}", file=sys.stderr)
            return 2
        try:
            print(f"Serving harness on http://{BIND_HOST}:{server.port}{PREFIX}", flush=True)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
