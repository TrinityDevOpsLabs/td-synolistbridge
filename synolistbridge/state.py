# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import fcntl
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "bridge.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another bridge process holds the data lock") from None
        yield


class State:
    def __init__(self, directory, route):
        self.db = sqlite3.connect(Path(directory) / "transfers.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transfers (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending','sending','review','delivered','done')),
                destination_id TEXT,
                updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        encoded = json.dumps(route, sort_keys=True)
        existing = self.db.execute("SELECT value FROM metadata WHERE key='route'").fetchone()
        if existing and existing[0] != encoded:
            self.db.close()
            raise ValueError("Data directory belongs to another account/list route; use a new directory")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('route', ?)", (encoded,))
            # A previous process may have died after the remote write succeeded.
            self.db.execute("UPDATE transfers SET status='review' WHERE status='sending'")

    def get(self, item_id):
        return self.db.execute("SELECT * FROM transfers WHERE id=?", (item_id,)).fetchone()

    def enqueue(self, item_id, text):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO transfers (id,text,status) VALUES (?,?,'pending')",
                            (item_id, text))

    def prepare(self, item_id, text):
        with self.db:
            self.db.execute("UPDATE transfers SET text=?, status='sending', updated=CURRENT_TIMESTAMP WHERE id=?",
                            (text, item_id))

    def set(self, item_id, status, destination_id=None):
        with self.db:
            self.db.execute("UPDATE transfers SET status=?, destination_id=COALESCE(?,destination_id),"
                            " updated=CURRENT_TIMESTAMP WHERE id=?", (status, destination_id, item_id))

    def rows(self):
        return self.db.execute("SELECT * FROM transfers ORDER BY updated,id").fetchall()

    def resolve(self, item_id, decision):
        if decision not in ("delivered", "retry", "skip"):
            raise ValueError("Invalid resolution")
        row = self.get(item_id)
        if row is None or row["status"] != "review":
            raise ValueError("Only a transfer in review can be resolved")
        self.set(item_id, {"delivered": "delivered", "retry": "pending", "skip": "done"}[decision])

    def close(self):
        self.db.close()
