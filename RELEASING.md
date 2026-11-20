# Release process

This project uses Semantic Versioning and tags releases as `vMAJOR.MINOR.PATCH`,
matching Trinity DevOps LLC's Jellyfin Synology utility.

These instructions assume `SynoListBridge` is the root of its own GitHub
repository. While it is nested inside the original bridge repository,
its `.github` configuration does not control that parent repository. Do not
tag or publish the parent repository as a SynoListBridge release.

## Version selection

- Increment **MAJOR** for incompatible configuration, database, or CLI changes.
- Increment **MINOR** for backwards-compatible features.
- Increment **PATCH** for backwards-compatible fixes and documentation updates.

Choose the version in the GitHub Release. Its tag is the source of truth
for release automation; no source-file version bump is required.

## Publish a release

1. Confirm the working tree contains only the intended release changes and
   excludes account credentials, local configuration, and runtime databases.
2. Install the pinned dependencies and run the validation checks:

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m unittest discover -s tests -v
   .venv/bin/python -m compileall -q synolistbridge
   .venv/bin/python -m synolistbridge --help
   .venv/bin/python -m synolistbridge --config config.example.json check
   docker compose -f docker-compose.yml config --quiet
   docker compose -f docker-compose.advanced.yml config --quiet
   docker build -t synolistbridge:release-check .
   docker run --rm synolistbridge:release-check --help
   ```

   Require all tests to pass, including provider contract tests; do not accept
   skipped provider tests caused by missing dependencies. Confirm the GitHub
   checks pass for both `linux/amd64` and `linux/arm64`. Test interactive setup
   and a real Keep → AnyList transfer on a supported NAS before publishing.
   Validation commands above do not start a bridge or modify real accounts.
3. Merge the release changes into the default branch and confirm CI passes.
4. On GitHub, create a Release targeting that commit. Choose a version tag
   such as `v1.0.3` and use the tag as the release title. If your signing
   policy requires a pre-created tag, select that tag when creating the
   Release. Pushing a tag alone does not create a Release.
5. Attach any intended assets before publishing. The automatic source ZIP and
   `tar.gz` archives include the Dockerfile, Compose configurations, application,
   and notices. Do not attach populated data volumes or account files.
6. Mark unstable versions such as `v1.1.0-rc.1` as prereleases, then publish.
   GitHub Actions fills in the description using the published Release's tag.

Never move or reuse a published version tag. Enable immutable releases in the
repository settings after confirming the release workflow. CODEOWNERS review
enforcement requires the repository's branch protection/ruleset settings;
the file alone does not enforce approvals.

## Release assets and images

The CI workflow validates code and builds container images for both
architectures without pushing registry images.

`.github/workflows/release-notes.yaml` generates descriptions from every commit
since the nearest reachable earlier `v*` version tag, including direct pushes
and merged pull requests. The first release includes the full commit history.
`feat:`, `fix:`, and `docs:` commit subjects are grouped into Added, Fixed, and
Documentation; other commits appear under Other changes. Commit links and a
full changelog link are included. These are commit summaries, so descriptive
commit messages make useful release notes; the workflow does not summarize diffs.

Publishing a GitHub Release generates notes for stable releases and
prereleases. Branch pushes, tag pushes, and drafts do not generate release
notes. The workflow replaces the release description; manual edits will be
overwritten when it runs. `CHANGELOG.md` does not need to be updated.

Merge the workflow and script to the default branch before use. To retry an
existing published release, run **Release notes from commits** from the Actions
tab and enter its tag. The run verifies that the release is already published
before regenerating its notes. It does not create a release or move a tag.

`.github/release.yml` remains available for GitHub's optional **Generate release
notes** button, which categorizes merged pull requests using labels.

If publishing prebuilt images later, tie them to the same immutable release
version and include both supported architectures and third-party notices.
No public registry location is configured in the current Compose files.
