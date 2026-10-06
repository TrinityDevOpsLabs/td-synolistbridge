# 🛒 SynoListBridge

Send shopping items from Google Keep to AnyList using your Synology NAS.

Add an item to a Google Keep checklist, either yourself or through Google Home.
SynoListBridge copies it to the AnyList list you choose, then checks it off in
Keep. It checks for new items every minute by default.

- Connect one or more Keep checklists to AnyList lists.
- Use AnyList's remembered categories and built-in grocery categories.
- Shared-list members can receive AnyList's list-change notifications when their
  notification settings allow them.
- Choose whether delivered items are checked off or deleted in Keep.

**Items move from Keep to AnyList only.** Changes in AnyList are not copied back
to Keep.

By **Trinity DevOps LLC**. This project uses unofficial Google and AnyList
connections and is not affiliated with Google, AnyList, or Synology.

## What you need

- A Synology NAS with **Container Manager** installed (x86-64 or ARM64).
- Internet access on the NAS.
- A Google Keep **checklist**, rather than a plain text note.
- A Google account that can access that checklist.
- An AnyList account that can edit your destination list, and its email and password.
- A computer with a browser for the one-time sign-in steps.

You can use different accounts for Google Keep and AnyList.
If you use Google Home or a Nest speaker, first check that your voice commands
add items to the Keep checklist you want. SynoListBridge does not configure your
speaker.

## Set up on your Synology NAS

**Before starting:** check off or remove any Keep items you do not want copied.
Once setup finishes, the bridge copies **all unchecked items from every checklist
you select**. Stop any other bridge using those lists.

### 1. Copy the project to your NAS

Put the project folder in your Docker shared folder using File Station, for
example `/volume1/docker/SynoListBridge`. Your NAS may use a different volume.
Keep the project files together, including `Dockerfile` and `docker-compose.yml`.

Leave the storage settings at their defaults for the easiest setup. Docker will
keep your account details and transfer history in persistent storage called
`synolistbridge_data`. To use a regular NAS folder instead, follow
[the data-folder instructions](ADVANCED_SETUP.md#store-data-in-a-nas-folder).

### 2. Start the project

Open **Container Manager → Project → Create**. Choose a project name, select the
folder you copied, and use the included `docker-compose.yml`. Build and start
the project. This may take a few minutes.

### 3. Open setup

Select the running **synolistbridge** container and open **Terminal**. Launch
`/bin/sh`, then type:

```sh
synolistbridge setup
```

Setup asks for your Google email, a Google sign-in value, and your AnyList email
and password. The next section explains how to get the Google sign-in value.

### 4. Sign into Google

You can use your own Google account. A separate Google account is optional but
recommended: the saved sign-in token gives broad access to that account. If you
use a separate account, share your Keep checklist with it first.

On your computer:

1. Open [Google's sign-in page](https://accounts.google.com/EmbeddedSetup) and sign
   into the Google account you chose for the bridge.
2. Click **I agree** if asked. If the page keeps loading, continue with the steps below.
3. Open browser developer tools with **F12** or **Ctrl+Shift+I**.
4. In Chrome or Edge, open **Application → Cookies**. In Firefox, open
   **Storage → Cookies**.
5. Select **accounts.google.com**, find **oauth_token**, and copy its **Value**.
6. Paste that value into the container's setup prompt when requested.

Keep this value private. Use the cookie value in that prompt, rather than your
Google password or an app password. Setup converts it into a saved sign-in token
for you; it does not save the browser cookie. Passwords and cookies appear as `*`
while you enter them.

If the cookie is missing or sign-in fails, see the
[Google sign-in troubleshooting guide](https://github.com/simon-weber/gpsoauth#alternative-flow).
Work or school account policies may prevent this sign-in method.

### 5. Choose your lists

Enter your AnyList email and password when asked. Then select a Keep checklist
and the AnyList list that should receive its items. For example:

**Keep “Groceries” → AnyList “Weekly Shopping”**

To connect another checklist, answer `yes` to **Add another list pair?**
Otherwise, press Enter. Each Keep checklist can be selected once; several
checklists can send items to the same AnyList list. Unselected checklists are
left alone. All selected lists use the same Google and AnyList accounts.

Review the list choices, then answer `yes` to
**Save all list pairs and allow transfers?** Setup saves your choices, and the
running container begins copying items automatically.

### 6. Test it

Add a new test item to each selected Keep checklist. Within about a minute, it
should appear in the AnyList list you chose and become checked off in Keep.

For shared AnyList lists, also check that another member receives a notification.
They need shared-list change notifications enabled in AnyList and permission for
AnyList to show notifications on their phone.

You can now close the terminal. The container keeps running on your NAS.

## Everyday use

Use Container Manager to start or stop the bridge and view its **Log** tab.

To request an item again, create a **new item** in Keep. Editing or unchecking
an item that was already delivered will not send it again.

**Back up the bridge's saved data.** It includes your sign-in details and the
record of items already copied. Deleting it can lose your setup and cause items
to be sent again. See [backup and upgrade instructions](OPERATIONS.md#backup-and-upgrades).

To change which lists are connected, stop the container, back up and edit its
`config.json`, then restart. Keep the saved account details and transfer history.
A newly connected list copies its existing unchecked items when the bridge starts.
For configuration examples, see [Advanced setup](ADVANCED_SETUP.md).

## Optional settings

Put settings in a file named `.env` in your project folder. You can copy
`.env.example` as a starting point. After changing settings, **recreate the
container through your Container Manager project** so they take effect.

| Setting | Default | What it does |
| --- | --- | --- |
| `BRIDGE_POLL_INTERVAL` | `1m` | How often to check Keep for new items. |
| `BRIDGE_DELETE_KEEP_ITEMS` | `false` | Set to `true` to delete delivered items instead of checking them off. |
| `BRIDGE_CATEGORY_MATCHING` | `true` | Set to `false` to add items without choosing categories. |
| `BRIDGE_CATEGORY_REFRESH_INTERVAL` | `7d` | How often to update the saved AnyList category choices. |

For time settings, use a whole number followed by `s` (seconds), `m` (minutes),
`h` (hours), or `d` (days). Examples: `30s`, `2m`, `6h`, `7d`.
The allowed range is **30 seconds to 7 days**. Use one unit at a time, such as
`90m` rather than `1h30m`.

Deleting delivered items removes individual items, not the Keep checklist.
Items whose delivery needs review remain in Keep.

### How categories are chosen

The bridge first uses AnyList's saved category choice for that item. Otherwise,
it looks for a matching item already in the list, then a favorite, then a known
name in AnyList's grocery database. For example, Cottage Cheese maps to Dairy.
Capitalization and extra spaces do not affect matching. Unknown names may be
added without a category.

Category choices are saved to avoid downloading them repeatedly. A category
change in AnyList can take up to seven days to reach the bridge by default;
use a shorter `BRIDGE_CATEGORY_REFRESH_INTERVAL` if you need faster updates.
If a category refresh fails, the bridge keeps its previous choices and retries.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| “Waiting for configuration / setup to be completed” | Open the container terminal and run `synolistbridge setup`. |
| “Unhealthy” before setup finishes | Finish setup and wait for the first successful transfer check. |
| Setup was cancelled or sign-in failed | Run setup again. It will not overwrite an already saved setup. |
| An item does not arrive | Check the container's Log tab and confirm you selected the correct lists. |
| Items arrive, but no notification appears | Check the other member's AnyList notification settings and phone notification permissions. |
| `PermissionError` with a NAS data folder | Follow the [data-folder permission instructions](ADVANCED_SETUP.md#store-data-in-a-nas-folder). |

See [Operations and troubleshooting](OPERATIONS.md) for transfer review,
backups, upgrades, and diagnostic commands. See [Advanced setup](ADVANCED_SETUP.md)
for SSH commands, custom storage, and manual configuration.

## Development and releases

Use Python 3.12 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m coverage run -m unittest discover -s tests -v
.venv/bin/python -m coverage report
.venv/bin/python -m synolistbridge --help
```

Automated checks run tests and build container images for x86-64 and ARM64.
Tests must pass with at least **80%** code coverage. The checks do not publish
images. See [RELEASING.md](RELEASING.md) for the release process.

## Support the project

If SynoListBridge is useful to you, you can support its development on
[GitHub Sponsors](https://github.com/sponsors/TrinityDevOpsLabs).

## License

Copyright 2026 Trinity DevOps LLC. Licensed under [Apache-2.0](LICENSE).
See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for
upstream attribution. The original workflow came from
[google-home-anylist-bridge](https://github.com/jfolger/google-home-anylist-bridge).

Software licenses do not override Google or AnyList's service terms.
