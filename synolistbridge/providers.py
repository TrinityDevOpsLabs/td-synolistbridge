# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from .config import read_secret


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    checked: bool


class KeepSource:
    def __init__(self, config):
        import gkeepapi
        self.keep = gkeepapi.Keep()
        self.keep.authenticate(config.google_email, read_secret(config.google_token_file))
        self.list_id = config.keep_list_id

    def lists(self):
        import gkeepapi
        return [(note.id, note.title) for note in self.keep.all()
                if isinstance(note, gkeepapi.node.List) and not note.trashed and not note.deleted]

    def note(self):
        import gkeepapi
        note = self.keep.get(self.list_id)
        if not isinstance(note, gkeepapi.node.List) or note.trashed or note.deleted:
            raise ValueError("Selected Keep checklist is unavailable")
        return note

    def items(self):
        self.keep.sync()
        return [Item(item.id, item.text, item.checked) for item in self.note().items
                if not item.deleted]

    def complete(self, item_id):
        item = next(item for item in self.note().items if item.id == item_id and not item.deleted)
        item.checked = True
        # On failure the CLI discards this client; a fresh poll verifies remote state.
        self.keep.sync()


class AnyListDestination:
    def __init__(self, config):
        from pyanylist import AnyListClient
        self.client = AnyListClient.login(config.anylist_email, read_secret(config.anylist_password_file))
        self.list_id = config.anylist_list_id

    def lists(self):
        return [(shopping.id, shopping.name) for shopping in self.client.get_lists()]

    def validate(self):
        self.client.get_list_by_id(self.list_id)

    def add(self, text):
        return self.client.add_item(self.list_id, text).id
