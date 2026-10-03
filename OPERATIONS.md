# Operations and troubleshooting

[Back to README](README.md) · [Advanced setup](ADVANCED_SETUP.md)

Run the commands below from your project folder using its `docker-compose.yml`.
Stop the container before `status` or `resolve`. Interactive setup stores
configuration and credentials in
`/data/config.json` and `/data/secrets/` inside the Docker-managed volume.

## Reliability and manual review

SQLite records each transfer using the Keep item's stable ID. Separate Keep
items with identical text remain separate requests; the destination service
may apply its own duplicate handling. Completed IDs are not sent again.
To request an item again, create a new Keep item; unchecking or editing an
already completed item with the same ID does not resend it.

If adding to AnyList succeeds but checking or deleting the Keep item fails, that
action is retried
without sending another AnyList item. Network failures before a send are
retried on the polling interval. Account/list selection is bound to the data
directory: use a new directory if changing accounts or list IDs.

An error during an AnyList add, or a crash after starting the add, can leave
its outcome unknown. That item enters **review** and is not automatically
resent or checked. Other items can still transfer. An edit to the source
text after delivery also requires review. Health becomes unhealthy while
reviews are pending or successful polls stop; Docker does not automatically
restart containers solely because a health check fails.

Stop the main container before accessing transfer state, since only one
process may hold the data lock:

```sh
docker compose stop synolistbridge
docker compose run --rm synolistbridge status
```

Check AnyList manually, then resolve a reviewed transfer using the Keep item
ID printed by `status`:

```sh
# Item exists in AnyList: next poll checks off or deletes the Keep item according to your setting.
docker compose run --rm synolistbridge resolve ITEM_ID delivered

# Item is confirmed absent: explicitly authorize another send.
docker compose run --rm synolistbridge resolve ITEM_ID retry

# Leave the Keep item as-is and permanently stop processing this ID.
docker compose run --rm synolistbridge resolve ITEM_ID skip

docker compose up -d
```

`retry` can duplicate an item if you incorrectly conclude that the original
send failed. For changed source text, `skip` preserves the edited item;
create a new Keep item if that text should be sent as a new request. This is
not an exactly-once protocol: the two providers do not share a transaction
or a documented idempotency key. Avoid editing items while they transfer.

The `once` command exits 0 for a successful poll, 1 for failure, or 2 when
review is needed. `status` includes shopping item text; treat its output as
private. Bridge logs contain IDs and error types, not account credentials or
item text.

## Backup and upgrades

For the advanced setup, stop the bridge, then back up `data/`, `config.json`, `.env`, and `secrets/`
securely. Restore transfer state with the corresponding configuration. Losing
or restoring an old database can replay unchecked items or lose knowledge of
recent sends. Do not delete the database to troubleshoot an uncertain transfer.

For an upgrade, stop the project, back it up, replace the application files,
and rebuild/recreate the service. Preserve configuration, secrets, and data.
Do not use Container Manager's delete/clean operations without checking what
they remove. Dependency versions are pinned in `requirements.txt`; changes
should be tested before deploying.


For interactive setup, back up the stopped Docker-managed data volume using your
preferred Docker-volume backup tool. Preserve the Container Manager project
and volume during upgrades and NAS migration.

The default data volume is `synolistbridge_data`. The setup container and DSM
project must use the same volume or bind mount. To retry initial setup with
the project settings, use `docker compose --env-file .env run --rm -it synolistbridge setup`
when using `.env`, or `docker compose run --rm -it synolistbridge setup`
with the default settings.
Existing saved configuration is never overwritten by setup.

## Waiting for setup

On first startup, the default container stays running and logs that it is
waiting for configuration. Open its Terminal in DSM Container Manager,
launch `/bin/sh`, and run `synolistbridge setup`. After saving,
the bridge starts automatically. Cancellation leaves it waiting; rerun setup.
An unhealthy status is expected until configuration and the first successful
poll are complete. A stop request ends the waiting process cleanly.
