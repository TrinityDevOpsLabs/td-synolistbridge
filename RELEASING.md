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

Keep `synolistbridge/__init__.py`'s `__version__` and the release tag consistent. The examples below use `v1.0.1`; substitute the version being released.

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
3. Update `__version__`. Release descriptions are generated from commit
   messages automatically; updating `CHANGELOG.md` is optional.
4. Commit the release changes on the default branch.
5. Create a signed tag when Git signing is configured:

   ```sh
   git tag -s v1.0.1 -m "Release v1.0.1"
   ```

   Otherwise, create an annotated tag:

   ```sh
   git tag -a v1.0.1 -m "Release v1.0.1"
   ```

6. Push the branch and the specific tag:

   ```sh
   git push origin main
   git push origin v1.0.1
   ```

7. Pushing a version tag automatically creates a draft release with notes from
   commit messages. Open that draft on GitHub, review the notes, attach any
   intended assets, and publish it. If you create and publish a release directly
   through GitHub, the workflow fills its description after publication.
   The automatic source ZIP and `tar.gz` archives include the Dockerfile,
   Compose configurations, application, and notices. Users can build those
   sources in Container Manager. Do not attach populated data volumes or
   configured account files.
8. Mark unstable versions such as `v0.2.0-rc.1` as prereleases.

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

Pushing a version tag creates a draft release automatically or updates its
existing release. Publishing a release regenerates the notes for both stable
releases and prereleases. Direct branch pushes alone do not create releases.
The workflow replaces the entire description; manual edits will be overwritten
on publication or another run. `CHANGELOG.md` does not need to be updated.

Commit and push the workflow and script to the default branch before use, and
include the workflow in future release tags. To backfill an existing release
or saved draft, run **Release notes from commits** manually from the Actions tab
with its tag. No tag needs to be moved. Check the Actions run if notes do not
appear after pushing a tag or publishing a release.

`.github/release.yml` remains available for GitHub's optional **Generate release
notes** button, which categorizes merged pull requests using labels.

If publishing prebuilt images later, tie them to the same immutable release
version and include both supported architectures and third-party notices.
No public registry location is configured in the current Compose files.
