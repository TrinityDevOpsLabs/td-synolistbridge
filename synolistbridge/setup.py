# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
"""One-time interactive terminal setup; never performs transfers."""
import getpass
import sys
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .providers import KeepSource, AnyListDestination


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Wizard:
    def __init__(self, config_path, data):
        self.config_path = Path(config_path)
        self.data = Path(data)
        self.draft = None
        self.lists = None

    def discover(self, fields):
        self.draft = None
        self.lists = None
        credentials = (fields["google_token"], fields["anylist_password"])
        if any(not value or "\n" in value or "\r" in value for value in credentials):
            raise ValueError("Invalid credentials")
        # Use temporary secret files until both accounts have authenticated.
        with tempfile.TemporaryDirectory() as temporary:
            token = Path(temporary) / "token"
            password = Path(temporary) / "password"
            atomic_write(token, credentials[0])
            atomic_write(password, credentials[1])
            config = Config(fields["google_email"].strip(), fields["anylist_email"].strip(),
                            "discover", "discover", google_token_file=str(token),
                            anylist_password_file=str(password))
            if not config.google_email or not config.anylist_email:
                raise ValueError("Email required")
            source, destination = KeepSource(config), AnyListDestination(config)
            lists = {"keep": source.lists(), "anylist": destination.lists()}
        if not lists["keep"] or not lists["anylist"]:
            raise ValueError("No available lists")
        self.draft = dict(fields)
        self.lists = lists

    def save(self, fields):
        if self.draft is None or fields.get("confirm") != "yes":
            raise ValueError("Confirm first transfer")
        for key in ("keep", "anylist"):
            if fields[key] not in {item_id for item_id, _ in self.lists[key]}:
                raise ValueError("Invalid list selection")
        config = Config(self.draft["google_email"].strip(), self.draft["anylist_email"].strip(),
                        fields["keep"], fields["anylist"],
                        google_token_file=str(self.data / "secrets/google_master_token"),
                        anylist_password_file=str(self.data / "secrets/anylist_password"))
        if self.config_path.exists():
            raise ValueError("Already configured")
        atomic_write(config.google_token_file, self.draft["google_token"])
        atomic_write(config.anylist_password_file, self.draft["anylist_password"])
        # Publish config last: a failed setup cannot start a partial route.
        atomic_write(self.config_path, json.dumps(asdict(config), indent=2) + "\n")
        self.draft = None
        self.lists = None

def choose_list(title, lists):
    print(title)
    for number, (_, name) in enumerate(lists, 1):
        # Provider names may contain terminal control characters.
        safe_name = "".join(char if char.isprintable() else " " for char in str(name))
        print(f"  {number}. {safe_name}")
    while True:
        selection = input("Select list number: ").strip()
        if selection.isascii() and selection.isdigit() and 1 <= int(selection) <= len(lists):
            return lists[int(selection) - 1][0]
        print("Enter one of the listed numbers.")


def run_setup(config_path, data):
    if Path(config_path).exists():
        print("Already configured. Setup will not overwrite the existing configuration.")
        return 1
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Setup requires an interactive terminal. Use docker run --rm -it with your data volume.")
        return 1
    wizard = Wizard(config_path, data)
    print("SynoListBridge setup. Credentials will be saved in the mounted data directory.")
    print("Use a dedicated Google account shared onto your Keep checklist and its Google master token.")
    try:
        fields = {
            "google_email": input("Google account email: ").strip(),
            "google_token": getpass.getpass("Google master token (hidden): "),
            "anylist_email": input("AnyList email: ").strip(),
            "anylist_password": getpass.getpass("AnyList password (hidden): "),
        }
        print("Connecting accounts and finding lists...")
        wizard.discover(fields)
        selections = {key: choose_list(title, wizard.lists[key]) for key, title in
                      (("keep", "Google Keep checklist:"), ("anylist", "AnyList destination:"))}
        print("The first poll will transfer every existing unchecked, nonempty item in the selected Keep list.")
        print("Review that list and disable any previous bridge before starting the DSM project.")
        if input("Save this configuration? Type yes to confirm: ").strip().lower() != "yes":
            print("Setup cancelled. No configuration saved.")
            return 1
        wizard.save(dict(selections, confirm="yes"))
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled. No configuration saved.")
        return 1
    except Exception as exc:
        print(f"Setup failed ({type(exc).__name__}). Check credentials, list access, and data permissions; then rerun setup.")
        return 1
    finally:
        wizard.draft = None
        wizard.lists = None
    print("Setup complete. No items transferred. Start the project in DSM Container Manager.")
    return 0
