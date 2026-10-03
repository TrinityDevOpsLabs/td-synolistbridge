# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from synolistbridge.__main__ import main
from synolistbridge.config import Config, read_secret


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"
        self.data = {"google_email": "google@example.com", "anylist_email": "any@example.com",
                     "keep_list_id": "keep", "anylist_list_id": "any"}
        self.path.write_text(json.dumps(self.data))

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(["--config", str(self.path), "--data", self.temp.name, *args])

    def test_invalid_poll_intervals_rejected(self):
        for interval in (True, "60", 0, 29, 86401):
            self.path.write_text(json.dumps(dict(self.data, poll_seconds=interval)))
            with self.assertRaises(ValueError):
                Config.load(self.path)

    def test_no_credentials_needed_for_check(self):
        self.assertEqual(self.command("check"), 0)

    def test_start_with_saved_config_skips_setup(self):
        event = unittest.mock.Mock()
        event.is_set.side_effect = [False, True]
        with patch("synolistbridge.__main__.threading.Event", return_value=event), \
             patch("synolistbridge.setup.run_setup") as wizard, \
             patch("synolistbridge.providers.KeepSource"), \
             patch("synolistbridge.providers.AnyListDestination"), \
             patch("synolistbridge.__main__.Bridge") as bridge:
            bridge.return_value.poll.return_value = 0
            self.assertEqual(self.command("start"), 0)
        wizard.assert_not_called()
        bridge.return_value.poll.assert_called_once()

    def test_start_waits_without_lock_and_stops_cleanly(self):
        self.path.unlink()
        event = unittest.mock.Mock()
        event.wait.return_value = True
        with patch("synolistbridge.__main__.threading.Event", return_value=event), \
             patch("synolistbridge.__main__.exclusive_lock") as lock, \
             self.assertLogs("synolistbridge", level="INFO") as logs:
            self.assertEqual(self.command("start"), 0)
        lock.assert_not_called()
        self.assertIn("synolistbridge setup", " ".join(logs.output))

    def test_start_runs_after_setup_saves_config(self):
        saved = self.path.read_text()
        self.path.unlink()
        event = unittest.mock.Mock()
        def wait(seconds):
            if seconds == 2:
                self.path.write_text(saved)
            return False
        event.wait.side_effect = wait
        event.is_set.side_effect = [False, True]
        with patch("synolistbridge.__main__.threading.Event", return_value=event), \
             patch("synolistbridge.providers.KeepSource"), \
             patch("synolistbridge.providers.AnyListDestination"), \
             patch("synolistbridge.__main__.Bridge") as bridge:
            bridge.return_value.poll.return_value = 0
            self.assertEqual(self.command("start"), 0)
        bridge.return_value.poll.assert_called_once()

    def test_setup_returns_without_starting_bridge(self):
        self.path.unlink()
        with patch("synolistbridge.setup.run_setup", return_value=0) as setup, \
             patch("synolistbridge.__main__.Bridge") as bridge:
            self.assertEqual(self.command("setup"), 0)
        setup.assert_called_once_with(str(self.path), self.temp.name)
        bridge.assert_not_called()

    def test_invalid_config_fails_safely(self):
        self.path.write_text('{"secret": "do-not-log-this"}')
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main(["--config", str(self.path), "check"])
        self.assertEqual(result, 1)
        self.assertNotIn("do-not-log-this", stderr.getvalue())

    def test_health_rejects_missing_stale_and_review_state(self):
        heartbeat = Path(self.temp.name) / "health.json"
        self.assertEqual(self.command("health"), 1)
        for timestamp, reviews, result in ((0, 0, 1), (time.time(), 1, 1), (time.time(), 0, 0)):
            heartbeat.write_text(json.dumps({"success": timestamp, "review": reviews}))
            self.assertEqual(self.command("health"), result)

    def test_secret_newlines_but_not_password_spaces_are_trimmed(self):
        secret = Path(self.temp.name) / "secret"
        secret.write_text(" password with spaces \n")
        self.assertEqual(read_secret(secret), " password with spaces ")
        secret.write_text("first\nsecond")
        with self.assertRaises(ValueError):
            read_secret(secret)

    def test_provider_error_does_not_leak_secret(self):
        with patch("synolistbridge.providers.KeepSource", side_effect=RuntimeError("SECRET-TOKEN")):
            with self.assertLogs("synolistbridge", level="ERROR") as logs:
                self.assertEqual(self.command("once"), 1)
        self.assertNotIn("SECRET-TOKEN", " ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
