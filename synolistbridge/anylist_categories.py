# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
"""AnyList category rules omitted by pyanylist's public API.

Wire field numbers follow anylist_rs/src/protobuf/anylist.proto.
Only the messages needed for category rules and item creation are handled here.
"""
import uuid

import requests


def fields(data):
    result = {}
    pos = 0

    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError("Truncated AnyList message")
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError("Invalid AnyList varint")

    while pos < len(data):
        tag = varint()
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("Invalid AnyList field")
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            size = varint() if wire == 2 else (8 if wire == 1 else 4)
            if pos + size > len(data):
                raise ValueError("Truncated AnyList field")
            value = data[pos:pos + size]
            pos += size
        else:
            raise ValueError("Unsupported AnyList wire type")
        result.setdefault(number, []).append(value)
    return result


def string(message, number):
    return message.get(number, [b""])[0].decode("utf-8")


def varint(value):
    output = bytearray()
    while value > 127:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return bytes(output)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return varint((number << 3) | 2) + varint(len(value)) + value


class CategoryRules:
    def __init__(self, client, list_id):
        self.client = client
        self.list_id = list_id
        self.client_id = uuid.uuid4().hex
        self.matches = {}
        self.builtin_matches = {}
        self.category_system_ids = {}

    def post(self, endpoint, payload):
        # The native client handles token refresh during validate() before this.
        response = requests.post(
            "https://www.anylist.com/" + endpoint,
            headers={
                "Authorization": "Bearer " + self.client.export_tokens().access_token,
                "X-AnyLeaf-API-Version": "3",
                "X-AnyLeaf-Client-Identifier": self.client_id,
            },
            files={"operations": (None, payload)},
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def refresh(self, key):
        data = fields(self.post("data/user-data/get", b""))
        shopping = fields(data.get(1, [b""])[0])
        matches = {}
        system_categories = {}
        category_system_ids = {}
        for raw in shopping.get(6, []):
            response = fields(raw)
            if string(response, 1) != self.list_id:
                continue
            groups = {}
            for group_raw in response.get(7, []):
                group = fields(fields(group_raw).get(1, [b""])[0])
                group_id = string(group, 1)
                groups[group_id] = {}
                for category in map(fields, group.get(5, [])):
                    category_id, category_name = string(category, 1), string(category, 5)
                    groups[group_id][category_id] = category_name
                    system = string(category, 7)
                    if system and category_id and category_name:
                        system_categories.setdefault(system, {})[group_id] = (category_id, category_name)
                        category_system_ids[category_id] = system
            for rule in map(fields, response.get(13, [])):
                group_id, category_id = string(rule, 4), string(rule, 6)
                name = string(rule, 5)
                category = groups.get(group_id, {}).get(category_id)
                if name and category:
                    matches.setdefault(key(name), {})[group_id] = (category_id, category)
        # Download the same public grocery-name index used by AnyList Web.
        # Map its stable system categories to this list's IDs and display names,
        # including renamed built-in categories and multiple category groups.
        response = requests.get(
            "https://www.anylist.com/static/webapp/data/tag_data.json", timeout=30)
        response.raise_for_status()
        builtin_matches = builtin_categories(response.json(), system_categories, key)
        # Publish all category snapshots only after all reads succeed.
        self.matches = matches
        self.builtin_matches = builtin_matches
        self.category_system_ids = category_system_ids

    def add(self, name, assignments=None, category=None):
        item_id = uuid.uuid4().hex
        item = (field(1, item_id) + field(3, self.list_id) + field(4, name)
                + field(12, self.client.user_id()))
        # Match the web client: omit explicit default fields and retain legacy
        # system category metadata alongside modern category assignments.
        system_ids = {self.category_system_ids[category_id]
                      for category_id, _ in (assignments or {}).values()
                      if category_id in self.category_system_ids}
        if len(system_ids) == 1:
            system_id = next(iter(system_ids))
            item += field(11, system_id) + field(13, system_id)
        elif category:
            item += field(11, category)
        for group_id, (category_id, _) in (assignments or {}).items():
            assignment = (field(1, uuid.uuid4().hex) + field(2, group_id)
                          + field(3, category_id))
            item += field(20, assignment)
        metadata = (field(1, uuid.uuid4().hex) + field(2, "add-shopping-list-item")
                    + field(3, self.client.user_id()))
        operation = (field(1, metadata) + field(2, self.list_id)
                     + field(3, item_id) + field(6, item))
        self.post("data/shopping-lists/update", field(1, operation))
        return item_id


def builtin_categories(data, system_categories, key):
    tags = data.get("tags")
    names = data.get("normalizedDisplayNamesIndex")
    if not isinstance(tags, dict) or not isinstance(names, dict) or not tags or not names:
        raise ValueError("Invalid AnyList grocery database")
    matches = {}
    for name, tag_id in names.items():
        tag = tags.get(tag_id, {})
        root = tag.get("rootCategory", tag_id)
        assignments = system_categories.get(root)
        if assignments:
            matches[key(name)] = assignments
    return matches
