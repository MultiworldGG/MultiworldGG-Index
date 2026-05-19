# Reusable workflow reference

All reusable workflows live in
`MultiworldGG/gen-pymod-release/.github/workflows/` and are called via
`uses:` in your per-world repo's workflow file. Pin to `@v3` — patch updates
fast-forward the major-version tag. Pin to a full SHA for complete
reproducibility.

---

## `build.yml@v3` — builds the wheel

Builds a pip-installable wheel from `worlds/<apworld>/` and uploads it as a
release asset. This is the primary workflow Oliver consumes when opening an
Index PR.

**Oliver trigger (easy / default path):** Oliver subscribes to the
`release.published` webhook event on installed repos. When you publish a
GitHub Release with a tag of the form `<apworld>-<version>`, Oliver waits for
the release-triggered workflow to attach a `.whl` asset that came from
`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`, then reads the
asset URL and SHA256 digest and opens the Index PR.

**Oliver trigger (advanced / custom-caller path):** Oliver also listens to
`workflow_run.completed`. This covers repos that wire up a custom caller
workflow on top of the reusable `build.yml`. The completed workflow run must
be triggered by a `release` event, must complete successfully, and must call
`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`. The caller
workflow name does not matter. Manual `workflow_dispatch` runs are useful for
dry-runs, but Oliver ignores them either way (no published release, no
release-event workflow run).

!!! note "Draft releases do not trigger the build"
    Creating a draft release is only the review step. The `release.published`
    event fires when someone clicks **Publish release** on that draft. That is
    when GitHub Actions builds and attaches the assets, and when Oliver can see
    the wheel.

!!! warning "Releases created by another workflow using `GITHUB_TOKEN`"
    If another GitHub Actions workflow creates the GitHub Release using the
    default `GITHUB_TOKEN`, GitHub
    [will not trigger a second workflow from that release event](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow).
    Oliver's `release.published` handler still fires, but the release-triggered
    build workflow never runs, so no `.whl` asset is attached and Oliver bails.

    To make the chained build actually run, the workflow that creates the
    release must use a token that is allowed to trigger workflows:

    - A [fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
      with `contents: write` and `workflows: write` on the per-world repo,
      [stored as a repository secret](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
      such as `secrets.RELEASE_PAT`, and passed to the release-creating step as
      `token: ${{ secrets.RELEASE_PAT }}`; or
    - A GitHub App token minted by
      [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token),
      from a GitHub App that has the `Contents` and `Workflows` write
      permissions on the per-world repo.

    Alternatively, publish the release manually from the GitHub UI, or call
    these reusable jobs directly from the workflow that creates the release
    (rather than relying on a second workflow to pick up the release event).

### Minimal usage

This includes an optional `workflow_dispatch` dry-run path for power users. The
usual author path is still draft release -> **Publish release**.

```yaml
name: Create and Release Python Package
on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      apworld:
        description: "World folder under worlds/ to build"
        required: true
        type: string
      source_ref:
        description: "Git ref to build for a manual dry-run"
        required: false
        type: string

permissions:
  contents: write

jobs:
  publish:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      apworld: ${{ inputs.apworld || '' }}
      source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}
```

### Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| `apworld` | no | `""` | World folder name under `worlds/<apworld>/`. Ignored on release events, where the apworld is parsed from the release tag prefix. Required for manual/non-release dry-runs. |
| `source-ref` | no | Release tag (on `release` event), else `github.sha` | Git ref of your repo to build from. |
| `dry-run` | no | `false` | Build and shape the wheel but skip the release-asset upload. Useful for testing the workflow without a real release. |

### Outputs

A single `.whl` file attached to the GitHub release as an asset. The asset
filename is `<dist>-<world_version>-py3-none-any.whl`.

The asset URL has the form:

```
https://github.com/<owner>/<repo>/releases/download/<release_tag>/<dist>-<world_version>-py3-none-any.whl
```

Oliver appends `#sha256=<hex>` to this URL in the Index manifest so pip
verifies the bytes at install time.

### Tag format requirement

The release tag must be `<apworld>-<version>` where `<version>` matches
`world_version` in `archipelago.json`. For example, tag `myclgm-1.2.0`
requires `"world_version": "1.2.0"` in `worlds/myclgm/archipelago.json`.

The draft-release helper creates this tag from `archipelago.json`. On publish,
the workflow fails with a clear error message if the tag and
`archipelago.json` disagree.

On manual/non-release runs there is no tag-declared version to compare, so the
workflow builds the `apworld` input at `source-ref` and skips the version-skew
check.

### Re-upload constraint

The workflow does not use `--clobber`. If a `.whl` asset already exists on
the release, re-running the workflow fails. This is deliberate: the asset
bytes are pinned by the `#sha256=<hex>` fragment in the Index manifest, and a
silent overwrite would invalidate that pin without warning.

To fix a transient build failure on an existing release:

1. `gh release delete-asset <tag> <assetname>` to remove the existing asset.
2. Re-run the workflow.

Or delete and recreate the entire release. Both are explicit human actions.

---

## `build-apworld.yml@v3` — builds the `.apworld` file

Checks out a MultiworldGG instance, installs your world source into it, runs
`python Launcher.py "Build APWorlds" -- "<game>"`, and uploads the resulting
`.apworld` file as a release asset.

This workflow is for players who install `.apworld` files directly into their
`custom_worlds/` folder. It is not required for the Index release — `build.yml`
handles that.

### Minimal usage

This job is normally paired with the `build.yml@v3` job in the same
release-triggered caller workflow. The `apworld` and `apworld-source-ref`
inputs below are for optional manual dry-runs.

```yaml
jobs:
  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "My Cool Game"
      apworld: ${{ inputs.apworld || '' }}
      apworld-source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}
```

### Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| `game` | yes | — | The game's display name, exactly as it appears in `archipelago.json`. Passed to `Launcher.py "Build APWorlds" -- "<game>"`. |
| `mwgg-ref` | no | `"main"` | Ref in canonical `MultiworldGG/MultiworldGG` to check out as the Launcher host. This does not resolve against the caller's fork. Ignored when `from-fork: true`. |
| `from-fork` | no | `false` | Set to `true` when the caller is an Archipelago fork (a full source tree with its own `Launcher.py` at the root). Skips the canonical MWGG checkout and builds from the caller's tree. `mwgg-ref` is ignored. |
| `apworld` | no | `""` | World folder name under `worlds/<apworld>/`. Ignored on release events, where the apworld is parsed from the release tag prefix. Required for manual/non-release dry-runs. |
| `apworld-source-ref` | no | Release tag (on `release` event), else `github.sha` | Your world repo's ref to check out as the world source. |
| `dry-run` | no | `false` | Build the `.apworld` but skip the release-asset upload. |

### How it works

When `from-fork: false` (default — standalone-repo callers):

1. Checks out canonical `MultiworldGG/MultiworldGG` at `mwgg-ref` into `mwgg/`.
2. Checks out your repo at `apworld-source-ref` into
   `mwgg/worlds/<apworld>/` (a transient overlay — your world source is dropped
   into the MultiworldGG tree for the Launcher to find it).
3. `pip install -r mwgg/requirements.txt`.
4. `python mwgg/Launcher.py "Build APWorlds" -- "<game>" --skip_open_folder`.
5. Uploads `mwgg/build/apworlds/<apworld>.apworld` as a release asset.

When `from-fork: true` (Archipelago fork callers):

1. Checks out your fork at `apworld-source-ref` into `mwgg/`. No canonical
   MultiworldGG checkout happens; `mwgg-ref` is ignored.
2. `pip install -r mwgg/requirements.txt` (your fork's requirements).
3. `python mwgg/Launcher.py "Build APWorlds" -- "<game>" --skip_open_folder`
   (your fork's Launcher).
4. Uploads `mwgg/build/apworlds/<apworld>.apworld` as a release asset.

### Output

A single `.apworld` file attached to the GitHub release as an asset. The file
is a zip archive containing the world source with `version` and
`compatible_version` fields added to the `archipelago.json` inside the zip.

### `.apworld` vs. wheel

| | Wheel (`.whl`) | APWorld (`.apworld`) |
|---|---|---|
| Used by | Index, pip, MultiworldGG's package manager | Players who manually install to `custom_worlds/` |
| Built by | `build.yml@v3` | `build-apworld.yml@v3` |
| Required for Index release | Yes | No |
| SHA-pinned by Oliver | Yes | No |

---

## `build-wheel.yml@v3` — pure-Python flat layout

For repos that ship a single pip-installable Python package at the repo root
(a `pyproject.toml` plus a top-level package directory — not a
`worlds/<apworld>/` shape). Used by client and library repos, not APWorlds.

This workflow is out of scope for APWorld authors. See
[`gen-pymod-release/README.md`](https://github.com/MultiworldGG/gen-pymod-release/blob/main/README.md)
if you need it.

---

## Pinning

Pin to a major-version tag for best-effort stability:

```yaml
uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
```

Pin to a full SHA for complete reproducibility (useful in security-sensitive
contexts):

```yaml
uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@<full-sha>
```

Breaking changes cut a new major version (`@v4`, etc.). Minor and patch
updates fast-forward the major-version tag without requiring changes in your
workflow file.
