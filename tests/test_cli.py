import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args, timeout=30):
    return subprocess.run(
        [sys.executable, "-m", "line_editor", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def assert_rejected(self, data_dir):
        r = run_cli("--data-dir", data_dir, "--port", "0")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_empty_data_dir(self):
        self.assert_rejected("")

    def test_file_data_dir(self):
        path = os.path.join(self.dir, "afile")
        with open(path, "w") as f:
            f.write("x")
        self.assert_rejected(path)

    def test_newer_schema_rejected(self):
        import sqlite3

        conn = sqlite3.connect(os.path.join(self.dir, "line_editor.sqlite3"))
        conn.execute("PRAGMA user_version=2")
        conn.close()
        self.assert_rejected(self.dir)

    def test_missing_required_args(self):
        self.assertEqual(run_cli("--port", "0").returncode, 2)
        self.assertEqual(run_cli("--data-dir", self.dir).returncode, 2)

    def test_serves_and_prints_url(self):
        proc = subprocess.Popen(
            [sys.executable, "-m", "line_editor", "--data-dir",
             os.path.join(self.dir, "new"), "--port", "0"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        watchdog = threading.Timer(30, proc.kill)
        watchdog.start()
        try:
            line = proc.stdout.readline().strip()
            m = re.fullmatch(r"Serving on http://127\.0\.0\.1:(\d+)/", line)
            self.assertIsNotNone(m, line)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{m.group(1)}/api/v1/health", timeout=10
            ) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()
            watchdog.cancel()


if __name__ == "__main__":
    unittest.main()
