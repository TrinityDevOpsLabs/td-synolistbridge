# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from synolistbridge.providers import KeepSource, AnyListDestination

try:
    import gkeepapi
    import pyanylist
except ImportError:
    gkeepapi = None


@unittest.skipIf(gkeepapi is None, "Install requirements.txt to run provider contract tests")
class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        secret = Path(self.temp.name) / "secret"
        secret.write_text("test-secret")
        self.config = SimpleNamespace(google_email="google@example.com", anylist_email="any@example.com",
                                      google_token_file=str(secret), anylist_password_file=str(secret),
                                      keep_list_id="", anylist_list_id="destination")

    def test_keep_authenticate_returns_none_and_items_use_real_ids(self):
        keep = gkeepapi.Keep()
        note = keep.createList("Shopping", [("milk", False), ("bread", True)])
        self.config.keep_list_id = note.id
        with patch.object(keep, "authenticate", return_value=None) as authenticate:
            with patch.object(keep, "sync") as sync:
                with patch("gkeepapi.Keep", return_value=keep):
                    source = KeepSource(self.config)
                    self.assertIn((note.id, "Shopping"), source.lists())
                    items = source.items()
                    milk = next(item for item in items if item.text == "milk")
                    self.assertFalse(milk.checked)
                    source.complete(milk.id)
                    self.assertTrue(next(item for item in note.items if item.id == milk.id).checked)
                    authenticate.assert_called_once_with("google@example.com", "test-secret")
                    self.assertEqual(sync.call_count, 2)

    def test_keep_deletes_only_selected_item(self):
        keep = gkeepapi.Keep()
        note = keep.createList("Shopping", [("milk", False), ("bread", False)])
        self.config.keep_list_id = note.id
        with patch.dict(os.environ, {"BRIDGE_DELETE_KEEP_ITEMS": "true"}), \
             patch.object(keep, "authenticate"), patch.object(keep, "sync") as sync, \
             patch("gkeepapi.Keep", return_value=keep):
            source = KeepSource(self.config)
            milk = next(item for item in note.items if item.text == "milk")
            source.complete(milk.id)
            self.assertTrue(milk.deleted)
            self.assertFalse(note.deleted)
            self.assertEqual([item.text for item in source.items()], ["bread"])
            self.assertEqual(sync.call_count, 2)

    def test_keep_rejects_plain_notes(self):
        keep = gkeepapi.Keep()
        self.config.keep_list_id = keep.createNote("Not a checklist", "milk").id
        with patch.object(keep, "authenticate"), patch.object(keep, "sync"), patch("gkeepapi.Keep", return_value=keep):
            source = KeepSource(self.config)
            with self.assertRaises(ValueError):
                source.items()

    def test_anylist_contract_and_stable_destination_id(self):
        from unittest.mock import Mock
        # Verify method names against the installed native extension.
        client = Mock(spec=pyanylist.AnyListClient)
        client.add_item.return_value = SimpleNamespace(id="created-item")
        client.get_lists.return_value = [SimpleNamespace(id="destination", name="Shopping")]
        factory = SimpleNamespace(login=Mock(return_value=client))
        with patch.object(pyanylist, "AnyListClient", factory):
            destination = AnyListDestination(self.config)
            destination.validate()
            self.assertEqual(destination.lists(), [("destination", "Shopping")])
            self.assertEqual(destination.add("milk"), "created-item")
            client.add_item.assert_called_once_with("destination", "milk")
            client.get_list_by_id.assert_called_once_with("destination")


if __name__ == "__main__":
    unittest.main()

class CompletionTests(unittest.TestCase):
    def test_completion_deletes_and_propagates_sync_failure(self):
        from unittest.mock import Mock
        source = KeepSource.__new__(KeepSource)
        source.delete_items = True
        item = Mock(id="item", deleted=False)
        source.note = Mock(return_value=SimpleNamespace(items=[item]))
        source.keep = Mock()
        source.keep.sync.side_effect = RuntimeError("offline")
        with self.assertRaises(RuntimeError):
            source.complete("item")
        item.delete.assert_called_once_with()
        source.keep.sync.assert_called_once_with()

    def test_invalid_delete_setting_rejected_before_authentication(self):
        with patch.dict(os.environ, {"BRIDGE_DELETE_KEEP_ITEMS": "typo"}):
            with self.assertRaises(ValueError):
                KeepSource(SimpleNamespace())
