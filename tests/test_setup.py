# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import io
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch

from synolistbridge.config import Config
from synolistbridge.setup import Wizard, handler_for


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
        page = self.wizard.page()
        self.assertNotIn("PRIVATE-TOKEN", page)
        self.assertNotIn("PRIVATE-PASSWORD", page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

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

    def request(self, path, origin=None, body=b"x=y", content_type="application/x-www-form-urlencoded"):
        handler_type = handler_for(self.wizard)
        handler = handler_type.__new__(handler_type)
        handler.path = path
        handler.headers = Message()
        handler.headers["Host"] = "nas.local:8765"
        handler.headers["Content-Type"] = content_type
        handler.headers["Content-Length"] = str(len(body))
        if origin:
            handler.headers["Origin"] = origin
        handler.rfile = io.BytesIO(body)
        handler.respond = Mock()
        handler.do_POST()
        return handler.respond.call_args.args

    def test_wrong_token_and_foreign_origin_are_rejected(self):
        self.assertEqual(self.request("/wrong-token/discover")[0], 404)
        self.assertEqual(self.request(self.wizard.base + "discover", "http://evil.example")[0], 403)

    def test_wrong_encoding_and_large_body_are_rejected(self):
        self.assertEqual(self.request(self.wizard.base + "discover", content_type="application/json")[0], 415)
        self.assertEqual(self.request(self.wizard.base + "discover", body=b"x" * 16385)[0], 413)

    def test_provider_errors_are_not_reflected(self):
        with patch.object(self.wizard, "discover", side_effect=RuntimeError("PRIVATE-TOKEN")):
            status, body = self.request(self.wizard.base + "discover", "http://nas.local:8765")
        self.assertEqual(status, 400)
        self.assertNotIn("PRIVATE-TOKEN", body)

    def test_saved_config_cannot_be_overwritten(self):
        self.discover()
        self.wizard.config_path.write_text("original")
        with self.assertRaises(ValueError):
            self.wizard.save({"keep": "keep-id", "anylist": "any-id", "confirm": "yes"})
        self.assertEqual(self.wizard.config_path.read_text(), "original")
