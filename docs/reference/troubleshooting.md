# Troubleshooting

Quick reference for common failure modes. Each entry: symptom, likely cause,
and fix. For live status information, see the
[Oliver /status page](https://oliver.multiworld.gg/status).

---

## Oliver didn't open a PR

Oliver opens an Index PR automatically within ~30 seconds after a published
release whose build workflow has attached a `.whl` asset from
`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`. If no PR
appeared, work through this list:

**1. Oliver is not installed on your repo.**
Install the GitHub App: <https://github.com/apps/oliver-multiworld-squirrel>.
After installing, publish the release or re-run the completed release workflow
from the Actions tab.

**2. The release tag does not include the apworld name.**
Release tags must be `<apworld>-<version>`, for example `myclgm-1.2.0`.
Oliver parses the apworld from the tag prefix.

**3. The workflow didn't complete successfully.**
Go to the Actions tab and check the run. A red check means the workflow
failed before Oliver saw a success event. Fix the workflow error and re-run.

**4. The release is still a draft.**
Draft releases do not fire the `release: published` event. Open the draft
release, review it, and click **Publish release**.

**5. The `.whl` asset is missing from the release.**
If `publish-wheel` failed mid-run or the upload step was skipped, the release
may not have a `.whl` asset. Check the release page; if the asset is absent,
re-run the workflow.

**6. The `.whl` asset has no SHA256 digest.**
Oliver bails if the asset has no digest exposed by the GitHub API. This is
rare but can happen with very large assets or API timing issues. Check the
Oliver status page for a `asset_digest_missing` event against your world.
If it shows up, delete and re-upload the asset or recreate the release.

**7. The release was created by another GitHub Actions workflow using `GITHUB_TOKEN`.**
GitHub
[will not trigger a second workflow from a release event created by the default `GITHUB_TOKEN`](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow).
Oliver's `release.published` handler still fires, but the release-triggered
build workflow never runs, so no `.whl` asset is attached to the release and
Oliver bails. To fix it:

- Publish the release manually from the GitHub UI instead of letting another
  workflow create it; or
- Have the release-creating workflow use a
  [fine-grained PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
  with `contents: write` + `workflows: write` (stored as a
  [repository secret](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
  and passed as `token: ${{ secrets.RELEASE_PAT }}`), or a GitHub App token
  minted by
  [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token);
  or
- Call the reusable build job directly from the workflow that creates the
  release, rather than relying on a downstream workflow to pick up the
  release event.

**8. Oliver is not installed on the Index repo.**
This is an operator-side issue, not an author-side issue. File an issue on
the Index repo if you have confirmed steps 1–7 are fine.

---

## Workflow failed: version mismatch

```
::error::Release tag 'myclgm-1.2.0' parses to version '1.2.0', but
worlds/myclgm/archipelago.json declares world_version='1.1.0'.
```

**Cause:** The version in your release tag and `world_version` in
`archipelago.json` disagree.

**Fix:** Either update `archipelago.json` to `"world_version": "1.2.0"` and
push a new commit, then delete and recreate the release on the updated tag;
or re-tag the release as `myclgm-1.1.0` to match the existing
`archipelago.json` value.

---

## Workflow failed: `must be python-entrypoint-reference`

**Cause:** A digit-led apworld name (e.g. `2048`) causes a Python package
naming constraint. The entry-point emission in `shape_tree.py` handles this
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
2. Re-run the release workflow from the Actions tab.

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

Oliver listens to two webhook events:

- `release.published` — fired when someone clicks **Publish release** on a
  draft (or creates a release directly). Oliver reads the release, waits for
  the `.whl` asset to appear, and opens the Index PR.
- `workflow_run.completed` — fired when a workflow run finishes. Oliver
  filters for runs triggered by a `release` event that successfully called
  `MultiworldGG/gen-pymod-release/.github/workflows/build.yml`.

A `workflow_dispatch` run fires neither: there is no published release, and
the workflow run was not triggered by a `release` event. To trigger Oliver,
you must publish a GitHub Release. Use `workflow_dispatch` only for testing
the build without publishing to the Index.

---

## I created the draft release, but nothing ran

That is expected. Draft releases are not release events for this flow.

Review the draft release in GitHub and click **Publish release**. Publishing
the draft fires the `release: published` event, starts the asset-building
workflow, and gives Oliver the successful workflow run it needs to open the
Index PR.
