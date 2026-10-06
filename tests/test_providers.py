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
        client.get_list_by_id.return_value = SimpleNamespace(items=[])
        client.get_favourites.return_value = []
        client.get_lists.return_value = [SimpleNamespace(id="destination", name="Shopping")]
        factory = SimpleNamespace(login=Mock(return_value=client))
        with patch.object(pyanylist, "AnyListClient", factory), \
             patch("synolistbridge.anylist_categories.CategoryRules") as rules:
            rules.return_value.matches = {}
            rules.return_value.builtin_matches = {}
            rules.return_value.category_system_ids = {}
            rules.return_value.add.return_value = "created-item"
            destination = AnyListDestination(self.config)
            destination.validate()
            self.assertEqual(destination.lists(), [("destination", "Shopping")])
            self.assertEqual(destination.add("milk"), "created-item")
            rules.return_value.add.assert_called_once_with("milk")
            client.add_item.assert_not_called()
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


class CategorizationTests(unittest.TestCase):
    def destination(self, items=(), favourites=()):
        from unittest.mock import Mock
        destination = AnyListDestination.__new__(AnyListDestination)
        destination.list_id = "destination"
        destination.categories = {}
        destination.category_matching = True
        destination.state = None
        destination.refresh_seconds = 604800
        destination.next_refresh = 0
        destination.cache_loaded = False
        destination.category_rules = Mock(matches={}, builtin_matches={}, category_system_ids={})
        destination.client = Mock()
        destination.client.get_list_by_id.return_value = SimpleNamespace(items=items)
        destination.client.get_favourites.return_value = favourites
        destination.category_rules.add.side_effect = lambda text, assignments=None, category=None: "categorized" if category else "plain"
        destination.client.add_item_with_details.return_value = SimpleNamespace(id="categorized")
        return destination

    def test_selected_list_overrides_favourite_and_includes_checked_items(self):
        destination = self.destination(
            items=[SimpleNamespace(name="Milk", category="Custom Dairy", is_checked=True)],
            favourites=[SimpleNamespace(name="milk", category="Dairy")],
        )
        destination.validate()
        self.assertEqual(destination.add("  MILK  "), "categorized")
        destination.category_rules.add.assert_called_once_with(
            "  MILK  ", category="Custom Dairy")
        destination.client.add_item.assert_not_called()

    def test_favourites_match_case_and_whitespace(self):
        destination = self.destination(favourites=[
            SimpleNamespace(name="Olive Oil", category="Pantry")])
        destination.validate()
        self.assertEqual(destination.add("olive   oil"), "categorized")
        destination.category_rules.add.assert_called_once_with(
            "olive   oil", category="Pantry")

    def test_unknown_names_are_added_without_guessing(self):
        destination = self.destination(items=[SimpleNamespace(name="milk", category=None)])
        destination.validate()
        self.assertEqual(destination.add("unknown"), "plain")
        destination.category_rules.add.assert_called_once_with("unknown")
        destination.client.add_item.assert_not_called()
        destination.client.add_item_with_details.assert_not_called()

    def test_category_preferences_refresh_each_poll(self):
        destination = self.destination(items=[SimpleNamespace(name="milk", category="Dairy")])
        destination.validate()
        destination.client.get_list_by_id.return_value = SimpleNamespace(items=[])
        destination.next_refresh = 0
        destination.validate()
        self.assertEqual(destination.add("milk"), "plain")

    def test_disabled_matching_skips_favourites_and_clears_categories(self):
        destination = self.destination(items=[SimpleNamespace(name="milk", category="Dairy")])
        destination.categories = {"milk": "Dairy"}
        destination.category_matching = False
        destination.validate()
        self.assertEqual(destination.add("milk"), "plain")
        destination.client.get_favourites.assert_not_called()
        destination.client.get_list_by_id.assert_called_once_with("destination")
        destination.client.add_item_with_details.assert_not_called()

    def test_invalid_matching_setting_rejected_before_login(self):
        with patch.dict(os.environ, {"BRIDGE_CATEGORY_MATCHING": "typo"}):
            with self.assertRaisesRegex(ValueError, "BRIDGE_CATEGORY_MATCHING"):
                AnyListDestination(SimpleNamespace())

    def test_saved_rule_used_after_item_deleted(self):
        destination = self.destination()
        destination.category_rules.matches = {"creama": {"group": ("dairy-id", "Dairy")}}
        destination.category_rules.add.side_effect = None
        destination.category_rules.add.return_value = "saved-rule-item"
        destination.validate()
        self.assertEqual(destination.add("Creama"), "saved-rule-item")
        destination.category_rules.add.assert_called_once_with(
            "Creama", {"group": ("dairy-id", "Dairy")})
        destination.client.add_item.assert_not_called()

    def test_fresh_cache_skips_category_requests(self):
        destination = self.destination()
        destination.next_refresh = 200
        with patch('synolistbridge.providers.time.time', return_value=100):
            destination.validate()
        destination.client.get_favourites.assert_not_called()
        destination.category_rules.refresh.assert_not_called()

    def test_refresh_failure_keeps_cache_and_delays_retry(self):
        destination = self.destination()
        destination.cache_loaded = True
        destination.categories = {'milk': 'Dairy'}
        destination.category_rules.refresh.side_effect = RuntimeError('offline')
        with patch('synolistbridge.providers.time.time', return_value=100), \
             self.assertLogs('synolistbridge', level='WARNING'):
            destination.validate()
        self.assertEqual(destination.categories, {'milk': 'Dairy'})
        self.assertEqual(destination.next_refresh, 400)
        with patch('synolistbridge.providers.time.time', return_value=101):
            destination.validate()
        self.assertEqual(destination.category_rules.refresh.call_count, 1)

    def test_first_refresh_failure_is_reported(self):
        destination = self.destination()
        destination.category_rules.refresh.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            destination.validate()

    def test_builtin_used_when_no_custom_match_exists(self):
        destination = self.destination()
        destination.category_rules.builtin_matches = {'cottage cheese': {'group': ('dairy', 'Dairy')}}
        destination.category_rules.add.side_effect = None
        destination.category_rules.add.return_value = 'builtin-item'
        self.assertEqual(destination.add('Cottage Cheese'), 'builtin-item')
        destination.category_rules.add.assert_called_once_with(
            'Cottage Cheese', {'group': ('dairy', 'Dairy')})
        destination.client.add_item.assert_not_called()

    def test_custom_saved_rule_overrides_builtin(self):
        destination = self.destination()
        destination.category_rules.matches = {'milk': {'group': ('custom', 'Custom')}}
        destination.category_rules.builtin_matches = {'milk': {'group': ('dairy', 'Dairy')}}
        destination.add('Milk')
        destination.category_rules.add.assert_called_once_with('Milk', {'group': ('custom', 'Custom')})

    def test_disabled_matching_skips_builtin_and_legacy_matches(self):
        destination = self.destination()
        destination.category_matching = False
        destination.categories = {'milk': 'Dairy'}
        destination.category_rules.builtin_matches = {'milk': {'group': ('dairy', 'Dairy')}}
        self.assertEqual(destination.add('Milk'), 'plain')
        destination.category_rules.add.assert_called_once_with("Milk")
        destination.client.add_item_with_details.assert_not_called()
