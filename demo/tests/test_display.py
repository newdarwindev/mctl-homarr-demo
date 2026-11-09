# SPDX-License-Identifier: GPL-3.0-or-later; newdarwindev, 2026-11-01
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts/mctl-display"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


display = load("display", LAUNCHER)
fixture = load("fixture", ROOT / "demo/fixtures/serve.py")


def wait_for(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError("Timed out waiting for bounded test process")


class UrlTests(unittest.TestCase):
    def test_valid_board_urls(self):
        for value in ("https://homarr.example/boards/demo", "http://127.0.0.1:8765/boards/demo",
                      "http://[::1]:7575/boards/demo", "https://homarr.example/boards/a%20b"):
            with self.subTest(value=value):
                self.assertEqual(display.board_url(value), value)

    def test_invalid_urls_are_redacted(self):
        values = [None, "", "file:///tmp/secret", "javascript:alert(1)", "data:text/html,x",
                  "//example.com", "https://", "https://user:secret@example.com/boards/demo",
                  "https://secret@example.com", "https://example.com/?token=secret",
                  "https://example.com/#secret", "https://example.com/?", "https://example.com/#",
                  "https://example.com:0", "https://example.com:65536", "https://example.com:abc",
                  "https://[bad", "https://example.com/a\nb", "https://example.com/%0asecret",
                  "https://example.com/\\secret", "https://%65xample.com", " https://example.com",
                  "https://example.com/" + "a" * 4096]
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(display.DisplayError) as caught:
                    display.board_url(value)
                self.assertNotIn("secret", str(caught.exception))

    def test_arguments_are_never_a_shell_command(self):
        url = "https://homarr.example/boards/$(touch${IFS}/tmp/injected);echo"
        self.assertEqual(display.board_url(url), url)
        args = display.browser_command("/browser path/chromium", url, "/tmp/a profile")
        self.assertEqual(args[-1], url)
        self.assertIn("--user-data-dir=/tmp/a profile", args)
        self.assertIn("--kiosk", args)
        self.assertNotIn("--no-sandbox", args)
        self.assertFalse(any("disable-web-security" in arg or "ignore-certificate" in arg for arg in args))

    def test_missing_browser(self):
        with patch.object(display.shutil, "which", return_value=None):
            with self.assertRaisesRegex(display.DisplayError, "not found"):
                display.browser_path(None)


FAKE_BROWSER = '''#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time
args = sys.argv[1:]
descendant = None
if os.environ.get("TEST_DESCENDANT"):
    descendant = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(120)"])
with open(os.environ["TEST_RECORD"], "w") as f:
    json.dump({"args":args,"pid":os.getpid(),"descendant":descendant.pid if descendant else None}, f)
if os.environ.get("TEST_WAIT"):
    while not os.path.exists(os.environ["TEST_CLOSE"]):
        time.sleep(0.02)
sys.exit(int(os.environ.get("TEST_EXIT", "0")))
'''


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.browser = self.path / "browser with spaces"
        self.browser.write_text(FAKE_BROWSER)
        self.browser.chmod(0o755)
        self.record = self.path / "record.json"
        self.env = dict(os.environ, TEST_RECORD=str(self.record), TEST_CLOSE=str(self.path / "close"))

    def launch(self, extra_env=None, url="http://127.0.0.1:8765/boards/demo"):
        process = subprocess.Popen([sys.executable, str(LAUNCHER), "homarr", "--url", url,
                                    "--browser", str(self.browser)],
                                   env=dict(self.env, **(extra_env or {})), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=8)
        self.addCleanup(cleanup)
        return process

    def record_ready(self):
        def record():
            try:
                return json.loads(self.record.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                return None
        return wait_for(record)

    def assert_profile_removed(self, record):
        profile = next(arg.split("=", 1)[1] for arg in record["args"] if arg.startswith("--user-data-dir="))
        self.assertFalse(Path(profile).exists())

    def test_normal_close_and_profile_cleanup(self):
        process = self.launch()
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertIn("separate", stdout)
        self.assertNotIn("http://", stdout + stderr)
        self.assert_profile_removed(self.record_ready())

    def test_waits_in_foreground_until_browser_closes(self):
        process = self.launch({"TEST_WAIT": "1"})
        record = self.record_ready()
        self.assertIsNone(process.poll())
        self.assertTrue(Path(next(a.split("=",1)[1] for a in record["args"] if a.startswith("--user-data-dir="))).is_dir())
        (self.path / "close").touch()
        process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0)
        self.assert_profile_removed(record)

    def test_sigint_stops_browser(self):
        self.check_signal(signal.SIGINT)

    def test_sigterm_stops_browser(self):
        self.check_signal(signal.SIGTERM)

    def check_signal(self, sig):
        process = self.launch({"TEST_WAIT": "1", "TEST_DESCENDANT": "1"})
        record = self.record_ready()
        process.send_signal(sig)
        process.communicate(timeout=8)
        self.assertEqual(process.returncode, 128 + sig)
        self.assert_profile_removed(record)
        for pid in (record["pid"], record["descendant"]):
            stat = Path(f"/proc/{pid}/stat")
            if stat.exists():
                self.assertEqual(stat.read_text().split()[2], "Z", "browser descendant still running")

    def test_failure_is_generic_and_profile_is_removed(self):
        process = self.launch({"TEST_EXIT": "7"})
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 2)
        self.assertIn("unsuccessfully", stderr)
        self.assertNotIn("http://", stdout + stderr)
        self.assert_profile_removed(self.record_ready())

    def test_missing_executable_cli(self):
        result = subprocess.run([sys.executable, str(LAUNCHER), "homarr", "--url", "http://localhost/boards/demo",
                                 "--browser", "/missing/chromium"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)

    def test_non_executable_is_rejected(self):
        self.browser.chmod(0o644)
        result = self.launch()
        _, stderr = result.communicate(timeout=8)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", stderr)

    def test_rejected_password_url_is_not_logged(self):
        result = self.launch(url="https://person:password-secret@homarr.example/boards/demo")
        stdout, stderr = result.communicate(timeout=8)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("password-secret", stdout + stderr)
        self.assertFalse(self.record.exists())

    def test_parser_errors_do_not_log_rejected_values(self):
        result = subprocess.run([sys.executable, str(LAUNCHER), "homarr", "--bad=password-secret"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("password-secret", result.stderr)

    def test_environment_url(self):
        result = subprocess.run([sys.executable, str(LAUNCHER), "homarr", "--browser", str(self.browser)],
                                env=dict(self.env, HOMARR_BOARD_URL="https://homarr.example/boards/demo"),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record_ready()["args"][-1], "https://homarr.example/boards/demo")

    def test_injection_payload_is_single_argument(self):
        marker = self.path / "injected"
        url = f"https://homarr.example/boards/$(touch${{IFS}}{marker});echo"
        process = self.launch(url=url)
        process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(self.record_ready()["args"][-1], url)
        self.assertFalse(marker.exists())

    def test_native_flags_and_exit_code_are_preserved(self):
        result = subprocess.run([sys.executable, str(LAUNCHER), "native", "--binary", str(self.browser),
                                 "--", "--offline", "--fullscreen"], env=dict(self.env, TEST_EXIT="17"),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 17)
        self.assertEqual(self.record_ready()["args"], ["--offline", "--fullscreen"])


class FixtureTests(unittest.TestCase):
    def test_synthetic_board_route_and_frame_headers(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), fixture.BoardHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/boards/demo") as response:
                    self.assertIn(b"SYNTHETIC DEMO", response.read())
                    self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                    self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            finally:
                server.shutdown()
                thread.join()


class RealBrowserTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("MCTL_REAL_BROWSER") == "1",
                         "UNRUN: Docker denies Chromium sandbox namespaces here; opt in with MCTL_REAL_BROWSER=1 on a supported runner.")
    def test_chromium_kiosk_displays_synthetic_board_fullscreen_and_stops(self):
        self.assertTrue(os.environ.get("DISPLAY"), "Run in the committed Docker runner under Xvfb")
        wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with ThreadingHTTPServer(("127.0.0.1", 0), fixture.BoardHandler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            process = subprocess.Popen([sys.executable, str(LAUNCHER), "homarr", "--browser", "/usr/bin/chromium",
                                        "--url", f"http://127.0.0.1:{server.server_port}/boards/demo"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                def loaded():
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        raise AssertionError(f"Real browser failed: {stdout} {stderr}")
                    tree = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
                    return tree if '"Synthetic Homarr board fixture' in tree else None
                tree = wait_for(loaded, timeout=15)
                line = next(line for line in tree.splitlines() if '"Synthetic Homarr board fixture' in line)
                self.assertRegex(line, r"1280x720\+0\+0")
                self.assertIsNone(process.poll())
                process.terminate()
                process.communicate(timeout=8)
                self.assertEqual(process.returncode, 143)
                remaining = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
                self.assertNotIn('"Synthetic Homarr board fixture', remaining)
            finally:
                if process.poll() is None:
                    process.terminate()
                process.communicate(timeout=8)
                server.shutdown()
                thread.join()
                wm.terminate()
                wm.wait(timeout=5)
