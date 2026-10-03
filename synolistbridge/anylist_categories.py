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
        for raw in shopping.get(6, []):
            response = fields(raw)
            if string(response, 1) != self.list_id:
                continue
            groups = {}
            for group_raw in response.get(7, []):
                group = fields(fields(group_raw).get(1, [b""])[0])
                groups[string(group, 1)] = {
                    string(category, 1): string(category, 5)
                    for category in map(fields, group.get(5, []))
                }
            for rule in map(fields, response.get(13, [])):
                group_id, category_id = string(rule, 4), string(rule, 6)
                name = string(rule, 5)
                category = groups.get(group_id, {}).get(category_id)
                if name and category:
                    matches.setdefault(key(name), {})[group_id] = (category_id, category)
        self.matches = matches

    def add(self, name, assignments):
        item_id = uuid.uuid4().hex
        item = (field(1, item_id) + field(3, self.list_id) + field(4, name)
                + field(6, 0) + field(12, self.client.user_id()))
        for group_id, (category_id, _) in assignments.items():
            assignment = (field(1, uuid.uuid4().hex) + field(2, group_id)
                          + field(3, category_id))
            item += field(20, assignment)
        metadata = (field(1, uuid.uuid4().hex) + field(2, "add-shopping-list-item")
                    + field(3, self.client.user_id()) + field(4, 0))
        operation = (field(1, metadata) + field(2, self.list_id)
                     + field(3, item_id) + field(6, item))
        self.post("data/shopping-lists/update", field(1, operation))
        return item_id
