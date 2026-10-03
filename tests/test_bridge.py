# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import tempfile
import unittest

from synolistbridge.bridge import Bridge
from synolistbridge.providers import Item
from synolistbridge.state import State, exclusive_lock


class Source:
    def __init__(self, items):
        self.current = {item.id: item for item in items}
        self.fail_completion = False

    def items(self):
        return list(self.current.values())

    def complete(self, item_id):
        if self.fail_completion:
            raise RuntimeError("Keep unavailable")
        item = self.current[item_id]
        self.current[item_id] = Item(item.id, item.text, True)


class Destination:
    def __init__(self):
        self.sent = []
        self.fail_add = False
        self.fail_validation = False

    def validate(self):
        if self.fail_validation:
            raise RuntimeError("AnyList unavailable")

    def add(self, text):
        self.sent.append(text)
        if self.fail_add:
            raise TimeoutError("Response lost after server accepted the item")
        return str(len(self.sent))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.route = {"source": "keep", "destination": "anylist"}
        self.state = State(self.temp.name, self.route)
        self.addCleanup(lambda: self.state.close())
        self.source = Source([Item("a", "milk", False)])
        self.destination = Destination()
        self.bridge = Bridge(self.source, self.destination, self.state)

    def restart(self):
        self.state.close()
        self.state = State(self.temp.name, self.route)
        self.bridge = Bridge(self.source, self.destination, self.state)

    def test_restart_does_not_duplicate_completed_transfer(self):
        self.bridge.poll()
        self.restart()
        self.source.current["a"] = Item("a", "milk", False)
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk"])

    def test_same_name_with_distinct_ids_is_transferred_twice(self):
        self.source.current["b"] = Item("b", "milk", False)
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk", "milk"])
        self.assertTrue(all(item.checked for item in self.source.items()))

    def test_completion_failure_retries_without_resending(self):
        self.source.fail_completion = True
        with self.assertRaises(RuntimeError):
            self.bridge.poll()
        self.assertEqual(self.state.get("a")["status"], "delivered")
        self.restart()
        self.source.fail_completion = False
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk"])
        self.assertTrue(self.source.current["a"].checked)

    def test_deletion_failure_retries_without_resending(self):
        from unittest.mock import Mock
        def delete(item_id):
            del self.source.current[item_id]
        self.source.complete = Mock(side_effect=RuntimeError("Keep unavailable"))
        with self.assertRaises(RuntimeError):
            self.bridge.poll()
        self.assertEqual(self.state.get("a")["status"], "delivered")
        self.restart()
        self.source.complete.side_effect = delete
        self.bridge.poll()
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk"])
        self.assertNotIn("a", self.source.current)
        self.assertEqual(self.state.get("a")["status"], "done")

    def test_uncertain_delivery_requires_review(self):
        self.destination.fail_add = True
        self.assertEqual(self.bridge.poll(), 1)
        self.restart()
        self.destination.fail_add = False
        self.assertEqual(self.bridge.poll(), 1)
        self.assertFalse(self.source.current["a"].checked)
        self.assertEqual(self.destination.sent, ["milk"])
        self.state.resolve("a", "delivered")
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk"])
        self.assertTrue(self.source.current["a"].checked)

    def test_interrupted_send_is_recovered_as_review(self):
        self.state.enqueue("a", "milk")
        self.state.prepare("a", "milk")
        self.restart()
        self.assertEqual(self.bridge.poll(), 1)
        self.assertEqual(self.destination.sent, [])

    def test_operator_retry_is_explicit(self):
        self.destination.fail_add = True
        self.bridge.poll()
        self.state.resolve("a", "retry")
        self.destination.fail_add = False
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["milk", "milk"])

    def test_checklist_edits_after_delivery_do_not_get_completed(self):
        self.source.fail_completion = True
        with self.assertRaises(RuntimeError):
            self.bridge.poll()
        self.source.current["a"] = Item("a", "bread", False)
        self.source.fail_completion = False
        self.assertEqual(self.bridge.poll(), 1)
        self.assertFalse(self.source.current["a"].checked)
        self.state.resolve("a", "skip")
        self.bridge.poll()
        self.assertFalse(self.source.current["a"].checked)

    def test_edit_before_first_send_uses_latest_text(self):
        self.state.enqueue("a", "milk")
        self.source.current["a"] = Item("a", "bread", False)
        self.bridge.poll()
        self.assertEqual(self.destination.sent, ["bread"])
        self.assertTrue(self.source.current["a"].checked)

    def test_removed_pending_item_is_not_sent(self):
        self.state.enqueue("a", "milk")
        self.source.current.clear()
        self.bridge.poll()
        self.assertEqual(self.destination.sent, [])
        self.assertEqual(self.state.get("a")["status"], "done")

    def test_destination_validation_failure_does_not_complete_source(self):
        self.destination.fail_validation = True
        with self.assertRaises(RuntimeError):
            self.bridge.poll()
        self.assertFalse(self.source.current["a"].checked)
        self.assertEqual(self.destination.sent, [])

    def test_database_cannot_be_reused_for_different_route(self):
        with self.assertRaises(ValueError):
            State(self.temp.name, {"source": "different"})

    def test_single_process_lock(self):
        with exclusive_lock(self.temp.name):
            with self.assertRaises(RuntimeError):
                with exclusive_lock(self.temp.name):
                    pass

    def test_resolution_rejects_unknown_or_completed_items(self):
        with self.assertRaises(ValueError):
            self.state.resolve("unknown", "retry")
        self.bridge.poll()
        with self.assertRaises(ValueError):
            self.state.resolve("a", "retry")


if __name__ == "__main__":
    unittest.main()
