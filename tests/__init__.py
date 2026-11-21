"""Shared helpers for the line_editor tests (stdlib unittest only)."""

import http.client
import json
import tempfile
import unittest

from line_editor.app import create_server

JSON_CT = {"Content-Type": "application/json"}


class ServerCase(unittest.TestCase):
    """Starts a server on a loopback ephemeral port over a temp data dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = self._tmp.name
        self.server = self.start_server()

    def start_server(self):
        server = create_server(self.data_dir, 0)
        server.start()
        self.addCleanup(server.stop)  # runs before _tmp.cleanup (LIFO)
        return server

    @property
    def port(self):
        return self.server.port

    def request(self, method, path, body=None, headers=None, port=None):
        """Send a request with full header control.

        body: bytes, str, or None. If headers lacks Host, a valid one is added.
        Content-Length is added automatically when body is given, unless the
        headers dict already names it (use that to send bad values).
        Returns (status, response_headers, raw_body_bytes).
        """
        port = port or self.port
        headers = dict(headers or {})
        lower = {k.lower() for k in headers}
        if isinstance(body, str):
            body = body.encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if "host" not in lower:
                conn.putheader("Host", f"127.0.0.1:{port}")
            if body is not None and "content-length" not in lower:
                conn.putheader("Content-Length", str(len(body)))
            for k, v in headers.items():
                if v is not None:
                    conn.putheader(k, v)
            conn.endheaders(body)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, resp, data
        finally:
            conn.close()

    def json_request(self, method, path, obj=None, headers=None, raw=None):
        h = dict(JSON_CT)
        h.update(headers or {})
        body = raw if raw is not None else (
            json.dumps(obj).encode("utf-8") if obj is not None else None
        )
        status, resp, data = self.request(method, path, body, h)
        return status, resp, (json.loads(data) if data else None)

    def create(self, title="T", text="hello"):
        status, _, data = self.json_request(
            "POST", "/api/v1/documents", {"title": title, "text": text}
        )
        self.assertEqual(status, 201, data)
        return data["document"]
