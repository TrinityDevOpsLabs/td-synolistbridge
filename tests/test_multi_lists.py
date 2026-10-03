# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from synolistbridge.config import Config
from synolistbridge.__main__ import main, route
from synolistbridge.state import State


class MultipleListTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        self.data = dict(google_email='google', anylist_email='anylist', lists=[
            dict(keep_list_id='first', anylist_list_id='groceries'),
            dict(keep_list_id='second', anylist_list_id='hardware')])
        self.path.write_text(json.dumps(self.data))

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(['--config', str(self.path), '--data', self.temp.name, *args])

    def test_config_validates_pairs_and_legacy(self):
        self.assertEqual([c.keep_list_id for c in Config.load(self.path).routes()], ['first', 'second'])
        for pairs in ([], 'bad', [{}], [dict(keep_list_id='first', anylist_list_id='')],
                      [self.data['lists'][0], self.data['lists'][0]]):
            self.path.write_text(json.dumps(dict(self.data, lists=pairs)))
            with self.assertRaises(ValueError):
                Config.load(self.path)

    def test_one_route_failure_does_not_stop_other_routes(self):
        with patch('synolistbridge.providers.KeepSource') as source, \
             patch('synolistbridge.providers.AnyListDestination') as destination, \
             patch('synolistbridge.__main__.Bridge') as bridge:
            bridge.return_value.poll.side_effect = [RuntimeError('offline'), 0]
            self.assertEqual(self.command('once'), 1)
            self.assertEqual(bridge.return_value.poll.call_count, 2)
        databases = list((Path(self.temp.name) / 'routes').glob('*/transfers.sqlite3'))
        self.assertEqual(len(databases), 2)

    def test_legacy_history_retained_when_converted_and_reordered(self):
        selected = Config.load(self.path).routes()[0]
        state = State(self.temp.name, route(selected))
        state.enqueue('old-item', 'milk')
        state.set('old-item', 'done')
        state.close()
        self.data['lists'].reverse()
        self.path.write_text(json.dumps(self.data))
        self.assertEqual(self.command('status'), 0)
        state = State(self.temp.name, route(selected))
        self.assertEqual(state.get('old-item')['status'], 'done')
        state.close()

    def test_account_connections_shared_and_successful_health(self):
        with patch('synolistbridge.providers.KeepSource') as source, \
             patch('synolistbridge.providers.AnyListDestination') as destination, \
             patch('synolistbridge.__main__.Bridge') as bridge:
            bridge.return_value.poll.return_value = 0
            self.assertEqual(self.command('once'), 0)
            self.assertIs(source.call_args_list[1].kwargs['client'], source.return_value.keep)
            self.assertIs(destination.call_args_list[1].kwargs['client'], destination.return_value.client)
        self.assertTrue((Path(self.temp.name) / 'health.json').exists())
