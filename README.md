# SynoListBridge

**Trinity DevOps LLC** — a standalone Google Keep → AnyList shopping-list
bridge for Synology DSM Container Manager.

Google/Nest captures voice shopping items in a Google Keep checklist.
SynoListBridge polls that checklist, adds unchecked items to your selected
AnyList list, then checks the Keep copies after successful delivery.
Home Assistant, HACS, and a virtual machine are not required.

## Requirements

- A Synology model and DSM installation supporting Container Manager
- An x86-64 or ARM64 CPU; this image uses Python 3.12 on Alpine Linux
- Outbound internet access to Google and AnyList
- A Google Keep checklist reachable by the bridge account
- A Google master token and your AnyList email/password

These are unofficial service clients. Verify that your Google/Nest voice
commands actually create items in the selected Keep checklist before setup.
Account, region, and voice assistant behavior can change. This app does not
configure your speaker or Google account's list destination.

## Easy DSM setup — no SSH

For production, download the source ZIP or `tar.gz` from a tagged stable
GitHub Release and review its release notes. Use the default branch only for
testing unreleased changes. This project has not published its initial release
yet; the current files are development sources.

1. Copy this project folder to `/volume1/docker/SynoListBridge` using DSM
   **File Station**.
2. In **Container Manager → Project → Create**, select that folder and upload
   `compose.easy.yaml` as the Compose source. Build and start the project.
   If DSM requires a particular source filename, copy it to `docker-compose.yml`
   using File Station and select that copy.
3. Open the container's **Log** tab. Find the private setup link beginning
   `http://YOUR-NAS-IP:8765/` and replace `YOUR-NAS-IP` with your NAS's LAN IP.
4. In your browser, enter your Google email/master token and AnyList
   email/password. The wizard connects to both services and provides dropdowns
   for selecting the lists. Review the first-transfer notice and click
   **Save and start bridge**.

The service then starts automatically. No manual configuration file, secret
files, UID/GID lookup, or command-line list discovery is needed. App data and
credentials live in a Docker-managed volume owned by the container user.
Your Google master token still needs to be generated separately using the
authentication instructions below; this app cannot bypass Google's login.

The setup URL has a random access token. Treat that link and initial logs as
private. Port 8765 uses HTTP: perform setup on a trusted private LAN, allow
that port in the DSM firewall for your LAN if needed, and do not forward it
from your router. The listener closes after saving; restarting an already
configured container does not reopen the wizard. During initial setup, the
container may show unhealthy until its first successful bridge poll.

**Keep the Container Manager project and its data volume.** Removing the volume
deletes credentials and transfer history. Back up the stopped volume through
your preferred Docker-volume backup tool before upgrades or NAS migration.
The easy setup uses `/data/config.json` and `/data/secrets/`; these paths differ
from the advanced file layout below.

For later CLI maintenance with this layout, use
`docker compose -f compose.easy.yaml ...` in the commands below (or the source
filename DSM actually saved). Stop the container before `status` or `resolve`.

## Advanced setup — local files and SSH

1. Copy this entire directory to a shared folder, for example
   `/volume1/docker/SynoListBridge`.
2. Copy `config.example.json` to `config.json` and `.env.example` to `.env`.
3. Create `data/` and `secrets/`. In `secrets/`, create two plain-text files:
   `google_master_token` and `anylist_password`, each containing one credential
   on one line. Do not put quotes around credentials. Use a local editor;
   avoid placing them in shell commands or command history.
4. Create/select a dedicated DSM user. Set `BRIDGE_UID` and `BRIDGE_GID` in
   `.env` to that user's numeric IDs (`id <username>` through SSH). Grant it
   write access to `data/` and read access to `config.json` and both secret
   files. Restrict secret/data access to that user and administrators through
   DSM permissions. Compose file secrets on DSM are local file mounts, not
   an encrypted vault. Keep the project on a local NAS filesystem.
5. Put your Google and AnyList emails in `config.json`. Leave the list-ID
   placeholders temporarily. Set your timezone in `.env`.
6. In Container Manager → **Project → Create**, select the project folder
   and its `compose.yaml`. Build the project, but do not start the service
   until list discovery and the first-run check below are complete. Some
   DSM versions expect `docker-compose.yml`; rename `compose.yaml` if needed.

### Google authentication

Use a dedicated Google account, share only your shopping checklist with it,
and obtain that account's master token using the current
[gpsoauth instructions](https://github.com/simon-weber/gpsoauth#alternative-flow)
or [Google Keep Sync authentication guide](https://github.com/watkins-matt/home-assistant-google-keep-sync#authentication-options).
The token usually starts with `aas_et/`. Browser OAuth cookies are not the
credential this service expects. Authentication changes are maintained upstream.
The token is not restricted to this single checklist.

### Discover and select the lists

For one-time setup commands, use SSH and run from the project folder:

```sh
docker compose build
docker compose run --rm synolistbridge check
docker compose run --rm synolistbridge discover
```

`discover` prints list IDs and names, without changing either service. Copy
the appropriate IDs into `keep_list_id` and `anylist_list_id` in `config.json`.
Use `sudo` for Docker commands if required by your DSM account. Older DSM
installations may use `docker-compose` instead of `docker compose`.

**First run transfers every existing unchecked, nonempty item in the selected
Keep checklist.** Review that list and remove/check anything you do not want
copied before the first transfer. Disable any previous Home Assistant bridge
for this list to avoid two independent writers.

```sh
docker compose run --rm synolistbridge once
docker compose up -d
docker compose logs --tail=50 synolistbridge
```

Add a new test item in Keep or through your speaker. It should appear in
AnyList after the next poll (60 seconds by default), and the Keep copy should
become checked. Container Manager can manage start/stop/logs after setup.
The advanced setup needs no incoming ports, host networking, or privileged
container access. Easy setup publishes port 8765 for the one-time wizard.

## Reliability and manual review

SQLite records each transfer using the Keep item's stable ID. Separate Keep
items with identical text remain separate requests; the destination service
may apply its own duplicate handling. Completed IDs are not sent again.
To request an item again, create a new Keep item; unchecking or editing an
already completed item with the same ID does not resend it.

If adding to AnyList succeeds but checking Keep fails, checking Keep is retried
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
# Item exists in AnyList: next poll only completes the Keep copy.
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
item text. The easy setup's initial log also contains the private wizard link.

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

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m synolistbridge --help
```

Python 3.12 or later is required by pyanylist. Its published Linux ARM64
wheel for this version is musllinux, which is why the deployment uses Alpine.
The bridge tests run without dependencies; provider contract tests require
the pinned packages. Tests use local objects/mocks and do not authenticate
to real accounts. A real account/NAS smoke test is required before production.
The included `.github/workflows/ci.yaml` tests Python and builds both container
architectures when this directory becomes the root of its own GitHub repository.
It does not publish images and is not active from this nested directory.
Repository ownership and generated release-note categories match the Jellyfin
utility. See [RELEASING.md](RELEASING.md) for versioning, validation, tags, and
the manual GitHub release process.

## License and attribution

Copyright 2026 Trinity DevOps LLC. New implementation: **Apache-2.0**, matching
the company's [Jellyfin Synology backup utility](https://github.com/TrinityDevOpsLabs/backup-restore-utility-for-jellyfin-synology).
See `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md` for preserved upstream
notices. The original workflow came from
[google-home-anylist-bridge](https://github.com/jfolger/google-home-anylist-bridge).
This project is not affiliated with Google, AnyList, or Synology. Software
licenses do not grant permission beyond the providers' service terms.

Official deployment references:
[Synology Container Manager](https://www.synology.com/en-us/dsm/packages/ContainerManager),
[gkeepapi](https://gkeepapi.readthedocs.io/en/latest/),
[pyanylist](https://github.com/ozonejunkieau/pyanylist).
