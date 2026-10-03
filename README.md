# 🛒 SynoListBridge

Copies unchecked items from a Google Keep shopping checklist to AnyList,
then checks them off in Keep by default. Runs on your Synology NAS through Container
Manager.

By **Trinity DevOps LLC**.

## Before you start

You will need:

- A Synology NAS with Container Manager installed (x86-64 or ARM64).
- Internet access on the NAS.
- A Google Keep checklist and an AnyList list.
- Your Google account email and **Google master token**.
- Your AnyList email and password.

The Google master token is a special account credential, not your Google
password. Getting it is the most involved part of setup. Use a separate Google
account, share your shopping checklist with it, and follow one of these guides:

- [gpsoauth token instructions](https://github.com/simon-weber/gpsoauth#alternative-flow)
- [Google Keep Sync authentication guide](https://github.com/watkins-matt/home-assistant-google-keep-sync#authentication-options)

Keep the token private: it can give access beyond your shopping checklist.
The token usually starts with `aas_et/`.

If you use Google/Nest voice commands, check that they add items to the right
Keep checklist before setting up the bridge. This app does not change your
speaker settings. Its connections to Google and AnyList use unofficial clients.

**This project is still in development; the first stable release has not been
published.**

## Set up in DSM

**Before you finish setup:** the bridge will copy **all existing unchecked
items** from your chosen Keep checklist. Check off or remove anything you do
not want copied. Stop any other bridge using that list.

1. **Copy the project to your NAS.** In File Station, put the project folder
   in your Docker shared folder, for example `/volume1/docker/SynoListBridge`.
   Use your NAS's actual volume if it is different. Keep all project files
   together, including `Dockerfile` and `docker-compose.yml`.
2. **Choose where to save data.** For the easiest setup, leave the storage
   settings alone; Docker manages the data for you. If you want an ordinary
   NAS folder instead, follow [the data-folder instructions](ADVANCED_SETUP.md#store-data-in-a-nas-folder)
   first. Keep your `.env` file in the project folder.
3. **Create the project.** Open **Container Manager → Project → Create**.
   Give it a name, select the copied project folder, and use the included
   `docker-compose.yml`. Build and start the project. This may take a few minutes.
4. **Open the container terminal.** Select the running `synolistbridge`
   container in Container Manager and open **Terminal**. Launch `/bin/sh`
   to open a command prompt, then enter:

   ```sh
   synolistbridge setup
   ```

5. **Answer the setup questions.** Enter your Google email and master token,
   then your AnyList email and password. Select each list by its number.
   Passwords and tokens do not appear while you type or paste them; that is
   normal. Review the selected Keep list before typing `yes` to save.
6. **Check that it works.** The bridge starts automatically after setup finishes.
   Add a new test item to Keep. Within about a minute, it should appear in
   AnyList and become checked in Keep (or disappear if deletion is enabled).

You do not need a web page or a separate image-build command. Once running,
you can close the terminal.

## If something goes wrong

- **The log says “Waiting for configuration / setup to be completed.”**
  The container is ready for setup. Open its terminal and run the command in step 4.
- **The container says “unhealthy” before setup is finished.** This is expected.
  It should become healthy after setup and the first successful sync.
- **You cancelled setup or entered the wrong credentials.** Run the setup command
  again. It will not replace a configuration that has already been saved.
- **You see `PermissionError` while using a NAS data folder.** Check the folder
  permissions and account settings in the [data-folder instructions](ADVANCED_SETUP.md#store-data-in-a-nas-folder).
- **The test item does not arrive.** Check the container's Log tab and see
  [Operations and troubleshooting](OPERATIONS.md).

## Optional: remove delivered items from Keep

By default, delivered items are checked off in Keep. To delete them instead,
add this line to `.env` in your project folder:

```dotenv
BRIDGE_DELETE_KEEP_ITEMS=true
```

Recreate the container through your DSM project to apply the change. Use
`false` to return to checking items off. This removes individual items after
successful delivery, leaving the Keep list intact. Items with uncertain
delivery remain in Keep for review. Previously completed items are unaffected.

## Everyday use

Manage start, stop, and logs in Container Manager. To request an item again,
create a **new item** in Keep. Editing or unchecking an item already delivered
will not send it again.

**Back up the data folder or Docker volume.** It contains your credentials and
transfer history. Deleting it can lose setup and cause items to be copied again.
See [backup and upgrade instructions](OPERATIONS.md#backup-and-upgrades).

For optional SSH setup commands, custom storage, or configuration files, see
[Advanced setup](ADVANCED_SETUP.md).

## 🛠️ Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m synolistbridge --help
```

Use Python 3.12 or later. The container uses Alpine for the pinned pyanylist
ARM64 wheel. Tests use mocks; provider contract tests require the pinned
packages. Test with real accounts on a supported NAS before production.

When this project is the root of its own GitHub repository, the included CI
workflow tests Python and builds x86-64 and ARM64 images. It does not publish
images. See [RELEASING.md](RELEASING.md) for the release process.

## License

Copyright 2026 Trinity DevOps LLC. Licensed under [Apache-2.0](LICENSE).
See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for
upstream attribution. The original workflow came from
[google-home-anylist-bridge](https://github.com/jfolger/google-home-anylist-bridge).

This project is not affiliated with Google, AnyList, or Synology. Software
licenses do not override the providers' service terms.
