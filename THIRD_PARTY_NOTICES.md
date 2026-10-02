# Third-party notices

SynoListBridge's new implementation is Copyright 2026 Trinity DevOps LLC,
licensed under Apache-2.0. This does not replace third-party copyright notices.

The original bridge's MIT notice is preserved in `licenses/original-bridge-MIT.txt`.
Its workflow informed this standalone implementation. The Home Assistant
integrations and macOS scripts are not bundled or required.

Runtime dependencies:

| Component | Version | License | Upstream |
| --- | --- | --- | --- |
| gkeepapi | 0.17.1 | MIT | https://github.com/kiwiz/gkeepapi |
| pyanylist | 0.0.6 | MIT | https://github.com/ozonejunkieau/pyanylist |
| anylist_rs (native dependency) | 0.3.3 in release source lock | MIT | https://github.com/phildenhoff/anylist_rs |
| gpsoauth | 2.0.0 | MIT | https://github.com/simon-weber/gpsoauth |
| future | 1.0.0 | MIT | https://github.com/PythonCharmers/python-future |
| pycryptodomex | 3.23.0 | BSD/public domain; see full notice | https://www.pycryptodome.org/ |
| requests | 2.34.2 | Apache-2.0 | https://requests.readthedocs.io/ |
| urllib3 | 2.8.0 | MIT | https://urllib3.readthedocs.io/ |
| charset-normalizer | 3.5.2 | MIT | https://github.com/jawah/charset_normalizer |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| certifi | 2026.7.22 | MPL-2.0 | https://github.com/certifi/python-certifi |

Notices from the installed Python distributions are preserved under `licenses/`.
These distributions also retain their license metadata in the container.
`licenses/native-rust-notices.tar.gz` preserves notices from the Rust crates
listed in pyanylist 0.0.6's published source archive lockfile. The corresponding
inventory records the crate source URLs, versions, licenses, and verified
SHA-256 checksums. This deliberately includes build-time and other-platform
dependencies as well as runtime dependencies; it is a source-lock inventory,
not a claim that every listed crate is linked into the Linux wheel.

The UUID internal crate shares its parent project's notices, supplied under
`licenses/uuid-rng-internal-1.22.0/`. The SystemConfiguration crates declare
MIT OR Apache-2.0 but omit standalone license files in their archives and
repository; the Apache-2.0 option and upstream Mullvad VPN credit are supplied
under `licenses/system-configuration-rs/`.

The Python/Alpine base image carries additional system components and their
notices; their licenses are not changed by this project.
