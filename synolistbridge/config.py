# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Config:
    google_email: str
    anylist_email: str
    keep_list_id: str = ""
    anylist_list_id: str = ""
    poll_seconds: int = 60
    google_token_file: str = "/run/secrets/google_master_token"
    anylist_password_file: str = "/run/secrets/anylist_password"

    category_refresh_seconds: int = 604800

    lists: tuple = ()

    def routes(self):
        pairs = self.lists or ({"keep_list_id": self.keep_list_id, "anylist_list_id": self.anylist_list_id},)
        return [replace(self, lists=(), **pair) for pair in pairs]

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        interval = os.getenv("BRIDGE_POLL_INTERVAL", "").strip()
        if interval:
            data["poll_seconds"] = parse_duration(interval, "BRIDGE_POLL_INTERVAL")
        refresh = os.getenv("BRIDGE_CATEGORY_REFRESH_INTERVAL", "7d").strip() or "7d"
        data["category_refresh_seconds"] = parse_duration(refresh, "BRIDGE_CATEGORY_REFRESH_INTERVAL")
        config = cls(**data)
        for field in ("google_email", "anylist_email", "google_token_file", "anylist_password_file"):
            if not isinstance(getattr(config, field), str) or not getattr(config, field).strip():
                raise ValueError(f"{field} must be a nonempty string")
        if type(config.poll_seconds) is not int or not 30 <= config.poll_seconds <= 604800:
            raise ValueError("poll_seconds must be an integer between 30 and 604800")
        if config.lists:
            if config.keep_list_id or config.anylist_list_id:
                raise ValueError("Use lists or legacy list IDs, not both")
            if not isinstance(config.lists, (list, tuple)):
                raise ValueError("lists must be a nonempty array of list pairs")
        elif config.lists != () and config.lists != []:
            raise ValueError("Invalid lists")
        for pair in config.lists:
            if not isinstance(pair, dict) or set(pair) != {"keep_list_id", "anylist_list_id"}:
                raise ValueError("Each list pair requires only keep_list_id and anylist_list_id")
        sources = set()
        for selected in config.routes():
            for name in ("keep_list_id", "anylist_list_id"):
                value = getattr(selected, name)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{name} must be a nonempty string")
            if selected.keep_list_id in sources:
                raise ValueError("Each Keep checklist may appear only once")
            sources.add(selected.keep_list_id)
        return config


def parse_duration(value, variable):
    match = re.fullmatch(r"([0-9]+)([smhd])", value)
    error = f"{variable} must use s, m, h, or d (30s minimum, 7d maximum)"
    if not match or len(match[1]) > 6:
        raise ValueError(error)
    seconds = int(match[1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match[2]]
    if not 30 <= seconds <= 604800:
        raise ValueError(error)
    return seconds


def read_secret(path):
    secret = Path(path).read_text().rstrip("\r\n")
    if not secret or "\n" in secret or "\r" in secret:
        raise ValueError("Secret files must contain one nonempty line")
    return secret
