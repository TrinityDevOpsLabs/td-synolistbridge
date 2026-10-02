# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
"""One-time browser setup. The HTTP listener closes before transfers start."""
import html
import json
import os
import secrets
import tempfile
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
        self.token = secrets.token_urlsafe(32)
        self.draft = None
        self.lists = None

    @property
    def base(self):
        return f"/{self.token}/"

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

    def page(self, message=""):
        esc = html.escape
        if self.draft is None:
            form = f'''<form method="post" action="{self.base}discover">
            <label>Google account email<input name="google_email" type="email" required></label>
            <label>Google master token<input name="google_token" type="password" autocomplete="off" required></label>
            <p>Use a dedicated Google account shared onto your shopping checklist.
            Obtain its master token using the
            <a href="https://github.com/simon-weber/gpsoauth#alternative-flow" target="_blank" rel="noreferrer">gpsoauth guide</a>.</p>
            <label>AnyList email<input name="anylist_email" type="email" required></label>
            <label>AnyList password<input name="anylist_password" type="password" autocomplete="off" required></label>
            <button>Connect accounts and find lists</button></form>'''
        else:
            selections = ""
            for key, title in (("keep", "Google Keep checklist"), ("anylist", "AnyList destination")):
                options = ''.join(f'<option value="{esc(str(item_id), quote=True)}">{esc(name)}</option>'
                                  for item_id, name in self.lists[key])
                selections += f'<label>{title}<select name="{key}">{options}</select></label>'
            form = f'''<form method="post" action="{self.base}save">{selections}
            <p>The first poll will transfer every unchecked item in the selected Keep checklist.
            Disable any previous bridge for that list before continuing.</p>
            <label><input class="check" type="checkbox" name="confirm" value="yes" required>
            I have reviewed the Keep list and want to start transferring its unchecked items.</label>
            <button>Save and start bridge</button></form>'''
        return f'''<!doctype html><html lang="en"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>SynoListBridge setup</title><style>
        body{{font:16px system-ui;max-width:600px;margin:40px auto;padding:0 20px;color:#182333}}
        label{{display:block;margin:20px 0}}input,select,button{{box-sizing:border-box;width:100%;padding:12px;font:inherit}}
        .check{{width:auto}}button{{background:#174e85;color:white;border:0;border-radius:6px;cursor:pointer}}
        p{{line-height:1.5}}.message{{color:#9c241e}}
        </style><h1>SynoListBridge</h1><p>Trinity DevOps LLC · DSM setup</p>
        <p>Use this setup page only on your trusted private network. Credentials are stored privately in the app data volume.</p>
        <p class="message">{esc(message)}</p>{form}</html>'''


def handler_for(wizard):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # The URL contains a setup access token.

        def respond(self, status, body):
            encoded = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path != wizard.base:
                return self.respond(404, "Use the private setup link from Container Manager logs.")
            self.respond(200, wizard.page())

        def do_POST(self):
            if self.path not in (wizard.base + "discover", wizard.base + "save"):
                return self.respond(404, "Unknown setup page")
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if origin and (urlsplit(origin).scheme not in ("http", "https") or urlsplit(origin).netloc != host):
                return self.respond(403, "Origin rejected")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
                return self.respond(415, "Form encoding required")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    return self.respond(413, "Form too large")
                raw = self.rfile.read(length).decode("utf-8")
                values = parse_qs(raw, strict_parsing=True, max_num_fields=10)
                if any(len(value) != 1 for value in values.values()):
                    raise ValueError("Duplicate fields")
                fields = {key: value[0] for key, value in values.items()}
                if self.path.endswith("discover"):
                    wizard.discover(fields)
                    self.respond(200, wizard.page())
                else:
                    wizard.save(fields)
                    self.respond(200, "<h1>Setup complete</h1><p>SynoListBridge is starting. This setup listener will close. View progress in Container Manager logs.</p>")
            except Exception:
                # Do not reflect provider errors, request bodies, or credentials.
                self.respond(400, wizard.page("Setup could not be completed. Check credentials, list access, and your selections, then try again."))

    return Handler


class SetupServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(10)
        return connection, address


def run_setup(config_path, data, stop, port=8765):
    wizard = Wizard(config_path, data)
    with SetupServer(("0.0.0.0", port), handler_for(wizard)) as server:
        server.timeout = 1
        print(f"Setup required. Open http://YOUR-NAS-IP:{port}{wizard.base} on your private network.", flush=True)
        while not stop.is_set() and not Path(config_path).exists():
            server.handle_request()
