# Reusable workflow reference

All reusable workflows live in
`MultiworldGG/gen-pymod-release/.github/workflows/` and are called via
`uses:` in your per-world repo's workflow file. Pin to `@v3` — patch updates
fast-forward the major-version tag. Pin to a full SHA for complete
reproducibility.

---

## `build.yml@v3` — builds the wheel

Builds a pip-installable wheel from `worlds/<apworld>/` and uploads it as a
release asset. This is the primary workflow; Oliver watches for its
`workflow_run.completed` event to open the Index PR.

**Trigger requirement:** the calling workflow must be named exactly
`Create and Release Python Package` for Oliver to recognise it.

### Minimal usage

```yaml
name: Create and Release Python Package
on:
  release:
    types: [published]
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  publish:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
```

### Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
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
`world_version` in `archipelago.json`. For example, tag `clique-1.2.0`
requires `"world_version": "1.2.0"` in `worlds/clique/archipelago.json`.

The workflow fails with a clear error message if the tag and
`archipelago.json` disagree.

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

```yaml
jobs:
  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Clique"
```

### Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| `game` | yes | — | The game's display name, exactly as it appears in `archipelago.json`. Passed to `Launcher.py "Build APWorlds" -- "<game>"`. |
| `mwgg-ref` | no | `"main"` | Which MultiworldGG ref to check out as the Launcher host. Override to test against a specific tag or fork branch. |
| `apworld-source-ref` | no | Release tag (on `release` event), else `github.sha` | Your world repo's ref to check out as the world source. |
| `dry-run` | no | `false` | Build the `.apworld` but skip the release-asset upload. |

### How it works

1. Checks out `MultiworldGG/MultiworldGG` at `mwgg-ref` into `mwgg/`.
2. Checks out your repo at `apworld-source-ref` into
   `mwgg/worlds/<apworld>/` (a transient overlay — your world source is dropped
   into the MultiworldGG tree for the Launcher to find it).
3. `pip install -r mwgg/requirements.txt`.
4. `python mwgg/Launcher.py "Build APWorlds" -- "<game>" --skip_open_folder`.
5. Uploads `mwgg/build/apworlds/<apworld>.apworld` as a release asset.

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
