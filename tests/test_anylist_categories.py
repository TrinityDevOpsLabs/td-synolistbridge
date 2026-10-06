# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import Mock, patch

from synolistbridge.anylist_categories import CategoryRules, builtin_categories, field, fields, string


class CategoryRuleTests(unittest.TestCase):
    def test_saved_rules_are_scoped_to_destination_and_refresh(self):
        category = field(1, 'dairy') + field(5, 'Dairy') + field(7, 'dairy-system')
        group = field(1, 'group') + field(5, category)
        rule = field(4, 'group') + field(5, 'creama') + field(6, 'dairy')
        response = (field(1, 'destination') + field(7, field(1, group))
                    + field(13, rule))
        other = field(1, 'other-list') + field(13, rule)
        rules = CategoryRules(Mock(), 'destination')
        rules.post = Mock(return_value=field(1, field(6, response) + field(6, other)))
        with patch("synolistbridge.anylist_categories.requests.get") as get:
            get.return_value.json.return_value = {"tags": {"milk": {"rootCategory": "dairy"}},
                                                 "normalizedDisplayNamesIndex": {"milk": "milk"}}
            rules.refresh(str.casefold)
        self.assertEqual(rules.matches, {'creama': {'group': ('dairy', 'Dairy')}})
        self.assertEqual(rules.category_system_ids, {'dairy': 'dairy-system'})
        rules.post.return_value = b''
        with patch("synolistbridge.anylist_categories.requests.get") as get:
            get.return_value.json.return_value = {"tags": {"milk": {"rootCategory": "dairy"}},
                                                 "normalizedDisplayNamesIndex": {"milk": "milk"}}
            rules.refresh(str.casefold)
        self.assertEqual(rules.matches, {})
        self.assertEqual(rules.category_system_ids, {})

    def test_add_sends_modern_assignments_for_all_groups(self):
        client = Mock()
        client.user_id.return_value = 'user'
        rules = CategoryRules(client, 'destination')
        rules.post = Mock(return_value=b'')
        item_id = rules.add('Creama', {'group': ('dairy', 'Dairy'), 'second': ('food', 'Food')})
        endpoint, payload = rules.post.call_args.args
        self.assertEqual(endpoint, 'data/shopping-lists/update')
        operation = fields(fields(payload)[1][0])
        item = fields(operation[6][0])
        self.assertEqual(string(item, 1), item_id)
        self.assertEqual(string(item, 4), 'Creama')
        self.assertEqual([(string(fields(x), 2), string(fields(x), 3)) for x in item[20]],
                         [('group', 'dairy'), ('second', 'food')])

    def test_web_compatible_add_payload(self):
        client = Mock()
        client.user_id.return_value = 'user'
        rules = CategoryRules(client, 'destination')
        rules.category_system_ids = {'other-id': 'other'}
        rules.post = Mock(return_value=b'')
        rules.add('Shoes', {'group': ('other-id', 'Other')})
        operation = fields(fields(rules.post.call_args.args[1])[1][0])
        metadata = fields(operation[1][0])
        item = fields(operation[6][0])
        self.assertEqual(set(metadata), {1, 2, 3})
        self.assertEqual(string(metadata, 2), 'add-shopping-list-item')
        self.assertEqual(string(metadata, 3), 'user')
        self.assertEqual(set(item), {1, 3, 4, 11, 12, 13, 20})
        self.assertEqual(string(item, 11), 'other')
        self.assertEqual(string(item, 13), 'other')
        self.assertEqual(string(item, 12), 'user')

    def test_plain_and_legacy_category_adds_omit_defaults(self):
        client = Mock()
        client.user_id.return_value = 'user'
        rules = CategoryRules(client, 'destination')
        rules.post = Mock(return_value=b'')
        for category in (None, 'Custom Dairy'):
            rules.add('Milk', category=category)
            operation = fields(fields(rules.post.call_args.args[1])[1][0])
            item = fields(operation[6][0])
            self.assertNotIn(6, item)
            self.assertNotIn(13, item)
            self.assertNotIn(20, item)
            self.assertEqual(string(item, 11), category or '')
            self.assertNotIn(4, fields(operation[1][0]))

    def test_malformed_messages_fail_without_silent_partial_parsing(self):
        for payload in (b'\x0a\x03x', b'\x80', b'\x00', b'\x0b'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                fields(payload)

    def test_builtin_catalog_maps_system_ids_and_renamed_groups(self):
        data = {'tags': {'cottage-cheese': {'rootCategory': 'dairy'},
                         'bacon': {'rootCategory': 'meat'},
                         'cheese-sticks': {'rootCategory': 'frozen-foods'},
                         'unknown': {}},
                'normalizedDisplayNamesIndex': {'cottage cheese': 'cottage-cheese',
                                                'bacon': 'bacon', 'cheese sticks': 'cheese-sticks',
                                                'unknown': 'unknown'}}
        systems = {'dairy': {'first': ('dairy-id', 'Chilled'), 'second': ('dairy-2', 'Dairy')},
                   'meat': {'first': ('meat-id', 'Meat')},
                   'frozen-foods': {'first': ('frozen-id', 'Frozen Foods')}}
        matches = builtin_categories(data, systems, str.casefold)
        self.assertEqual(matches['cottage cheese'], systems['dairy'])
        self.assertEqual(matches['bacon'], systems['meat'])
        self.assertEqual(matches['cheese sticks'], systems['frozen-foods'])
        self.assertNotIn('unknown', matches)

    def test_invalid_catalog_is_rejected(self):
        for data in ({}, {'tags': {}, 'normalizedDisplayNamesIndex': {}}, {'tags': []}):
            with self.assertRaises(ValueError):
                builtin_categories(data, {}, str.casefold)
