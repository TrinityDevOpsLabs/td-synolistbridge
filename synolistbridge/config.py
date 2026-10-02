# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    google_email: str
    anylist_email: str
    keep_list_id: str
    anylist_list_id: str
    poll_seconds: int = 60
    google_token_file: str = "/run/secrets/google_master_token"
    anylist_password_file: str = "/run/secrets/anylist_password"

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        config = cls(**data)
        for field in ("google_email", "anylist_email", "keep_list_id",
                      "anylist_list_id", "google_token_file", "anylist_password_file"):
            if not isinstance(getattr(config, field), str) or not getattr(config, field).strip():
                raise ValueError(f"{field} must be a nonempty string")
        if type(config.poll_seconds) is not int or not 30 <= config.poll_seconds <= 86400:
            raise ValueError("poll_seconds must be an integer between 30 and 86400")
        return config


def read_secret(path):
    secret = Path(path).read_text().rstrip("\r\n")
    if not secret or "\n" in secret or "\r" in secret:
        raise ValueError("Secret files must contain one nonempty line")
    return secret
