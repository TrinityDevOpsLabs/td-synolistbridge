# Advanced setup

[Back to README](README.md) · [Operations and troubleshooting](OPERATIONS.md)

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
   DSM permissions. Follow the [data folder permission steps](#store-data-in-a-nas-folder),
   including an explicit Synology ACL grant and access through parent folders;
   Unix mode bits alone may not allow container writes. Compose file secrets on DSM are local file mounts, not
   an encrypted vault. Keep the project on a local NAS filesystem.
5. Put your Google and AnyList emails in `config.json`. Leave the list-ID
   placeholders temporarily. Set your timezone in `.env`.
6. Using File Station, copy `docker-compose.advanced.yml` over the included
   `docker-compose.yml`. This replaces the interactive setup with the local-file
   configuration. In Container Manager → **Project → Create**, select the
   project folder. Build the project, but do not start the service until list
   discovery and the first-run check below are complete.

### Google authentication

The interactive [README setup](README.md#google-authentication) exchanges a
browser cookie automatically. For this manual-file configuration, obtain the
master token using the [upstream token exchange instructions](https://github.com/simon-weber/gpsoauth#alternative-flow).
The `google_master_token` file must contain the resulting master token, not
the browser cookie.

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
container access. The default interactive setup also requires no incoming ports.


## Choose a data folder for interactive setup

### Store data in a NAS folder

The default Docker-managed volume needs no host-directory permissions setup.
For a repo-local or other custom data directory, complete these steps **before
running setup or starting the project**:

1. Create the directory, for example `mkdir -p ./data` from the project folder.
   Use a local NAS filesystem.
2. Choose the host/DSM account that will own the data. Through SSH, run
   `id <username>` and note its numeric UID and GID.
3. Create or edit `.env` in the project folder:

   ```dotenv
   BRIDGE_DATA_SOURCE=./data
   BRIDGE_UID=1026
   BRIDGE_GID=100
   ```

   Replace the example IDs with your account's IDs. `BRIDGE_DATA_SOURCE` can
   also be an absolute directory path. Relative paths resolve from the project
   folder. `.env` and the repo-local `data/` directory are gitignored; add an
   ignore rule if you choose another directory inside the repository.
4. Grant that account read/write access to the directory and its contents.
   On Synology, use **File Station → directory → Properties → Permission**
   to add an explicit read/write permission for that account and apply it to
   the directory, subfolders, and files. Ensure the account can traverse parent
   folders. Inherited Synology ACLs can block writes even when Unix mode bits
   show `777`; changing `chmod` alone may not fix this. Restrict access to the
   selected account and administrators because this directory stores credentials.
5. Return to the DSM setup steps in the README. Run setup from the container terminal;
   it uses the same physical directory and UID/GID as the running container.
   For later `.env` changes, recreate the container so the new mount and
   UID/GID take effect; restarting alone does not apply these changes.

A startup `Command failed (PermissionError)` can mean the container cannot
create `/data/bridge.lock`. Check the configured UID/GID and directory ACLs
before troubleshooting credentials.

Back up the custom data directory. Changing the storage setting does not
migrate existing data; stop the bridge and copy any existing volume contents
first, preserving access for the configured account. Remove `BRIDGE_DATA_SOURCE`
to return to the default `synolistbridge_data` Docker-managed volume; its default container identity
is UID/GID `1000:1000`.

### Alternative: setup before starting the DSM project

If you prefer SSH, build from the copied project folder first:

```sh
docker build -t synolistbridge:local .
```

Choose **one** setup command:

**With a `.env` file (including a physical data directory):** complete the
[directory and permission steps above](#store-data-in-a-nas-folder)
first, then run:

```sh
docker compose --env-file .env run --rm -it synolistbridge setup
```

This applies the data mount, UID/GID, and volume name from the Compose
configuration. Keep `.env` beside `docker-compose.yml` so the DSM project
uses the same settings. Run from this folder; relative paths such as
`./data` resolve against the Compose project folder. Exported shell
variables can override `.env` settings; avoid conflicting `BRIDGE_*`
variables when running setup.

**Without a `.env` file (default Docker-managed volume):** run:

```sh
docker run --rm -it --mount type=volume,source=synolistbridge_data,target=/data \
  -e BRIDGE_CONFIG=/data/config.json synolistbridge:local setup
```

Use this only with the default data volume and UID/GID `1000:1000`.
`docker run --env-file .env` alone does **not** apply `BRIDGE_DATA_SOURCE`
as a mount or `BRIDGE_UID`/`BRIDGE_GID` as the container user; Compose
handles these host-side settings for the `.env` workflow.

Use `sudo` for Docker commands if required by your DSM account. `-it` is
required for interactive prompts; passwords and tokens are hidden.

Then create and start the project in DSM Container Manager.


## Keep existing Docker volumes when upgrading

Existing installations using a Compose-generated volume name must keep that
volume: before upgrading, set `BRIDGE_VOLUME_NAME` in `.env` to its actual
Docker volume name (find it in the existing container's mounts). The new
fixed default name does not migrate an older volume automatically.

For multiple Keep → AnyList pairs, replace the two top-level list IDs with a
`lists` array as shown in [Multiple list pairs](README.md#multiple-list-pairs).
Review every source checklist before starting: the first poll transfers all
existing unchecked items from every configured pair.
