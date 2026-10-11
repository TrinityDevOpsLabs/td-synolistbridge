# Generic Docker setup

[Back to README](README.md) · [Operations and troubleshooting](OPERATIONS.md)

SynoListBridge uses a standard Docker Compose workload. Synology is not required.
The container build targets x86-64 (`linux/amd64`) and ARM64 (`linux/arm64`).
You need Docker Engine and Docker Compose on your host, internet access, and
the Google Keep and AnyList accounts described in [What you need](README.md#what-you-need).
No incoming ports, host networking, or privileged container access are required.

## 1. Get the project and build

Download and extract the project's source archive, or clone the repository.
Open a terminal in the project folder containing `Dockerfile` and
`docker-compose.yml`, then run:

```sh
docker compose build
```

The included Compose file builds the image locally; no prebuilt registry image
is needed. Use `sudo` for Docker commands if your host requires it.

Keep the default storage settings for the easiest setup. Docker stores account
details, configuration, and transfer history in the persistent named volume
`synolistbridge_data`. The default container user is UID/GID `1000:1000`.

## 2. Complete interactive setup

**Before starting:** check off or remove any Keep items you do not want copied,
and stop any other bridge using those lists. The first transfer copies every
unchecked item from every checklist you select.

```sh
docker compose run --rm -it synolistbridge setup
```

Follow the prompts for Google and AnyList sign-in, then select your list pairs.
For the Google sign-in value, follow [Sign into Google](README.md#4-sign-into-google).
Review your choices before confirming **Save all list pairs and allow transfers?**
The `-it` options provide the interactive terminal required by setup.

This command saves your setup in the same volume used by the running service.
When setup finishes, start the service with the command below. The setup message
mentions a DSM project; on a generic Docker host, use Compose instead.

## 3. Start and test

```sh
docker compose up -d
docker compose logs --tail=50 synolistbridge
```

Add a new test item to each selected Keep checklist. Within about a minute, it
should appear in its AnyList destination and become checked off in Keep.
The bridge runs in the background and restarts unless explicitly stopped.

## Manage the bridge

Run these commands from the same project folder:

```sh
# View service status and recent logs.
docker compose ps
docker compose logs --tail=50 synolistbridge

# Stop or start transfers.
docker compose stop
docker compose start
```

To change polling, deletion, or category settings, create or edit `.env` beside
`docker-compose.yml` using the [README settings](README.md#optional-settings).
Apply the changes with:

```sh
docker compose up -d --force-recreate
```

Back up `synolistbridge_data`: it contains credentials and the record of items
already delivered. Keep its volume name and storage settings consistent between
setup and normal operation. `docker compose down` keeps the named volume;
`docker compose down -v` deletes it and loses your saved setup and history.
See [Backup and upgrades](OPERATIONS.md#backup-and-upgrades) before upgrading
or moving the installation.

For transfer troubleshooting and review commands, see
[Operations and troubleshooting](OPERATIONS.md).
