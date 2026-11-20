# Copyright 2026 Trinity DevOps LLC
# SPDX-License-Identifier: Apache-2.0
import logging

LOG = logging.getLogger("synolistbridge")


class Bridge:
    def __init__(self, source, destination, state, *, destination_factory=None):
        self.source, self.destination, self.state = source, destination, state
        self.destination_factory = destination_factory

    def poll(self):
        items = {item.id: item for item in self.source.items()}
        destination_validated = False
        for item in items.values():
            if not item.checked and item.text.strip():
                self.state.enqueue(item.id, item.text)
        for row in self.state.rows():
            item = items.get(row["id"])
            status = row["status"]
            if status == "pending":
                # An item removed or checked before delivery is no longer requested.
                if item is None or item.checked:
                    self.state.set(row["id"], "done")
                    continue
                # Check the destination only when there is work to send. Do
                # this before prepare(): a failed validation is safe to retry.
                if not destination_validated:
                    if self.destination is None:
                        self.destination = self.destination_factory()
                    self.destination.validate()
                    destination_validated = True
                self.state.prepare(row["id"], item.text)
                try:
                    destination_id = self.destination.add(item.text)
                except Exception:
                    self.state.set(row["id"], "review")
                    LOG.warning("Transfer %s needs review after an uncertain AnyList response", row["id"])
                    continue
                # If this local commit fails, the durable 'sending' record stops replay.
                self.state.set(row["id"], "delivered", destination_id)
                row = self.state.get(row["id"])
                status = "delivered"
            if status == "delivered":
                if item is not None and not item.checked:
                    # If text changed after delivery, leave it for manual review.
                    if item.text != row["text"]:
                        self.state.set(row["id"], "review")
                        LOG.warning("Transfer %s needs review because its source text changed", row["id"])
                        continue
                    self.source.complete(item.id)
                self.state.set(row["id"], "done")
                LOG.info("Transfer %s completed", row["id"])
        return sum(row["status"] == "review" for row in self.state.rows())
