# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from synolistbridge.config import Config
from synolistbridge.setup import Wizard, run_setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name)
        self.wizard = Wizard(self.data / "config.json", self.data)
        self.fields = {"google_email": "google@example.com", "anylist_email": "any@example.com",
                       "google_token": "PRIVATE-TOKEN", "anylist_password": "PRIVATE-PASSWORD"}

    def discover(self):
        with patch("synolistbridge.setup.KeepSource") as keep, patch("synolistbridge.setup.AnyListDestination") as anylist:
            keep.return_value.lists.return_value = [("keep-id", '<script>private list</script>')]
            anylist.return_value.lists.return_value = [("any-id", "Shopping")]
            self.wizard.discover(self.fields)

    def test_discovery_does_not_publish_credentials_or_config(self):
        self.discover()
        self.assertFalse(self.wizard.config_path.exists())
        self.assertFalse((self.data / "secrets").exists())

    def test_save_requires_valid_lists_and_confirmation(self):
        self.discover()
        for fields in ({"keep": "keep-id", "anylist": "any-id"},
                       {"keep": "invalid", "anylist": "any-id", "confirm": "yes"}):
            with self.assertRaises(ValueError):
                self.wizard.save(fields)
        self.assertFalse(self.wizard.config_path.exists())

    def test_save_persists_private_files_and_clears_draft(self):
        self.discover()
        self.wizard.save({"keep": "keep-id", "anylist": "any-id", "confirm": "yes"})
        config = Config.load(self.wizard.config_path)
        self.assertEqual(config.keep_list_id, "keep-id")
        self.assertEqual(config.anylist_list_id, "any-id")
        self.assertEqual(Path(config.google_token_file).read_text(), "PRIVATE-TOKEN")
        self.assertEqual(Path(config.anylist_password_file).read_text(), "PRIVATE-PASSWORD")
        for path in (self.wizard.config_path, Path(config.google_token_file), Path(config.anylist_password_file)):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertIsNone(self.wizard.draft)
        self.assertIsNone(self.wizard.lists)
        self.assertNotIn("PRIVATE", self.wizard.config_path.read_text())

    def test_failed_authentication_clears_previous_draft(self):
        self.discover()
        with patch("synolistbridge.setup.KeepSource", side_effect=RuntimeError("SECRET")):
            with self.assertRaises(RuntimeError):
                self.wizard.discover(self.fields)
        self.assertIsNone(self.wizard.draft)

    def interactive(self, answers):
        return patch("builtins.input", side_effect=answers)

    def test_interactive_setup_saves_without_transfers(self):
        with patch("synolistbridge.setup.sys.stdin.isatty", return_value=True), \
             patch("synolistbridge.setup.sys.stdout.isatty", return_value=True), \
             self.interactive(["google@example.com", "any@example.com", "bad", "2", "1", "1", "yes"]), \
             patch("synolistbridge.setup.getpass.getpass", side_effect=["PRIVATE-TOKEN", "PRIVATE-PASSWORD"]), \
             patch("synolistbridge.setup.KeepSource") as keep, \
             patch("synolistbridge.setup.AnyListDestination") as anylist, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            output.isatty = Mock(return_value=True)
            keep.return_value.lists.return_value = [("keep-id", "Groceries")]
            anylist.return_value.lists.return_value = [("any-id", "Shopping")]
            self.assertEqual(run_setup(self.wizard.config_path, self.data), 0)
            self.assertNotIn("PRIVATE", output.getvalue())
            keep.return_value.check.assert_not_called()
            anylist.return_value.add.assert_not_called()
        self.assertEqual(Config.load(self.wizard.config_path).keep_list_id, "keep-id")

    def test_noninteractive_setup_fails_before_reading_credentials(self):
        with patch("synolistbridge.setup.sys.stdin.isatty", return_value=False), \
             patch("synolistbridge.setup.getpass.getpass") as secret:
            self.assertEqual(run_setup(self.wizard.config_path, self.data), 1)
        secret.assert_not_called()
        self.assertFalse(self.wizard.config_path.exists())

    def test_cancellation_does_not_save(self):
        with patch("synolistbridge.setup.sys.stdin.isatty", return_value=True), \
             patch("synolistbridge.setup.sys.stdout.isatty", return_value=True), \
             patch("builtins.input", side_effect=EOFError):
            self.assertEqual(run_setup(self.wizard.config_path, self.data), 1)
        self.assertFalse(self.wizard.config_path.exists())

    def test_saved_config_cannot_be_overwritten(self):
        self.discover()
        self.wizard.config_path.write_text("original")
        with self.assertRaises(ValueError):
            self.wizard.save({"keep": "keep-id", "anylist": "any-id", "confirm": "yes"})
        self.assertEqual(self.wizard.config_path.read_text(), "original")
