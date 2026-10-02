# Security

SynoListBridge stores transfer IDs, item text, and destination IDs in a local
SQLite database. Credentials are read from files mounted under `/run/secrets`.
They are not stored in the transfer database. Provider clients hold account
data and tokens in process memory while running.

Use a dedicated Google account and share only the intended Keep checklist
with it. A Google master token is not scoped to one note. Restrict access to
the project folder, secret files, configuration, database, and backups using
DSM permissions. Do not enable verbose third-party debug logging: provider
responses may contain account data or credentials.

Do not commit or upload `.env`, `config.json`, `secrets/`, `data/`, authentication
cookies/tokens, or account backups. Git and Docker ignore rules exclude the
local configuration and runtime directories. Configured paths and list names
can also expose private account information.

The container runs without root by default, uses a read-only root filesystem,
drops Linux capabilities. The advanced configuration publishes no network ports.
The easy configuration publishes HTTP port 8765 for a one-time browser wizard.
Its URL contains a random access token printed in startup logs. Protect that
link and those logs, perform setup only on a trusted private LAN, and never
forward the port from your router. The setup listener closes after configuration
is saved. Configured restarts run the bridge without reopening the wizard.
Wizard-created files have mode 0600 in the private Docker-managed volume;
backups of that volume contain account credentials.

For the advanced configuration, use a dedicated
UID/GID with only the folder permissions it needs. Local Compose secrets are
file mounts and do not encrypt the credentials at rest.

If a credential is exposed, treat it as compromised, revoke the relevant
provider sessions/credentials, and replace the local secret. If it was committed,
remove it from repository history as well. Removing the latest copy is not enough.

Report security issues privately to the maintainer through GitHub's private
vulnerability reporting if enabled. Do not include real credentials or shopping
data in public issues. This repository supplies no hosted security-reporting
service and no support email address has been configured.
