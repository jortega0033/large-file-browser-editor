"""HTTP server, routing and static serving (loopback only)."""

import json
import os
import re
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from . import storage
from .sample import SAMPLE_TITLE, build_sample_text
from .validation import MAX_BODY_BYTES, ApiError, validate_payload

BIND_HOST = "127.0.0.1"
REQUEST_TIMEOUT = 10
DRAIN_LIMIT = 8 * 1024 * 1024
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

HTML = "text/html; charset=utf-8"
# Exact allowlist: request path -> (file name inside STATIC_DIR, content type).
STATIC_FILES = {
    "/": ("index.html", HTML),
    "/index.html": ("index.html", HTML),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
JSON_TYPE = "application/json; charset=utf-8"
DOC_PATH = re.compile(r"/api/v1/documents/([0-9]{1,18})")


def _reject_constant(name):
    raise ValueError(f"invalid JSON constant {name}")


def _content_type_ok(value):
    if value is None:
        return False
    parts = value.split(";")
    if parts[0].strip().lower() != "application/json":
        return False
    for param in parts[1:]:
        if not param.strip():
            continue
        key, _, val = param.partition("=")
        if key.strip().lower() == "charset":
            if val.strip().strip('"').lower() != "utf-8":
                return False
    return True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = REQUEST_TIMEOUT
    server_version = "LineEditor/" + __version__
    sys_version = ""

    def version_string(self):
        return self.server_version

    def log_message(self, format, *args):
        if getattr(self.server, "log_requests", False):
            super().log_message(format, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    # ---- method entry points: everything funnels into _handle ----
    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def do_OPTIONS(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    # ---- core ----
    def _handle(self):
        self.close_connection = True
        self._unread = self._parse_length() or 0
        try:
            self._dispatch()
        except ApiError as e:
            self._send_error_safe(e)
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except storage.NotFound:
            self._send_error_safe(ApiError(404, "not_found", "Document not found."))
        except storage.DocumentLimit:
            self._send_error_safe(
                ApiError(409, "document_limit", "The document limit has been reached.")
            )
        except sqlite3.Error as e:
            print(f"storage error: {type(e).__name__}", file=sys.stderr)
            self._send_error_safe(
                ApiError(503, "storage_unavailable", "The database is unavailable.")
            )
        except Exception as e:  # last resort; never echo internals
            print(f"internal error: {type(e).__name__}", file=sys.stderr)
            self._send_error_safe(
                ApiError(500, "internal_error", "Internal server error.")
            )

    def _send_error_safe(self, err):
        try:
            self._send_json(err.status, err.body(), err.headers)
        except OSError:
            self.close_connection = True

    def _dispatch(self):
        method = self.command
        self._check_host()
        path = self.path.split("?", 1)[0]

        if path in STATIC_FILES:
            allow = ("GET",)
            handler = self._serve_static
            arg = path
        elif path == "/api/v1/health":
            allow, handler, arg = ("GET",), self._health, None
        elif path == "/api/v1/sample":
            allow, handler, arg = ("GET",), self._sample, None
        elif path == "/api/v1/documents":
            allow, handler, arg = ("GET", "POST"), self._documents, None
        else:
            m = DOC_PATH.fullmatch(path)
            if m is None:
                raise ApiError(404, "not_found", "Not found.")
            allow, handler, arg = ("GET", "PUT"), self._document, int(m.group(1))

        if method not in allow:
            raise ApiError(
                405,
                "method_not_allowed",
                "Method not allowed.",
                headers={"Allow": ", ".join(allow)},
            )
        handler(method, arg)

    # ---- security checks ----
    def _allowed_hosts(self):
        p = self.server.port
        return {f"127.0.0.1:{p}", f"localhost:{p}"}

    def _check_host(self):
        hosts = self.headers.get_all("Host") or []
        if len(hosts) != 1 or hosts[0].strip().lower() not in self._allowed_hosts():
            raise ApiError(403, "forbidden_host", "Host not allowed.")

    def _check_origin(self):
        origin = self.headers.get("Origin")
        if origin is None:
            return
        p = self.server.port
        allowed = {f"http://127.0.0.1:{p}", f"http://localhost:{p}"}
        if origin.strip().lower() not in allowed:
            raise ApiError(403, "forbidden_origin", "Origin not allowed.")

    # ---- request body ----
    def _parse_length(self):
        """Content-Length as int, or None when missing/invalid."""
        vals = self.headers.get_all("Content-Length") or []
        if len(vals) != 1:
            return None
        s = vals[0].strip()
        if not (s.isascii() and s.isdigit()):
            return None
        if len(s) > 18:
            return 10**18
        return int(s)

    def _read_json_body(self):
        if not _content_type_ok(self.headers.get("Content-Type")):
            raise ApiError(
                415,
                "unsupported_media_type",
                "Content-Type must be application/json (UTF-8).",
            )
        if self.headers.get("Transfer-Encoding") is not None:
            raise ApiError(400, "bad_request", "Transfer-Encoding is not supported.")
        length = self._parse_length()
        if length is None:
            raise ApiError(400, "bad_request", "A valid Content-Length is required.")
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "body_too_large", "Request body is too large.")
        body = self.rfile.read(length)
        self._unread = 0
        if len(body) != length:
            raise ApiError(400, "bad_request", "Request body was incomplete.")
        try:
            return json.loads(body.decode("utf-8"), parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ApiError(400, "invalid_json", "Request body is not valid JSON.") from None

    # ---- responses ----
    def _send(self, status, body, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True
        self._drain()

    def _send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, JSON_TYPE, headers)

    def _drain(self):
        """After an early error response, discard (bounded) unread body bytes so
        the client is not reset while still sending. Runs after the response."""
        remaining = min(self._unread, DRAIN_LIMIT)
        self._unread = 0
        if remaining <= 0:
            return
        try:
            self.connection.settimeout(1.0)
            while remaining > 0:
                chunk = self.rfile.read1(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    # ---- route handlers ----
    def _serve_static(self, method, path):
        name, ctype = STATIC_FILES[path]
        try:
            with open(os.path.join(STATIC_DIR, name), "rb") as f:
                data = f.read()
        except OSError:
            raise ApiError(404, "not_found", "Not found.") from None
        headers = {"Content-Security-Policy": CSP} if ctype == HTML else None
        self._send(200, data, ctype, headers)

    def _health(self, method, _arg):
        self._send_json(
            200,
            {"status": "ok", "version": __version__, "schema_version": storage.SCHEMA_VERSION},
        )

    def _sample(self, method, _arg):
        self._send_json(200, {"title": SAMPLE_TITLE, "text": build_sample_text()})

    def _documents(self, method, _arg):
        store = self.server.store
        if method == "GET":
            self._send_json(200, {"documents": store.list_documents()})
            return
        self._check_origin()
        data = validate_payload(self._read_json_body(), update=False)
        doc = store.create_document(data["title"], data["text"])
        self._send_json(
            201, {"document": doc}, {"Location": f"/api/v1/documents/{doc['id']}"}
        )

    def _document(self, method, doc_id):
        store = self.server.store
        if method == "GET":
            self._send_json(200, {"document": store.get_document(doc_id)})
            return
        self._check_origin()
        data = validate_payload(self._read_json_body(), update=True)
        try:
            doc = store.update_document(
                doc_id, data["title"], data["text"], data["base_revision"]
            )
        except storage.RevisionConflict as c:
            rev = c.current["revision"]
            raise ApiError(
                409,
                "revision_conflict",
                f"This document was changed elsewhere (now revision {rev}).",
                field="base_revision",
                extra={"current": {"document": c.current}},
            ) from None
        self._send_json(200, {"document": doc})


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets another process share the port; keep it off there.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, handler, store):
        self.store = store
        self.log_requests = False
        self._thread = None
        self._closed = False
        super().__init__(address, handler)
        self.port = self.server_address[1]

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
        )
        self._thread.start()

    def stop(self):
        thread, self._thread = self._thread, None
        if thread is not None:
            self.shutdown()
        if not self._closed:
            self._closed = True
            self.server_close()
        if thread is not None:
            thread.join()


def create_server(data_dir, port=0):
    """Open the store (may raise storage.StoreError) and bind 127.0.0.1:port."""
    store = storage.Store(data_dir)
    return AppServer((BIND_HOST, port), Handler, store)
