import json
import threading
import unittest

from tests import JSON_CT, ServerCase

DOCS = "/api/v1/documents"


class BasicTests(ServerCase):
    def test_health(self):
        status, resp, data = self.json_request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok", "version": "0.1.0", "schema_version": 1})
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.getheader("Referrer-Policy"), "no-referrer")
        self.assertEqual(resp.getheader("Cross-Origin-Resource-Policy"), "same-origin")

    def test_index_html_and_csp(self):
        status, resp, body = self.request("GET", "/")
        # index.html is owned by the frontend; accept 200 only when present.
        self.assertEqual(status, 200)
        self.assertTrue(resp.getheader("Content-Type").startswith("text/html"))
        self.assertIn("default-src 'none'", resp.getheader("Content-Security-Policy"))
        self.assertIn("frame-ancestors 'none'", resp.getheader("Content-Security-Policy"))
        status2, _, body2 = self.request("GET", "/index.html")
        self.assertEqual((status2, body2), (200, body))

    def test_static_allowlist(self):
        for path, ctype in (
            ("/static/app.js", "javascript"),
            ("/static/styles.css", "text/css"),
        ):
            status, resp, _ = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn(ctype, resp.getheader("Content-Type"))

    def test_static_traversal_and_unlisted(self):
        for path in (
            "/static/../x",
            "/static/%2e%2e/x",
            "/static/app.js/..",
            "/static/",
            "/static/index.html",
            "/static/..%5cline_editor/app.py",
            "/line_editor/app.py",
            "/static/app.js/",
            "//etc/passwd",
        ):
            status, _, data = self.request("GET", path)
            self.assertEqual(status, 404, path)
            self.assertEqual(json.loads(data)["error"]["code"], "not_found")

    def test_query_string_ignored_for_routing(self):
        status, _, _ = self.request("GET", "/api/v1/health?x=1")
        self.assertEqual(status, 200)

    def test_sample_endpoint(self):
        status, _, data = self.json_request("GET", "/api/v1/sample")
        self.assertEqual(status, 200)
        self.assertEqual(data["title"], "Sample log")
        lines = data["text"].split("\n")
        self.assertEqual(len(lines), 201)
        self.assertEqual(lines[200], "")
        self.assertEqual(
            lines[0], "2026-01-01T00:00:00Z service-1 INFO event=001 value=37"
        )
        self.assertTrue(lines[9].endswith("service-2 WARN event=010 value=" + str((10 * 37) % 101)))
        self.assertIn("service-1 ERROR event=025", lines[24])
        self.assertTrue(lines[199].startswith("2026-01-01T00:03:19Z service-0 ERROR event=200 value="))
        # sample is not stored
        _, _, listing = self.json_request("GET", DOCS)
        self.assertEqual(listing["documents"], [])

    def test_unknown_route(self):
        status, _, data = self.json_request("GET", "/api/v1/nope")
        self.assertEqual((status, data["error"]["code"]), (404, "not_found"))


class DocumentTests(ServerCase):
    def test_create_get_list_update(self):
        status, resp, data = self.json_request(
            "POST", DOCS, {"title": "  My doc ", "text": "a\r\nb\n"}
        )
        self.assertEqual(status, 201)
        doc = data["document"]
        self.assertEqual(resp.getheader("Location"), f"{DOCS}/{doc['id']}")
        self.assertEqual(doc["title"], "My doc")
        self.assertEqual(doc["text"], "a\r\nb\n")
        self.assertEqual((doc["revision"], doc["size_bytes"]), (1, 5))
        self.assertTrue(doc["created_at"].endswith("Z"))

        status, _, data = self.json_request("GET", f"{DOCS}/{doc['id']}")
        self.assertEqual((status, data["document"]), (200, doc))

        status, _, data = self.json_request(
            "PUT", f"{DOCS}/{doc['id']}", {"title": "New", "text": "z", "base_revision": 1}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["document"]["revision"], 2)
        self.assertEqual(data["document"]["text"], "z")

        other = self.create("other", "")
        _, _, listing = self.json_request("GET", DOCS)
        ids = [d["id"] for d in listing["documents"]]
        self.assertEqual(ids, [other["id"], doc["id"]])
        self.assertNotIn("text", listing["documents"][0])

    def test_get_missing_and_bad_ids(self):
        for path in (f"{DOCS}/999", f"{DOCS}/abc", f"{DOCS}/-1", f"{DOCS}/" + "1" * 19, f"{DOCS}/1/"):
            status, _, data = self.json_request("GET", path)
            self.assertEqual((status, data["error"]["code"]), (404, "not_found"), path)

    def test_put_missing_is_404(self):
        status, _, data = self.json_request(
            "PUT", f"{DOCS}/42", {"title": "t", "text": "", "base_revision": 1}
        )
        self.assertEqual((status, data["error"]["code"]), (404, "not_found"))

    def test_revision_conflict_returns_current(self):
        doc = self.create("t", "v1")
        url = f"{DOCS}/{doc['id']}"
        self.json_request("PUT", url, {"title": "t", "text": "v2", "base_revision": 1})
        status, _, data = self.json_request(
            "PUT", url, {"title": "mine", "text": "mine", "base_revision": 1}
        )
        self.assertEqual(status, 409)
        self.assertEqual(data["error"]["code"], "revision_conflict")
        self.assertEqual(data["current"]["document"]["text"], "v2")
        self.assertEqual(data["current"]["document"]["revision"], 2)
        # stored doc was not touched by the losing save
        _, _, got = self.json_request("GET", url)
        self.assertEqual(got["document"]["text"], "v2")

    def test_concurrent_double_save(self):
        doc = self.create("t", "base")
        url = f"{DOCS}/{doc['id']}"
        results = []
        barrier = threading.Barrier(2)

        def worker(label):
            barrier.wait()
            status, _, _ = self.json_request(
                "PUT", url, {"title": "t", "text": label, "base_revision": 1}
            )
            results.append(status)

        threads = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(sorted(results), [200, 409])
        _, _, got = self.json_request("GET", url)
        self.assertEqual(got["document"]["revision"], 2)

    def test_persistence_across_restart(self):
        doc = self.create("keep", "persist me")
        self.server.stop()
        self.server = self.start_server()
        status, _, data = self.json_request("GET", f"{DOCS}/{doc['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(data["document"]["text"], "persist me")

    def test_document_limit(self):
        from line_editor.storage import Store

        store = Store(self.data_dir)
        for i in range(500):
            store.create_document(f"d{i}", "")
        status, _, data = self.json_request("POST", DOCS, {"title": "x", "text": ""})
        self.assertEqual((status, data["error"]["code"]), (409, "document_limit"))


class LimitTests(ServerCase):
    def post(self, title, text):
        return self.json_request("POST", DOCS, {"title": title, "text": text})

    def test_title_boundaries(self):
        self.assertEqual(self.post("a" * 120, "")[0], 201)
        status, _, data = self.post("a" * 121, "")
        self.assertEqual((status, data["error"]["field"]), (400, "title"))
        self.assertEqual(self.post("\U0001F600" * 120, "")[0], 201)
        self.assertEqual(self.post("\U0001F600" * 121, "")[0], 400)
        self.assertEqual(self.post("   ", "")[0], 400)
        self.assertEqual(self.post("a\x00b", "")[0], 400)

    def test_text_boundaries(self):
        self.assertEqual(self.post("t", "a" * 262144)[0], 201)
        status, _, data = self.post("t", "a" * 262145)
        self.assertEqual((status, data["error"]["code"]), (413, "text_too_large"))
        self.assertEqual(self.post("t", "\U0001F600" * 65536)[0], 201)  # 262144 bytes
        self.assertEqual(self.post("t", "\U0001F600" * 65537)[0], 413)

    def test_text_content_rules(self):
        status, _, data = self.post("t", "a\x00b")
        self.assertEqual((status, data["error"]["field"]), (400, "text"))
        # JSON escape of a lone surrogate
        status, _, data = self.json_request(
            "POST", DOCS, raw=b'{"title":"t","text":"\\ud800"}'
        )
        self.assertEqual((status, data["error"]["code"]), (400, "invalid_field"))

    def test_bad_types_and_keys(self):
        cases = [
            {"title": 1, "text": ""},
            {"title": "t", "text": None},
            {"title": "t"},
            {"text": ""},
            {"title": "t", "text": "", "extra": 1},
            {"title": "t", "text": "", "base_revision": 1},
        ]
        for body in cases:
            status, _, data = self.json_request("POST", DOCS, body)
            self.assertEqual((status, data["error"]["code"]), (400, "invalid_field"), body)

    def test_update_base_revision_types(self):
        doc = self.create()
        url = f"{DOCS}/{doc['id']}"
        for bad in (True, 0, -1, 1.0, "1", None):
            status, _, data = self.json_request(
                "PUT", url, {"title": "t", "text": "", "base_revision": bad}
            )
            self.assertEqual(status, 400, bad)
            self.assertEqual(data["error"]["field"], "base_revision")
        status, _, _ = self.json_request("PUT", url, {"title": "t", "text": ""})
        self.assertEqual(status, 400)

    def test_bad_json(self):
        for raw in (b"{", b"", b"[]", b'"x"', b"null", b"\xff\xfe", b'{"title":NaN}', b"[" * 100000):
            status, _, data = self.json_request("POST", DOCS, raw=raw)
            self.assertEqual((status, data["error"]["code"]), (400, "invalid_json"), raw[:20])

    def test_content_type(self):
        body = b'{"title":"t","text":""}'
        for ct in ("text/plain", "application/x-www-form-urlencoded", "application/json; charset=latin-1"):
            status, _, data = self.request("POST", DOCS, body, {"Content-Type": ct})
            self.assertEqual(status, 415, ct)
            self.assertEqual(json.loads(data)["error"]["code"], "unsupported_media_type")
        status, _, _ = self.request("POST", DOCS, body, {})
        self.assertEqual(status, 415)
        status, _, _ = self.request(
            "POST", DOCS, body, {"Content-Type": "application/json; charset=utf-8"}
        )
        self.assertEqual(status, 201)
        status, _, _ = self.request(
            "POST", DOCS, body, {"Content-Type": "Application/JSON; charset=UTF-8"}
        )
        self.assertEqual(status, 201)

    def test_content_length_errors(self):
        for cl in ("abc", "-1", "1.5", ""):
            status, _, data = self.request(
                "POST", DOCS, b"{}", {**JSON_CT, "Content-Length": cl}
            )
            self.assertEqual(status, 400, repr(cl))
            self.assertEqual(json.loads(data)["error"]["code"], "bad_request")
        # missing Content-Length entirely
        status, _, data = self.request("POST", DOCS, None, JSON_CT)
        self.assertEqual((status, json.loads(data)["error"]["code"]), (400, "bad_request"))

    def test_body_too_large(self):
        body = b'{"title":"t","text":"' + b"a" * (1048576 - 20) + b'"}'
        self.assertGreater(len(body), 1048576)
        status, _, data = self.request("POST", DOCS, body, JSON_CT)
        self.assertEqual((status, json.loads(data)["error"]["code"]), (413, "body_too_large"))
        # declared-but-not-sent huge length is rejected without reading it
        status, _, data = self.request(
            "POST", DOCS, None, {**JSON_CT, "Content-Length": "99999999999"}
        )
        self.assertEqual((status, json.loads(data)["error"]["code"]), (413, "body_too_large"))

    def test_escaped_text_over_body_cap(self):
        # 262144 bytes of control characters escape to 6 bytes each (> 1 MiB).
        text = "\x01" * 262144
        status, _, data = self.json_request("POST", DOCS, {"title": "t", "text": text})
        self.assertEqual((status, data["error"]["code"]), (413, "body_too_large"))

    def test_server_recovers_after_errors(self):
        self.request("POST", DOCS, b"{", JSON_CT)
        self.request("POST", DOCS, None, JSON_CT)
        self.assertEqual(self.create("ok", "fine")["revision"], 1)


class SecurityTests(ServerCase):
    def test_foreign_host(self):
        for host in ("evil.example", "evil.example:%d", "127.0.0.1", "localhost", "127.0.0.1:1", ""):
            h = host % self.port if "%d" in host else host
            status, resp, data = self.request("GET", "/api/v1/health", None, {"Host": h})
            self.assertEqual(status, 403, host)
            self.assertEqual(json.loads(data)["error"]["code"], "forbidden_host")
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))

    def test_localhost_host_allowed(self):
        status, _, _ = self.request(
            "GET", "/api/v1/health", None, {"Host": f"localhost:{self.port}"}
        )
        self.assertEqual(status, 200)

    def test_foreign_host_on_static_and_post(self):
        self.assertEqual(self.request("GET", "/", None, {"Host": "evil.example"})[0], 403)
        status, _, _ = self.request(
            "POST", DOCS, b'{"title":"t","text":""}', {**JSON_CT, "Host": "evil.example"}
        )
        self.assertEqual(status, 403)
        self.assertEqual(self.json_request("GET", DOCS)[2]["documents"], [])

    def test_origin_checks(self):
        body = {"title": "t", "text": ""}
        for origin in ("http://evil.example", "null", "https://127.0.0.1:%d" % self.port,
                       "http://127.0.0.1", "http://127.0.0.1:1"):
            status, resp, data = self.json_request("POST", DOCS, body, {"Origin": origin})
            self.assertEqual(status, 403, origin)
            self.assertEqual(data["error"]["code"], "forbidden_origin")
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))
        for origin in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            status, resp, _ = self.json_request("POST", DOCS, body, {"Origin": origin})
            self.assertEqual(status, 201, origin)
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))
        doc = self.create()
        status, _, _ = self.json_request(
            "PUT", f"{DOCS}/{doc['id']}",
            {"title": "t", "text": "", "base_revision": 1},
            {"Origin": "http://evil.example"},
        )
        self.assertEqual(status, 403)
        _, _, got = self.json_request("GET", f"{DOCS}/{doc['id']}")
        self.assertEqual(got["document"]["revision"], 1)

    def test_no_cors_headers_anywhere(self):
        for method, path in (("GET", "/"), ("GET", "/api/v1/health"), ("GET", DOCS), ("OPTIONS", DOCS)):
            _, resp, _ = self.request(
                method, path, None, {"Origin": f"http://127.0.0.1:{self.port}"}
            )
            names = [k.lower() for k, _ in resp.getheaders()]
            self.assertFalse([n for n in names if n.startswith("access-control-")], path)

    def test_options_and_other_methods(self):
        for method in ("OPTIONS", "DELETE", "PATCH", "HEAD"):
            for path in (DOCS, f"{DOCS}/1", "/api/v1/health", "/"):
                status, resp, _ = self.request(method, path)
                self.assertEqual(status, 405, (method, path))
                self.assertTrue(resp.getheader("Allow"))
        _, resp, _ = self.request("OPTIONS", DOCS)
        self.assertEqual(resp.getheader("Allow"), "GET, POST")
        _, resp, _ = self.request("DELETE", f"{DOCS}/1")
        self.assertEqual(resp.getheader("Allow"), "GET, PUT")
        self.assertEqual(self.request("POST", "/api/v1/health")[0], 405)
        self.assertEqual(self.request("PUT", DOCS)[0], 405)

    def test_options_unknown_path_is_404(self):
        self.assertEqual(self.request("OPTIONS", "/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
