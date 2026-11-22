"""Run browser suites headless, in real time, and collect each page's report.

    python -m tests.browser.run_headless [suite[?query] ...] [--timeout SECONDS]

The runner starts the harness server in-process on a free loopback port. For
each suite it starts an installed Chromium-family browser with ``--headless=new``
and a throwaway profile, and waits on the wall clock for the page to POST its
report to ``/tests/browser/report``. It never uses ``--dump-dom`` or
``--virtual-time-budget``: pages, timers and workers run in real time.

A suite name may carry a query string, for example ``selftest?fail=1``; it is
passed to the page.

Exit codes: 0 every check passed; 1 a check failed, no report arrived in time or
the browser ended before it reported; 2 usage error; 3 no browser found (skipped).

``LFBE_BROWSER`` names the browser program to use before the usual locations.
"""

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from .serve import PREFIX, create_harness_server

DEFAULT_LIMIT = 120
MODE = "real time, report route"


class Suite:
    def __init__(self, page, limit=DEFAULT_LIMIT, default=True):
        self.page = page
        self.limit = limit
        self.default = default


# One table of suites. A later ticket adds its page here; ``default`` says whether a
# bare ``run_headless`` runs it. Opt-in suites run only when named.
SUITES = {
    "selftest": Suite("selftest.html", limit=60, default=True),
}


# ---- browser discovery -------------------------------------------------------------
def _candidates():
    env = os.environ.get("LFBE_BROWSER")
    if env:
        yield env
    if sys.platform == "win32":
        roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        for root in filter(None, roots):
            yield os.path.join(root, "Google", "Chrome", "Application", "chrome.exe")
            yield os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe")
            yield os.path.join(root, "Chromium", "Application", "chrome.exe")
    elif sys.platform == "darwin":
        yield "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        yield "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        yield "/Applications/Chromium.app/Contents/MacOS/Chromium"
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                     "microsoft-edge", "microsoft-edge-stable"):
            found = shutil.which(name)
            if found:
                yield found


def find_browser():
    for path in _candidates():
        if path and os.path.isfile(path):
            return path
    named = os.environ.get("LFBE_BROWSER")
    return shutil.which(named) if named else None


# ---- process handling --------------------------------------------------------------
def end_process_tree(proc):
    """End the browser and everything it started. Safe to call on an ended process."""
    if sys.platform == "win32":
        # /T ends the root and every process it started, as long as the root still exists.
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if proc.poll() is None:
                proc.kill()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def remove_dir(path):
    for _ in range(20):
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.exists(path):
            return True
        time.sleep(0.25)
    return not os.path.exists(path)


# ---- one suite ---------------------------------------------------------------------
def split_suite(arg):
    name, _, query = arg.partition("?")
    return name, query


def suite_url(port, suite, query, token):
    page, _, own_query = suite.page.partition("?")
    parts = [q for q in (own_query, query) if q] + [f"run={token}"]
    return f"http://127.0.0.1:{port}{PREFIX}{page}?{'&'.join(parts)}"


def browser_version(report):
    ua = str((report.get("env") or {}).get("userAgent", ""))
    # Edge's user agent also contains Chrome/<n>, so look for its own token first.
    match = re.search(r"(Edg)/([0-9.]+)", ua) or re.search(r"(HeadlessChrome|Chrome)/([0-9.]+)", ua)
    if not match:
        return "unknown version"
    return ("Edge" if match.group(1) == "Edg" else "Chrome/Chromium") + " " + match.group(2)


def run_suite(server, browser, label, suite, query, limit):
    """Run one suite. Returns 0 (passed) or 1 (failed, timed out or browser ended)."""
    token = secrets.token_hex(8)
    server.reports.expect(token)
    url = suite_url(server.port, suite, query, token)
    profile = tempfile.mkdtemp(prefix="lfbe-profile-")
    log = tempfile.TemporaryFile()
    args = [
        browser, "--headless=new", f"--user-data-dir={profile}", "--no-first-run",
        "--no-default-browser-check", url,
    ]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": log}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    print(f"== {label}: {url.rsplit('run=', 1)[0].rstrip('?&')}")
    started = time.monotonic()
    proc = None
    report = None
    reason = None
    try:
        try:
            proc = subprocess.Popen(args, **kwargs)
        except OSError as e:
            print(f"FAIL: cannot start the browser: {e}")
            return 1
        report = server.reports.wait(token, limit, stop=lambda: proc.poll() is not None)
        if report is None:
            report = server.reports.wait(token, 0)
        if report is None:
            if proc.poll() is not None:
                reason = f"browser exited before reporting (exit code {proc.returncode})"
                log.seek(0)
                tail = log.read()[-600:].decode("utf-8", "replace").strip().splitlines()[-3:]
                for line in tail:
                    print(f"  browser: {line}")
            else:
                reason = f"timed out: no report after {limit:g} s"
    finally:
        if proc is not None:
            end_process_tree(proc)
        log.close()
        gone = remove_dir(profile)
    if not gone:
        print(f"warning: could not remove the profile directory {profile}")
    if report is None:
        print(f"FAIL: {reason}")
        return 1
    print(f"browser: {browser_version(report)}; mode: {MODE}; {time.monotonic() - started:.1f} s")
    failed = 0
    for entry in report.get("checks") or []:
        ok = bool(entry.get("ok"))
        failed += 0 if ok else 1
        detail = entry.get("detail")
        tag = " [realtime]" if entry.get("realtime") else ""
        text = f"{'PASS' if ok else 'FAIL'}  {entry.get('name')}{tag}"
        if detail not in (None, ""):
            text += f" -- {detail}"
        print(text)
    for entry in report.get("measurements") or []:
        note = "" if entry.get("asserted", True) else " (not asserted)"
        print(f"MEASURE  {entry.get('name')}: {entry.get('value')} {entry.get('unit', '')}{note}".rstrip())
    total = len(report.get("checks") or [])
    print(f"{label}: {report.get('passed')} passed, {report.get('failed')} failed of {total} checks")
    return 0 if failed == 0 and not report.get("failed") else 1


# ---- command line ------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tests.browser.run_headless")
    parser.add_argument("suite", nargs="*", help="suite names; none means the default set")
    parser.add_argument("--timeout", type=float, help="seconds to wait for each report (overrides the suite limit)")
    args = parser.parse_args(argv)

    known = ", ".join(sorted(SUITES))
    selected = []
    for arg in args.suite:
        name, query = split_suite(arg)
        if name not in SUITES:
            print(f"unknown suite {name!r}; known suites: {known}", file=sys.stderr)
            return 2
        selected.append((arg, name, query))
    if args.timeout is not None and args.timeout <= 0:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    if not selected:
        selected = [(n, n, "") for n, s in SUITES.items() if s.default]
        left_out = [n for n, s in SUITES.items() if not s.default]
        print("default set: " + (", ".join(n for n, _, _ in selected) or "(none)"))
        print("opt-in suites left out: " + (", ".join(left_out) or "(none registered)"))

    browser = find_browser()
    if browser is None:
        print("skipped: no browser found (set LFBE_BROWSER to a Chrome, Edge or Chromium program)")
        return 3
    print(f"browser program: {browser}")

    with tempfile.TemporaryDirectory(prefix="lfbe-harness-", ignore_cleanup_errors=True) as data_dir:
        server = create_harness_server(data_dir, 0)
        server.start()
        try:
            worst = 0
            for label, name, query in selected:
                suite = SUITES[name]
                limit = args.timeout if args.timeout is not None else suite.limit
                worst = max(worst, run_suite(server, browser, label, suite, query, limit))
        finally:
            server.stop()
    return worst


if __name__ == "__main__":
    sys.exit(main())
