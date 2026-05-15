# Troubleshooting

Quick reference for common failure modes. Each entry: symptom, likely cause,
and fix. For live status information, see the
[Oliver /status page](https://oliver.multiworld.gg/status).

---

## Oliver didn't open a PR

Oliver opens an Index PR automatically within ~30 seconds of your
`Create and Release Python Package` workflow completing successfully. If no PR
appeared, work through this list:

**1. Oliver is not installed on your repo.**
Install the GitHub App: <https://github.com/apps/oliver-multiworld-squirrel>.
After installing, re-run the workflow from the Actions tab.

**2. `WORLD_FOLDER_NAME` is not set.**
Go to Settings → Secrets and variables → Actions → Variables and confirm
`WORLD_FOLDER_NAME` is present with the correct apworld slug. Oliver reads
this variable to know which world to look for.

**3. The workflow didn't complete successfully.**
Go to the Actions tab and check the run. A red check means the workflow
failed before Oliver saw a success event. Fix the workflow error and re-run.

**4. The `.whl` asset is missing from the release.**
If `publish-wheel` failed mid-run or the upload step was skipped, the release
may not have a `.whl` asset. Check the release page; if the asset is absent,
re-run the workflow.

**5. The `.whl` asset has no SHA256 digest.**
Oliver bails if the asset has no digest exposed by the GitHub API. This is
rare but can happen with very large assets or API timing issues. Check the
Oliver status page for a `asset_digest_missing` event against your world.
If it shows up, delete and re-upload the asset or recreate the release.

**6. Oliver is not installed on the Index repo.**
This is an operator-side issue, not an author-side issue. File an issue on
the Index repo if you have confirmed steps 1–5 are fine.

---

## Workflow failed: version mismatch

```
::error::Release tag 'clique-1.2.0' parses to version '1.2.0', but
worlds/clique/archipelago.json declares world_version='1.1.0'.
```

**Cause:** The version in your release tag and `world_version` in
`archipelago.json` disagree.

**Fix:** Either update `archipelago.json` to `"world_version": "1.2.0"` and
push a new commit, then delete and recreate the release on the updated tag;
or re-tag the release as `clique-1.1.0` to match the existing
`archipelago.json` value.

---

## Workflow failed: `must be python-entrypoint-reference`

**Cause:** A digit-led apworld slug (e.g. `2048`) causes a Python package
naming constraint. The entry-point emission in `shape_orphan.py` handles this
automatically in `@v3` — digit-led names skip entry-point emission rather than
emitting an invalid name.

**Fix:** If you see this error on `build.yml@v3` or `build-apworld.yml@v3`,
it is a bug in the workflow. Open an issue on
[`gen-pymod-release`](https://github.com/MultiworldGG/gen-pymod-release/issues).

---

## Karen left a comment with red checks

Karen posts a sticky review comment on the Index PR with a table showing which
checks passed, warned, or failed. A red check does not automatically block
merge — the human CODEOWNER decides whether to merge, ask for a fix, or
override.

Red checks are guidance, not a wall. If Karen flags something and you're not
sure what to do, ask in the PR comment thread. The CODEOWNER will advise.

Common red checks and their causes:

| Check | Common cause |
|---|---|
| `url_reachability` | The `module_location` URL is not yet reachable (e.g. release was just published, asset CDN propagation lag). Usually resolves on PR re-synchronise. |
| `bandit` | `subprocess` with `shell=True`, `exec()`, hardcoded credentials, or similar. Karen reports the specific line numbers. |
| `pip_audit` | A declared dependency has a known CVE. Upgrade the dep in `pyproject.toml` and cut a new release. |
| `no_network_at_import` | A top-level `import requests` or `urllib.request.urlopen()` call at module scope. Move network calls inside functions. |
| `size_sanity` | World source exceeds the size cap (default 250 MB). A human CODEOWNER can apply the `karen/size-cap-mb:<N>` label to the PR to raise the cap for this specific world. |

---

## I need to re-release the same tag

GitHub does not allow silently re-publishing a release tag at a different
commit SHA. The release tag is the immutability boundary.

**If you need to fix a broken release on the same version:**

1. Delete the release and the tag from GitHub.
2. Fix the issue, push the fix to your branch.
3. Recreate the release at the new commit with the same tag name.

Or, bump `world_version` in `archipelago.json`, use a new tag, and let the new
release supersede the old one. This is the cleaner option and avoids confusing
CI history.

---

## I deleted the release asset and want to re-upload

The workflow uploads without `--clobber`, so re-running the workflow on a
release that already has a `.whl` asset fails by design. If you deleted the
asset and want to re-upload:

1. Delete the asset: `gh release delete-asset <tag> <assetname>`
   (or do it from the GitHub release page UI).
2. Re-run the workflow from the Actions tab, or trigger `workflow_dispatch`.

Both steps are explicit manual actions — this is intentional. The SHA256
digest in the Index manifest pins exactly what was on disk when Oliver opened
the PR, and a silent overwrite would break that pin.

---

## Oliver opened the PR but the wrong world name appears

Oliver reads the `game` field from your `archipelago.json` to populate the
`game` field in the Index manifest. If the Index PR shows the wrong game name,
check `worlds/<apworld>/archipelago.json` in your repo at the release tag's
commit.

Common causes: the `game` field was misspelled, or the release was cut from a
branch where `archipelago.json` had a different value.

Fix: correct `archipelago.json`, bump `world_version`, and cut a new release.
Oliver will open an updated PR.

---

## The workflow ran on `workflow_dispatch` but Oliver didn't open a PR

Oliver's event filter checks:
- Workflow name: `Create and Release Python Package`
- Trigger event: `release` (not `workflow_dispatch`)

A `workflow_dispatch` run does not trigger Oliver. To trigger Oliver, you must
publish a GitHub Release (which fires the `release: published` event). Use
`workflow_dispatch` only for testing the build without publishing to the Index.
