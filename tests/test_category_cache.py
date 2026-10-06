# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from synolistbridge.config import Config
from synolistbridge.state import State


class CategoryCacheTests(unittest.TestCase):
    def test_cache_survives_restart_and_empty_refresh_replaces_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            state = State(directory, {'list': 'destination'})
            self.assertIsNone(state.load_categories())
            payload = {'rules': {'creama': {'group': ['dairy', 'Dairy']}}, 'categories': {}}
            state.save_categories(100, payload)
            state.close()
            state = State(directory, {'list': 'destination'})
            self.assertEqual(state.load_categories(), (100, payload))
            state.save_categories(200, {'rules': {}, 'categories': {}})
            self.assertEqual(state.load_categories(), (200, {'rules': {}, 'categories': {}}))
            state.close()

    def test_category_refresh_interval_default_override_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(dict(google_email='google', anylist_email='anylist',
                                            keep_list_id='keep', anylist_list_id='destination')))
            for value, expected in (('', 604800), ('6h', 21600), ('30s', 30), ('7d', 604800)):
                with patch.dict(os.environ, {'BRIDGE_CATEGORY_REFRESH_INTERVAL': value}):
                    self.assertEqual(Config.load(path).category_refresh_seconds, expected)
            for value in ('6hrs', '21600', '29s', '8d'):
                with patch.dict(os.environ, {'BRIDGE_CATEGORY_REFRESH_INTERVAL': value}):
                    with self.assertRaisesRegex(ValueError, 'BRIDGE_CATEGORY_REFRESH_INTERVAL'):
                        Config.load(path)

    def test_restart_reuses_builtin_cache_and_upgrades_old_cache(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from synolistbridge.providers import AnyListDestination
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / 'secret'
            secret.write_text('test-secret')
            config = SimpleNamespace(anylist_email='test', anylist_password_file=str(secret),
                                     anylist_list_id='destination', category_refresh_seconds=604800)
            state = State(directory, {'list': 'destination'})
            self.addCleanup(state.close)
            payload = {'version': 3, 'category_system_ids': {'dairy': 'dairy'}, 'rules': {}, 'categories': {},
                       'builtin_rules': {'cottage cheese': {'group': ['dairy', 'Dairy']}}}
            state.save_categories(100, payload)
            client = Mock()
            module = SimpleNamespace(AnyListClient=SimpleNamespace(login=Mock(return_value=client)))
            with patch.dict('sys.modules', {'pyanylist': module}), \
                 patch.dict(os.environ, {'BRIDGE_CATEGORY_MATCHING': 'true'}):
                destination = AnyListDestination(config, state)
                with patch('synolistbridge.providers.time.time', return_value=101):
                    destination.validate()
                self.assertEqual(destination.category_rules.builtin_matches, payload['builtin_rules'])
                self.assertEqual(destination.category_rules.category_system_ids, {'dairy': 'dairy'})
                client.get_favourites.assert_not_called()
                state.save_categories(100, {'rules': {}, 'categories': {}})
                upgraded = AnyListDestination(config, state)
                self.assertEqual(upgraded.next_refresh, 0)
                self.assertTrue(upgraded.cache_loaded)
