# Security

SynoListBridge stores transfer IDs, item text, and destination IDs in a local
SQLite database. Credentials are read from files under `/data/secrets` for interactive setup,
or mounted under `/run/secrets` for advanced setup.
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
and drops Linux capabilities. Neither configuration publishes network ports.
Interactive setup reads tokens and passwords with hidden terminal prompts;
run it from a trusted terminal. Setup-created files have mode 0600 in the
private Docker-managed volume; backups of that volume contain account credentials.

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
