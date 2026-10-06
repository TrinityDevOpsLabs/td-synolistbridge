# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import os
import logging
import time

import requests
from dataclasses import dataclass

from .config import read_secret


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    checked: bool


class KeepSource:
    def __init__(self, config, client=None):
        delete = os.getenv("BRIDGE_DELETE_KEEP_ITEMS", "false").strip().lower()
        if delete not in ("true", "false"):
            raise ValueError("BRIDGE_DELETE_KEEP_ITEMS must be true or false")
        self.delete_items = delete == "true"
        import gkeepapi
        self.keep = client if client is not None else gkeepapi.Keep()
        if client is None:
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
        if self.delete_items:
            item.delete()
        else:
            item.checked = True
        # On failure the CLI discards this client; a fresh poll verifies remote state.
        self.keep.sync()


class AnyListDestination:
    def __init__(self, config, state=None, client=None):
        matching = os.getenv("BRIDGE_CATEGORY_MATCHING", "true").strip().lower()
        if matching not in ("true", "false"):
            raise ValueError("BRIDGE_CATEGORY_MATCHING must be true or false")
        self.category_matching = matching == "true"
        from pyanylist import AnyListClient
        self.client = client if client is not None else AnyListClient.login(
            config.anylist_email, read_secret(config.anylist_password_file))
        self.list_id = config.anylist_list_id
        self.categories = {}
        from .anylist_categories import CategoryRules
        self.category_rules = CategoryRules(self.client, self.list_id)
        self.state = state
        self.refresh_seconds = getattr(config, "category_refresh_seconds", 604800)
        self.next_refresh = 0
        self.cache_loaded = False
        cached = state.load_categories() if state is not None and self.category_matching else None
        if cached:
            refreshed, payload = cached
            self.categories = payload["categories"]
            self.category_rules.matches = payload["rules"]
            self.category_rules.builtin_matches = payload.get("builtin_rules", {})
            self.category_rules.category_system_ids = payload.get("category_system_ids", {})
            self.next_refresh = refreshed + self.refresh_seconds if payload.get("version") == 3 else 0
            self.cache_loaded = True

    def lists(self):
        return [(shopping.id, shopping.name) for shopping in self.client.get_lists()]

    @staticmethod
    def category_key(text):
        return " ".join(text.split()).casefold()

    def validate(self):
        shopping = self.client.get_list_by_id(self.list_id)
        if not self.category_matching:
            self.categories = {}
            return
        now = time.time()
        if now < self.next_refresh:
            return
        try:
            self.refresh_categories(shopping, now)
        except (requests.RequestException, ValueError, RuntimeError):
            if not self.cache_loaded:
                raise
            self.next_refresh = now + min(300, self.refresh_seconds)
            logging.getLogger("synolistbridge").warning(
                "Category refresh failed; using cached categories")

    def refresh_categories(self, shopping, now):
        categories = {}
        # Favorites supply saved preferences; the selected list takes precedence.
        # Include checked items so a previous purchase can categorize a new one.
        for item in [*self.client.get_favourites(), *shopping.items]:
            if item.category:
                categories[self.category_key(item.name)] = item.category
        self.category_rules.refresh(self.category_key)
        if self.state is not None:
            self.state.save_categories(now, {"version": 3, "categories": categories,
                                             "rules": self.category_rules.matches,
                                             "builtin_rules": self.category_rules.builtin_matches,
                                             "category_system_ids": self.category_rules.category_system_ids})
        self.categories = categories
        self.cache_loaded = True
        self.next_refresh = now + self.refresh_seconds

    def add(self, text):
        assignments = self.category_rules.matches.get(self.category_key(text)) if self.category_matching else None
        if assignments:
            return self.category_rules.add(text, assignments)
        category = self.categories.get(self.category_key(text)) if self.category_matching else None
        if category:
            return self.category_rules.add(text, category=category)
        builtin = self.category_rules.builtin_matches.get(self.category_key(text)) if self.category_matching else None
        if builtin:
            return self.category_rules.add(text, builtin)
        return self.category_rules.add(text)
