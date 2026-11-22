"""Python parts of the browser harness (#7): fixture tool, harness server, runner.

None of these tests starts a browser. The runner is exercised with the Python
interpreter as a stand-in "browser" that exits at once.
"""

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from line_editor.app import CSP
from line_editor.sample import build_sample_text
from tests import ServerCase
from tests.browser import make_fixture, run_headless, serve

JSON_CT = {"Content-Type": "application/json"}
MIB = 1024 * 1024

PINNED_OUTPUTS = {
    7: [50271532, 266108690, 4195786334],
    99: [1118692146, 3456687457, 2323025554],
    1337: [792042790, 815997621, 3480950701],
    2024: [3486492848, 3052955074, 2793987405],
}


def fixture_bytes(lines, **kwargs):
    return b"".join(make_fixture.fixture_blocks(lines, **kwargs))


class GeneratorTests(unittest.TestCase):
    def test_mulberry32_pinned_outputs(self):
        for seed, expected in PINNED_OUTPUTS.items():
            gen = make_fixture.mulberry32(seed)
            self.assertEqual([next(gen) for _ in range(3)], expected, f"seed {seed}")


class FixtureTests(unittest.TestCase):
    def test_200_lines_equal_the_sample_text(self):
        data = fixture_bytes(200, eol="lf")
        self.assertEqual(data, build_sample_text().encode("utf-8"))
        self.assertEqual(len(data), 10991)

    def test_lf_10000_lines_size_and_digest(self):
        data = fixture_bytes(10000, eol="lf")
        self.assertEqual(len(data), 558511)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "83ea4b136fe6da1f75a1d1939d51f7011551e83d8030352ec1bc35958b24b2a7",
        )

    def test_late_lines_are_not_wrapped(self):
        from line_editor.sample import sample_line

        self.assertEqual(sample_line(500000), "2026-01-01T138:53:19Z service-0 ERROR event=500000 value=32")
        self.assertEqual(sample_line(1000000), "2026-01-01T277:46:39Z service-0 ERROR event=1000000 value=64")

    def test_crlf_and_bom_variants(self):
        lf = fixture_bytes(1000, eol="lf")
        crlf = fixture_bytes(1000, eol="crlf")
        self.assertEqual(crlf, lf.replace(b"\n", b"\r\n"))
        self.assertEqual(len(crlf), len(lf) + 1000)
        bom = fixture_bytes(1000, eol="lf", bom=True)
        self.assertEqual(bom, b"\xef\xbb\xbf" + lf)

    def test_mixed_follows_the_generator_and_the_seed(self):
        mixed = fixture_bytes(2000, eol="mixed", seed=7)
        gen = make_fixture.mulberry32(7)
        expected_crlf = sum(next(gen) & 1 for _ in range(2000))
        self.assertEqual(mixed.count(b"\r\n"), expected_crlf)
        self.assertEqual(mixed.count(b"\n"), 2000)
        self.assertEqual(mixed.replace(b"\r\n", b"\n"), fixture_bytes(2000, eol="lf"))
        self.assertNotEqual(mixed, fixture_bytes(2000, eol="mixed", seed=8))

    def test_mixed_10000_lines_seed_7_digest(self):
        data = fixture_bytes(10000, eol="mixed", seed=7)
        self.assertEqual(len(data), 563529)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "df6acdf8d463b2702b0e6c0f853087aa96c64c4a2f819b7fc36082bf698e329c",
        )

    def test_command_line_prints_length_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fx.log")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = make_fixture.main(["--lines", "10000", "--eol", "lf", "--out", out])
            self.assertEqual(code, 0)
            with open(out, "rb") as f:
                data = f.read()
        self.assertEqual(buf.getvalue().split(), ["558511", hashlib.sha256(data).hexdigest()])

    def test_command_line_rejects_bad_eol(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            make_fixture.main(["--lines", "1", "--eol", "cr", "--out", "x"])
        self.assertEqual(cm.exception.code, 2)


class HarnessServerCase(ServerCase):
    def start_server(self):
        server = serve.create_harness_server(self.data_dir, 0)
        server.start()
        self.addCleanup(server.stop)
        return server

    def post_report(self, obj=None, raw=None, headers=None):
        status, _, data = self.json_request("POST", serve.REPORT_PATH, obj, headers, raw)
        return status, data


class HarnessRoutesTests(HarnessServerCase):
    def test_page_has_the_application_csp(self):
        status, resp, _ = self.request("GET", "/tests/browser/selftest.html")
        self.assertEqual(status, 200)
        _, root, _ = self.request("GET", "/")
        self.assertEqual(resp.getheader("Content-Security-Policy"), CSP)
        self.assertEqual(resp.getheader("Content-Security-Policy"), root.getheader("Content-Security-Policy"))
        self.assertTrue(resp.getheader("Content-Type").startswith("text/html"))

    def test_scripts_are_served_as_javascript(self):
        for name in ("harness.js", "prng.js", "fixtures.js", "selftest.js", "echo_worker.js"):
            status, resp, _ = self.request("GET", "/tests/browser/" + name)
            self.assertEqual(status, 200, name)
            self.assertTrue(resp.getheader("Content-Type").startswith("text/javascript"), name)

    def test_application_routes_stay_available(self):
        status, _, data = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["status"], "ok")
        self.assertEqual(self.request("GET", "/static/app.js")[0], 200)

    def test_everything_outside_the_allowlist_is_404(self):
        for path in (
            "/tests/browser/serve.py",
            "/tests/browser/run_headless.py",
            "/tests/browser/__init__.py",
            "/tests/browser/../../README.md",
            "/tests/browser/..%2f..%2fREADME.md",
            "/tests/browser/%2e%2e/%2e%2e/README.md",
            "/tests/browser/",
            "/tests/browser/missing.html",
            "/tests/browser/Selftest.html",
            "/tests/test_api.py",
        ):
            self.assertEqual(self.request("GET", path)[0], 404, path)

    def test_allowlist_names_no_python_file(self):
        for path, (name, _) in serve.HARNESS_FILES.items():
            self.assertFalse(name.endswith(".py"), path)
            self.assertTrue(path.startswith("/tests/browser/"), path)
            self.assertTrue(os.path.isfile(os.path.join(serve.HARNESS_DIR, name)), path)

    def test_query_string_is_ignored_on_harness_paths(self):
        status, resp, _ = self.request("GET", "/tests/browser/selftest.html?fail=1&run=abc")
        self.assertEqual(status, 200)
        self.assertEqual(resp.getheader("Content-Security-Policy"), CSP)
        self.assertEqual(self.request("GET", "/tests/browser/now?x=1")[0], 200)
        self.assertEqual(self.request("GET", "/tests/browser/serve.py?selftest.html")[0], 404)

    def test_foreign_host_is_403(self):
        for path in ("/tests/browser/selftest.html", "/tests/browser/now", "/tests/browser/report"):
            status, _, _ = self.request("GET", path, headers={"Host": "evil.example"})
            self.assertEqual(status, 403, path)
        # the Host check comes before the Origin check and the method check
        status, _, data = self.request(
            "POST", "/tests/browser/report", b'{"run": "x"}',
            {"Host": "evil.example", "Origin": "http://127.0.0.1:1", **JSON_CT},
        )
        self.assertEqual((status, json.loads(data)["error"]["code"]), (403, "forbidden_host"))

    def test_now_is_a_number_that_advances(self):
        status, resp, data = self.request("GET", "/tests/browser/now")
        self.assertEqual(status, 200)
        first = json.loads(data)
        self.assertIsInstance(first, float)
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        import time

        time.sleep(0.05)
        second = json.loads(self.request("GET", "/tests/browser/now")[2])
        self.assertGreater(second, first)

    def test_methods(self):
        status, resp, _ = self.request("POST", "/tests/browser/now", b"", {"Content-Length": "0"})
        self.assertEqual((status, resp.getheader("Allow")), (405, "GET"))
        status, resp, _ = self.request("GET", "/tests/browser/report")
        self.assertEqual((status, resp.getheader("Allow")), (405, "POST"))
        self.assertEqual(self.request("PUT", "/tests/browser/selftest.html", b"", {"Content-Length": "0"})[0], 405)
        for method in ("HEAD", "OPTIONS"):
            for path in ("/tests/browser/now", "/tests/browser/report"):
                status, resp, _ = self.request(method, path)
                self.assertEqual(status, 405, (method, path))
                self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))


class ReportRouteTests(HarnessServerCase):
    def test_expected_token_is_received_once(self):
        self.server.reports.expect("tok1")
        report = {"run": "tok1", "suite": "x", "passed": 1, "failed": 0}
        status, data = self.post_report(report)
        self.assertEqual((status, data), (200, {"status": "received"}))
        self.assertEqual(self.server.reports.wait("tok1", 0), report)
        status, data = self.post_report(report)
        self.assertEqual(status, 409)
        self.assertEqual(data["error"]["code"], "unknown_run")

    def test_unknown_token_is_409(self):
        status, data = self.post_report({"run": "never-registered"})
        self.assertEqual((status, data["error"]["code"]), (409, "unknown_run"))

    def test_missing_or_bad_token_is_400_on_field_run(self):
        for body in ({}, {"suite": "x"}, {"run": 5}, {"run": ""}, {"run": None}, [1, 2]):
            status, data = self.post_report(body)
            self.assertEqual(status, 400, body)
            self.assertEqual(data["error"]["code"], "invalid_field", body)
            self.assertEqual(data["error"].get("field"), "run", body)

    def test_invalid_json_is_400_before_the_token(self):
        status, data = self.post_report(raw=b"{not json")
        self.assertEqual((status, data["error"]["code"]), (400, "invalid_json"))

    def raw_post(self, body, headers):
        status, _, data = self.request("POST", "/tests/browser/report", body, headers)
        return status, json.loads(data)["error"]["code"]

    def test_guards_do_not_depend_on_the_token(self):
        self.server.reports.expect("tok2")
        good = b'{"run": "tok2"}'
        origin_bad = {"Origin": "http://evil.example"}
        self.assertEqual(self.raw_post(good, {**JSON_CT, **origin_bad}), (403, "forbidden_origin"))
        self.assertEqual(self.raw_post(good, {"Content-Type": "text/plain"}), (415, "unsupported_media_type"))
        self.assertEqual(
            self.raw_post(None, {**JSON_CT, "Content-Length": str(MIB + 1)}), (413, "body_too_large")
        )
        self.assertEqual(
            self.raw_post(good, {**JSON_CT, "Transfer-Encoding": "chunked"}), (400, "bad_request")
        )
        self.assertEqual(self.raw_post(good, {**JSON_CT, "Content-Length": "abc"}), (400, "bad_request"))
        # none of the refused requests consumed the token
        self.assertEqual(self.post_report({"run": "tok2"})[0], 200)

    def test_guards_run_in_the_documented_order(self):
        good = b'{"run": "tok-order"}'
        # Origin before content type
        self.assertEqual(
            self.raw_post(good, {"Content-Type": "text/plain", "Origin": "http://evil.example"}),
            (403, "forbidden_origin"),
        )
        # content type before Transfer-Encoding
        self.assertEqual(
            self.raw_post(good, {"Content-Type": "text/plain", "Transfer-Encoding": "chunked"}),
            (415, "unsupported_media_type"),
        )
        # Transfer-Encoding before the body cap
        self.assertEqual(
            self.raw_post(None, {**JSON_CT, "Transfer-Encoding": "chunked", "Content-Length": str(MIB + 1)}),
            (400, "bad_request"),
        )
        # the body cap before JSON syntax and before the token
        self.assertEqual(
            self.raw_post(None, {**JSON_CT, "Content-Length": str(MIB + 1)}), (413, "body_too_large")
        )

    def test_same_origin_post_with_an_origin_header_is_accepted(self):
        for host in ("127.0.0.1", "localhost"):
            token = "tok-" + host
            self.server.reports.expect(token)
            status, _, _ = self.request(
                "POST", "/tests/browser/report", json.dumps({"run": token}).encode(),
                {**JSON_CT, "Host": f"{host}:{self.port}", "Origin": f"http://{host}:{self.port}"},
            )
            self.assertEqual(status, 200, host)

    def test_token_comes_from_the_body_not_the_query(self):
        self.server.reports.expect("tok-query")
        status, _, data = self.request(
            "POST", "/tests/browser/report?run=tok-query", b"{}", JSON_CT
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(data)["error"]["field"], "run")
        self.assertEqual(self.post_report({"run": "tok-query"})[0], 200)

    def test_body_of_exactly_1_mib_is_accepted_and_one_more_byte_is_not(self):
        self.server.reports.expect("tok-big")
        prefix = b'{"run": "tok-big", "pad": "'
        suffix = b'"}'
        body = prefix + b"x" * (MIB - len(prefix) - len(suffix)) + suffix
        self.assertEqual(len(body), MIB)
        self.assertEqual(self.request("POST", "/tests/browser/report", body, JSON_CT)[0], 200)
        status, _, _ = self.request("POST", "/tests/browser/report", body + b" ", JSON_CT)
        self.assertEqual(status, 413)

    def test_one_token_answered_by_two_threads_at_once_gives_one_200(self):
        import threading

        self.server.reports.expect("tok-race")
        results = []

        def send():
            results.append(self.post_report({"run": "tok-race"})[0])

        threads = [threading.Thread(target=send) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), [200, 409, 409, 409])

    def test_a_report_never_reaches_the_data_directory(self):
        def snapshot():
            return sorted(
                (os.path.join(r, f), os.path.getsize(os.path.join(r, f)))
                for r, _, files in os.walk(self.data_dir) for f in files
            )

        before = snapshot()
        self.server.reports.expect("tok3")
        self.assertEqual(self.post_report({"run": "tok3", "blob": "x" * 100000})[0], 200)
        self.assertEqual(snapshot(), before)

    def test_report_board_wait_returns_on_stop_and_timeout(self):
        board = serve.ReportBoard()
        board.expect("t")
        self.assertIsNone(board.wait("t", 0.05))
        self.assertIsNone(board.wait("t", 5, stop=lambda: True))
        self.assertIsNone(board.wait("unknown", 0.05))


class ApplicationServerCase(ServerCase):
    def test_harness_routes_do_not_exist_on_the_application_server(self):
        self.assertEqual(self.request("GET", "/tests/browser/now")[0], 404)
        self.assertEqual(self.request("GET", "/tests/browser/selftest.html")[0], 404)
        status, _, _ = self.request(
            "POST", "/tests/browser/report", b'{"run": "x"}', JSON_CT
        )
        self.assertEqual(status, 404)


class RunnerTests(unittest.TestCase):
    def run_main(self, argv, **env):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = run_headless.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_unknown_suite_is_a_usage_error_naming_the_known_suites(self):
        code, _, err = self.run_main(["no-such-suite"])
        self.assertEqual(code, 2)
        self.assertIn("selftest", err)

    def test_unknown_suite_with_a_query_is_checked_by_name(self):
        self.assertEqual(self.run_main(["nope?fail=1"])[0], 2)

    def test_bad_timeout_is_a_usage_error(self):
        self.assertEqual(self.run_main(["selftest", "--timeout", "0"])[0], 2)

    def test_no_browser_is_skipped_with_exit_3(self):
        with mock.patch.object(run_headless, "find_browser", return_value=None):
            code, out, _ = self.run_main(["selftest"])
        self.assertEqual(code, 3)
        self.assertIn("skipped: no browser found", out)

    def test_a_missing_browser_path_falls_through_to_the_other_locations(self):
        missing = os.path.join(tempfile.gettempdir(), "no-such-browser-program")
        with mock.patch.dict(os.environ, {"LFBE_BROWSER": missing}):
            with mock.patch.object(run_headless.sys, "platform", "freebsd"), \
                    mock.patch.object(run_headless.shutil, "which", return_value=None):
                self.assertIsNone(run_headless.find_browser())
            with mock.patch.object(run_headless, "_candidates", return_value=iter([missing, sys.executable])):
                self.assertEqual(run_headless.find_browser(), sys.executable)

    def test_default_set_listing_names_what_ran_and_what_was_left_out(self):
        with mock.patch.object(run_headless, "find_browser", return_value=None):
            _, out, _ = self.run_main([])
        self.assertIn("default set: selftest", out)
        self.assertIn("opt-in suites left out:", out)

    def test_browser_that_exits_at_once_is_reported_without_waiting(self):
        # The interpreter as a stand-in: it rejects --headless=new and exits with code 2.
        with mock.patch.object(run_headless, "find_browser", return_value=sys.executable):
            import time

            started = time.monotonic()
            code, out, _ = self.run_main(["selftest", "--timeout", "30"])
            elapsed = time.monotonic() - started
        self.assertEqual(code, 1)
        self.assertIn("browser exited before reporting", out)
        self.assertLess(elapsed, 15)

    def test_suite_url_carries_the_query_and_the_token(self):
        suite = run_headless.Suite("selftest.html")
        url = run_headless.suite_url(1234, suite, "fail=1", "abc")
        self.assertEqual(url, "http://127.0.0.1:1234/tests/browser/selftest.html?fail=1&run=abc")
        self.assertEqual(
            run_headless.suite_url(1234, suite, "", "abc"),
            "http://127.0.0.1:1234/tests/browser/selftest.html?run=abc",
        )

    def test_suite_table_has_limits_and_a_default_flag(self):
        for name, suite in run_headless.SUITES.items():
            self.assertTrue(suite.page.endswith(".html"), name)
            self.assertGreater(suite.limit, 0, name)
            self.assertIn("/tests/browser/" + suite.page.split("?")[0], serve.HARNESS_FILES, name)


if __name__ == "__main__":
    unittest.main()
