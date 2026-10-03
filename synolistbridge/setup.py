# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
"""One-time interactive terminal setup; never performs transfers."""
import termios
import sys
import json
import os
import tempfile
import secrets
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
        pairs = fields.get("lists") or [{"keep_list_id": fields["keep"], "anylist_list_id": fields["anylist"]}]
        sources = set()
        for pair in pairs:
            for key, field in (("keep", "keep_list_id"), ("anylist", "anylist_list_id")):
                if pair[field] not in {item_id for item_id, _ in self.lists[key]}:
                    raise ValueError("Invalid list selection")
            if pair["keep_list_id"] in sources:
                raise ValueError("Each Keep checklist may appear only once")
            sources.add(pair["keep_list_id"])
        config = Config(self.draft["google_email"].strip(), self.draft["anylist_email"].strip(),
                        lists=pairs,
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


def masked_input(prompt):
    """Read a secret from the interactive Linux terminal with star feedback."""
    descriptor = sys.stdin.fileno()
    original = termios.tcgetattr(descriptor)
    settings = termios.tcgetattr(descriptor)
    settings[3] &= ~(termios.ECHO | termios.ICANON)
    settings[6][termios.VMIN] = 1
    settings[6][termios.VTIME] = 0
    chars = []
    print(prompt, end="", flush=True)
    try:
        termios.tcsetattr(descriptor, termios.TCSANOW, settings)
        while True:
            char = sys.stdin.read(1)
            if not char or char == "\x04":
                raise EOFError
            if char in ("\n", "\r"):
                return "".join(chars)
            if char == "\x03":
                raise KeyboardInterrupt
            if char in ("\x7f", "\b"):
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
            elif char == "\x15":  # Ctrl+U clears the field.
                print("\b \b" * len(chars), end="", flush=True)
                chars.clear()
            elif char.isprintable():
                chars.append(char)
                print("*", end="", flush=True)
    finally:
        termios.tcsetattr(descriptor, termios.TCSANOW, original)
        print(flush=True)


def exchange_google_cookie(email, cookie):
    """Exchange a browser login cookie without persisting or printing it."""
    if not email or not cookie or "\n" in cookie or "\r" in cookie:
        raise ValueError("Email and a single-line OAuth cookie are required")
    import gpsoauth
    response = gpsoauth.exchange_token(email, cookie, secrets.token_hex(8))
    token = response.get("Token")
    if not isinstance(token, str) or not token or "\n" in token or "\r" in token:
        raise ValueError("Google token exchange failed")
    return token


def run_setup(config_path, data):
    if Path(config_path).exists():
        print("Already configured. Setup will not overwrite the existing configuration.")
        return 1
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Setup requires an interactive terminal. Use docker run --rm -it with your data volume.")
        return 1
    wizard = Wizard(config_path, data)
    print("SynoListBridge setup. Credentials will be saved in the mounted data directory.")
    print("You can use your own Google account. A separate account with the checklist shared to it is optional but recommended.")
    print("In your computer's browser, open https://accounts.google.com/EmbeddedSetup and sign in.")
    print("Click I agree if prompted. A page that keeps loading is normal.")
    print("Open browser developer tools (F12), then Application > Cookies (Chrome/Edge)")
    print("or Storage > Cookies (Firefox). Select accounts.google.com and copy the oauth_token value.")
    print("Paste only that value below, not your password. Setup will exchange it automatically.")
    try:
        email = input("Google account email: ").strip()
        cookie = masked_input("Google oauth_token cookie (masked): ").strip()
        print("Connecting to Google...")
        try:
            token = exchange_google_cookie(email, cookie)
        finally:
            cookie = None
        print("Enter the email address and password you use to sign into AnyList.")
        fields = {
            "google_email": email,
            "google_token": token,
            "anylist_email": input("AnyList account email: ").strip(),
            "anylist_password": masked_input("AnyList account password (masked): "),
        }
        print("Connecting accounts and finding lists...")
        wizard.discover(fields)
        print("Create list pairs: each Keep checklist sends items only to its selected AnyList destination.")
        print("All pairs use these same accounts and shared polling settings.")
        print("Only selected Keep checklists are processed. AnyList changes are not copied back to Keep.")
        print("You will review every pair before anything is saved or transferred.")
        pairs = []
        while True:
            available = [item for item in wizard.lists["keep"]
                         if item[0] not in {pair["keep_list_id"] for pair in pairs}]
            print(f"Choose list pair {len(pairs) + 1}:")
            keep_id = choose_list("Keep source checklist (unchecked items will be transferred):", available)
            any_id = choose_list("AnyList destination for this checklist:", wizard.lists["anylist"])
            pairs.append({"keep_list_id": keep_id, "anylist_list_id": any_id})
            if len(pairs) == len(wizard.lists["keep"]):
                break
            if input("Add another list pair? Type yes, or press Enter to finish: ").strip().lower() != "yes":
                break
        print(f"Review all {len(pairs)} list pair(s) (Keep source → AnyList destination):")
        for number, pair in enumerate(pairs, 1):
            names = [next(name for item_id, name in wizard.lists[key] if item_id == pair[field])
                     for key, field in (("keep", "keep_list_id"), ("anylist", "anylist_list_id"))]
            names = ["".join(c if c.isprintable() else " " for c in str(name)) for name in names]
            print(f"  {number}. {names[0]} → {names[1]}")
        print("The first poll transfers ALL existing unchecked, nonempty items from EVERY selected Keep checklist.")
        print("Delivered items are checked off in Keep, or deleted if BRIDGE_DELETE_KEEP_ITEMS=true.")
        print("Setup saves configuration only. The running bridge starts transfers immediately after setup finishes.")
        print("Review every source checklist and disable any previous bridge before confirming.")
        if input("Save all list pairs and allow transfers? Type yes to confirm: ").strip().lower() != "yes":
            print("Setup cancelled. No configuration saved.")
            return 1
        wizard.save({"lists": pairs, "confirm": "yes"})
    except (EOFError, KeyboardInterrupt):
        print("\nSetup cancelled. No configuration saved.")
        return 1
    except Exception as exc:
        print(f"Setup failed ({type(exc).__name__}). Check credentials, list access, and data permissions; then rerun setup.")
        return 1
    finally:
        wizard.draft = None
        wizard.lists = None
    print("Setup complete. The running DSM bridge will start automatically. If using one-off setup, start your DSM project.")
    return 0
