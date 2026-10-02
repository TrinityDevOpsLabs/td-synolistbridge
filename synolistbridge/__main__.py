# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from pathlib import Path

from .bridge import Bridge
from .config import Config
from .state import State, exclusive_lock


def route(config):
    return {key: getattr(config, key) for key in
            ("google_email", "anylist_email", "keep_list_id", "anylist_list_id")}


def main(argv=None):
    parser = argparse.ArgumentParser(description="SynoListBridge by Trinity DevOps LLC")
    parser.add_argument("--config", default=os.getenv("BRIDGE_CONFIG", "/config/config.json"))
    parser.add_argument("--data", default=os.getenv("BRIDGE_DATA", "/data"))
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("start", "run", "once", "discover", "status", "check", "health"):
        commands.add_parser(command)
    resolve = commands.add_parser("resolve")
    resolve.add_argument("item_id")
    resolve.add_argument("decision", choices=("delivered", "retry", "skip"))
    args = parser.parse_args(argv)
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Dependencies may log raw provider responses; expose only our own safe messages.
    logging.getLogger().setLevel(logging.CRITICAL)
    logging.getLogger("synolistbridge").setLevel(logging.INFO)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        if args.command == "start":
            if not Path(args.config).exists():
                from .setup import run_setup
                with exclusive_lock(args.data):
                    run_setup(args.config, args.data, stop)
                if stop.is_set():
                    return 0
            args.command = "run"
        config = Config.load(args.config)
        if args.command == "check":
            print("Configuration is valid; credentials and connectivity were not checked.")
            return 0
        if args.command == "health":
            heartbeat = json.loads((Path(args.data) / "health.json").read_text())
            return 0 if (heartbeat["review"] == 0 and
                         0 <= time.time() - heartbeat["success"] < max(180, config.poll_seconds * 3)) else 1
        if args.command == "discover":
            from .providers import KeepSource, AnyListDestination
            print(json.dumps({"keep": KeepSource(config).lists(),
                              "anylist": AnyListDestination(config).lists()}, indent=2))
            return 0
        with exclusive_lock(args.data):
            state = State(args.data, route(config))
            try:
                if args.command == "status":
                    print(json.dumps([dict(row) for row in state.rows()], indent=2))
                    return 0
                if args.command == "resolve":
                    state.resolve(args.item_id, args.decision)
                    print("Resolution saved. Run the bridge to resume processing.")
                    return 0
                from .providers import KeepSource, AnyListDestination
                bridge = None
                while not stop.is_set():
                    try:
                        if bridge is None:
                            bridge = Bridge(KeepSource(config), AnyListDestination(config), state)
                        reviews = bridge.poll()
                        temporary = Path(args.data) / "health.tmp"
                        temporary.write_text(json.dumps({"success": time.time(), "review": reviews}))
                        temporary.replace(Path(args.data) / "health.json")
                        logging.getLogger("synolistbridge").info("Poll successful; %d transfers need review", reviews)
                        if args.command == "once":
                            return 2 if reviews else 0
                    except sqlite3.Error:
                        logging.getLogger("synolistbridge").error("State database failed; stopping to preserve transfer safety")
                        return 1
                    except Exception as exc:
                        # Never print provider exception messages: they may contain credentials.
                        logging.getLogger("synolistbridge").error("Poll failed (%s); retrying after the polling interval",
                                                                 type(exc).__name__)
                        bridge = None
                        if args.command == "once":
                            return 1
                    stop.wait(config.poll_seconds)
                return 0
            finally:
                state.close()
    except Exception as exc:
        print(f"Command failed ({type(exc).__name__}). Check configuration, permissions, and credentials.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
