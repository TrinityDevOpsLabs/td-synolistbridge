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

Keep `synolistbridge/__init__.py`'s `__version__`, the dated changelog section,
and the release tag consistent. The initial planned version is `0.1.0`.

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
   docker compose -f compose.easy.yaml config --quiet
   docker build -t synolistbridge:release-check .
   docker run --rm synolistbridge:release-check --help
   ```

   Require all tests to pass, including provider contract tests; do not accept
   skipped provider tests caused by missing dependencies. Confirm the GitHub
   checks pass for both `linux/amd64` and `linux/arm64`. Test the browser wizard
   and a real Keep → AnyList transfer on a supported NAS before publishing.
   Validation commands above do not start a bridge or modify real accounts.
3. Update `__version__`. Move completed entries in `CHANGELOG.md` from
   `Unreleased` into a dated version section, for example
   `## [0.1.0] - YYYY-MM-DD`. Use the actual release date.
4. Commit the release changes on the default branch.
5. Create a signed tag when Git signing is configured:

   ```sh
   git tag -s v0.1.0 -m "Release v0.1.0"
   ```

   Otherwise, create an annotated tag:

   ```sh
   git tag -a v0.1.0 -m "Release v0.1.0"
   ```

6. Push the branch and the specific tag:

   ```sh
   git push origin main
   git push origin v0.1.0
   ```

7. On GitHub, draft a release from the tag, generate release notes, review
   them, attach any intended assets, and publish it. The automatic source
   ZIP and `tar.gz` archives include the Dockerfile, Compose configurations,
   application, and notices. Users can build those sources in Container Manager.
   Do not attach populated data volumes or configured account files.
8. Mark unstable versions such as `v0.2.0-rc.1` as prereleases.

Never move or reuse a published version tag. Enable immutable releases in the
repository settings after confirming the release workflow. CODEOWNERS review
enforcement requires the repository's branch protection/ruleset settings;
the file alone does not enforce approvals.

## Release assets and images

The included GitHub workflow validates code and builds container images for
both architectures. It does not create releases or push registry images,
matching the Jellyfin utility's manually reviewed release process. Release
notes are categorized using `.github/release.yml` and pull-request labels.

If publishing prebuilt images later, tie them to the same immutable release
version and include both supported architectures and third-party notices.
No public registry location is configured in the current Compose files.
