# 🛒 SynoListBridge

Copies unchecked items from a Google Keep shopping checklist to AnyList,
then checks them off in Keep by default. Runs on your Synology NAS through Container
Manager.

Category matching is enabled by default. The bridge reads AnyList's saved
category rules for the destination list, so remembered categories still apply
after an item is deleted. For example, a saved rule for Creama → Dairy applies
when Creama is transferred again. Matching ignores capitalization and extra
whitespace and supports assignments to multiple category groups. If no saved
rule exists, the bridge reuses the category of a matching current list item
(including checked items), then a matching favorite. If there is no saved match, it uses AnyList's
[built-in grocery database](https://www.anylist.com/static/webapp/data/tag_data.json)
to match known grocery names and aliases to the list's built-in categories.
For example, Cottage Cheese maps to Dairy and Bacon maps to Meat. AnyList's
database maps Cheese Sticks to Frozen Foods (String Cheese maps to Dairy).
Custom saved rules take precedence, and renamed built-in categories retain
their names. Matching uses complete names, ignoring capitalization and extra
whitespace; arbitrary descriptions and names absent from the database may
remain uncategorized.

Saved rules, built-in grocery matches, and fallback matches are cached in `transfers.sqlite3` for the
configured account/list route. Set `BRIDGE_CATEGORY_REFRESH_INTERVAL=7d` in
`.env` to control refresh frequency (default **7 days**). It accepts the same
`30s`–`7d` duration range as polling. A fresh cache survives restarts; a missing
or expired cache refreshes on the next poll. Older caches refresh once after
upgrading to populate built-in matches. Successful refreshes replace old
rules, including removed rules. If a refresh fails, the bridge keeps using the
cache and retries after at most five minutes. Category changes in AnyList may
take up to the refresh interval to apply. Refreshes happen during polling, so a
longer poll interval can delay them further. Normal list validation still occurs
each poll; category caching reduces additional category and favorites requests.

Set `BRIDGE_CATEGORY_MATCHING=false` in `.env` to disable category matching;
items will then be added without an explicit category. Accepted values are
`true` and `false`. Recreate the container after changing either setting.

The poll interval defaults to **1 minute (60 seconds)**. Set
`BRIDGE_POLL_INTERVAL=2m` in `.env` to poll every two minutes. Use a whole number
followed by `s` (seconds), `m` (minutes), `h` (hours), or `d` (days), such as
`30s`, `1m`, `1h`, or `1d`. The minimum is `30s` and the maximum is `7d` (also
`168h`, `10080m`, or `604800s`). Bare numbers, decimals, and combined durations
such as `1h30m` are rejected. This replaces `BRIDGE_POLL_SECONDS` and overrides
`poll_seconds` in `config.json`, which remains a numeric value in seconds.
An unset or empty variable uses the configuration file's value. Rebuild and
recreate the container to apply these changes:

```sh
docker compose up -d --build
```

By **Trinity DevOps LLC**.

## Before you start

You will need:

- A Synology NAS with Container Manager installed (x86-64 or ARM64).
- Internet access on the NAS.
- A Google Keep checklist and an AnyList list.
- Your Google account email and access to sign in through a web browser.
- The email address and password you use to sign into your AnyList account.

### Google authentication

**You can use your own Google account.** If the checklist is already in that
account, you do not need to share it with anyone.

A separate Google account is **optional but recommended** because the master
token gives broad access to the account. If you choose a separate account,
share only your shopping checklist with it.

Setup gets the master token for you. You only need to copy a temporary
login cookie from your browser:

1. On your computer, open [Google's sign-in page](https://accounts.google.com/EmbeddedSetup)
   and sign into the Google account you will use for the bridge.
2. Click **I agree** if prompted. If the page keeps loading, continue anyway.
3. Open your browser's developer tools (usually **F12** or **Ctrl+Shift+I**).
   In Chrome or Edge, select **Application → Cookies**. In Firefox, select
   **Storage → Cookies**.
4. Select **accounts.google.com**, find **oauth_token**, and copy its **Value**.
   Keep it private and paste it only into the setup prompt in step 5 below.

You do not need to download another project or run a token-conversion command.
The app exchanges the cookie automatically and saves the master token; it does
not save the browser cookie. Neither a Google password nor an app password
should be entered into that prompt.

This uses the unofficial [gpsoauth login flow](https://github.com/simon-weber/gpsoauth#alternative-flow).
Company policies may block it. If the cookie is missing or login fails, follow
that guide for troubleshooting rather than changing your account's security settings.

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

5. **Answer the setup questions.** Enter your Google email and paste the
   `oauth_token` cookie copied above. For **AnyList account email**, enter the
   email address you use to sign into AnyList. For **AnyList account password**,
   enter that account's password. These are your AnyList login details; they
   may differ from your Google login. Use an AnyList account that can access
   the destination shopping list. Select each list by its number.
   Passwords and cookies show `*` characters while you type or paste; their
   actual values stay hidden. Use Backspace to correct an entry. Review the selected Keep list before typing `yes` to save.
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
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
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

GitHub Actions runs tests on pushes and pull requests. All tests must pass, and
total statement coverage across `synolistbridge` must be at least **80%**.
The coverage XML report is available as the `coverage-report` workflow artifact.
To enforce this before merging, configure a GitHub branch ruleset or branch
protection rule requiring the `test` status check.
