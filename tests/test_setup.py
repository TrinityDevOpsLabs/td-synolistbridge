# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from synolistbridge.config import Config
from synolistbridge.setup import Wizard, run_setup, exchange_google_cookie, masked_input


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
        self.assertEqual(config.routes()[0].keep_list_id, "keep-id")
        self.assertEqual(config.routes()[0].anylist_list_id, "any-id")
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
             patch("synolistbridge.setup.masked_input", side_effect=["PRIVATE-TOKEN", "PRIVATE-PASSWORD"]), \
             patch("synolistbridge.setup.exchange_google_cookie", return_value="MASTER-TOKEN") as exchange, \
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
        exchange.assert_called_once_with("google@example.com", "PRIVATE-TOKEN")
        config = Config.load(self.wizard.config_path)
        self.assertEqual(config.routes()[0].keep_list_id, "keep-id")
        self.assertEqual(Path(config.google_token_file).read_text(), "MASTER-TOKEN")

    def test_multiple_pairs_are_reviewed_before_save(self):
        with patch("synolistbridge.setup.sys.stdin.isatty", return_value=True), \
             patch("synolistbridge.setup.masked_input", side_effect=["COOKIE", "PASSWORD"]), \
             patch("synolistbridge.setup.exchange_google_cookie", return_value="TOKEN"), \
             patch("builtins.input", side_effect=["google", "anylist", "1", "1", "yes", "1", "2", "yes"]), \
             patch("synolistbridge.setup.KeepSource") as keep, \
             patch("synolistbridge.setup.AnyListDestination") as anylist, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            output.isatty = Mock(return_value=True)
            keep.return_value.lists.return_value = [("groceries", "Groceries"), ("hardware", "Hardware")]
            anylist.return_value.lists.return_value = [("food", "Food"), ("tools", "Tools")]
            self.assertEqual(run_setup(self.wizard.config_path, self.data), 0)
            self.assertIn("Groceries → Food", output.getvalue())
            self.assertIn("Hardware → Tools", output.getvalue())
            self.assertIn("EVERY selected Keep checklist", output.getvalue())
            anylist.return_value.add.assert_not_called()
        routes = Config.load(self.wizard.config_path).routes()
        self.assertEqual([(r.keep_list_id, r.anylist_list_id) for r in routes],
                         [("groceries", "food"), ("hardware", "tools")])

    def test_noninteractive_setup_fails_before_reading_credentials(self):
        with patch("synolistbridge.setup.sys.stdin.isatty", return_value=False), \
             patch("synolistbridge.setup.masked_input") as secret:
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

class CookieExchangeTests(unittest.TestCase):
    def test_exchange_uses_cookie_and_generated_android_id(self):
        api = Mock()
        api.exchange_token.return_value = {"Token": "master-secret"}
        with patch.dict("sys.modules", {"gpsoauth": api}), \
             patch("synolistbridge.setup.secrets.token_hex", return_value="0123456789abcdef"):
            self.assertEqual(exchange_google_cookie("user@example.com", "cookie-secret"), "master-secret")
        api.exchange_token.assert_called_once_with("user@example.com", "cookie-secret", "0123456789abcdef")

    def test_failed_exchange_does_not_expose_provider_response(self):
        api = Mock()
        for response in ({"Error": "PRIVATE-COOKIE"}, {"Token": ""}, {"Token": "a\nb"}):
            api.exchange_token.return_value = response
            with patch.dict("sys.modules", {"gpsoauth": api}):
                with self.assertRaises(ValueError) as error:
                    exchange_google_cookie("user@example.com", "cookie-secret")
            self.assertNotIn("PRIVATE", str(error.exception))

class MaskedInputTests(unittest.TestCase):
    def read_secret(self, text):
        stream = io.StringIO(text)
        stream.fileno = Mock(return_value=7)
        settings = [0, 0, 0, 0, 0, 0, [0] * 32]
        with patch("synolistbridge.setup.sys.stdin", stream), \
             patch("synolistbridge.setup.sys.stdout", new_callable=io.StringIO) as output, \
             patch("synolistbridge.setup.termios.tcgetattr", side_effect=[settings, [*settings[:6], list(settings[6])]]), \
             patch("synolistbridge.setup.termios.tcsetattr") as restore:
            try:
                result = masked_input("Secret: ")
            finally:
                self.assertEqual(restore.call_count, 2)
            return result, output.getvalue()

    def test_masked_paste_and_backspace(self):
        secret, output = self.read_secret("abc\x7fdé\n")
        self.assertEqual(secret, "abdé")
        self.assertNotIn("abc", output)
        self.assertIn("***", output)

    def test_clear_field(self):
        secret, _ = self.read_secret("abc\x15xyz\n")
        self.assertEqual(secret, "xyz")

    def test_cancel_restores_terminal(self):
        for text, error in (("abc\x03", KeyboardInterrupt), ("abc\x04", EOFError)):
            with self.assertRaises(error):
                self.read_secret(text)
