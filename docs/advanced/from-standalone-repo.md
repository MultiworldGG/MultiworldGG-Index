# Advanced setup — from a standalone repo

This page covers authors whose world lives in its own repository and who want
to provide a custom `pyproject.toml` for:

- Non-default Python dependencies (`requests`, `numpy`, etc.)
- Custom PyPI classifiers
- Extra entry points beyond the auto-discovered `mwgg.client`
- Multiple worlds shipped from a single repo under `worlds/<apworld-1>/`,
  `worlds/<apworld-2>/`, etc.

---

## When you want this

If your world has no special dependencies and ships one world, the
[easy setup](../easy/from-standalone-repo.md) is all you need.

You want the advanced path when:

- Your world imports a third-party library that is not in MultiworldGG's base
  requirements (e.g. `pillow`, `pyserial`, a custom data-processing library).
- You want custom classifiers to appear in the wheel metadata.
- You ship an in-game client and want to declare an `mwgg.client` entry point
  with a non-default target.
- You ship multiple worlds from one repo and need per-world dependency
  declarations.

---

## How the build consumes your `pyproject.toml`

`gen-pymod-release`'s `shape_orphan.py` script applies these rules when
`worlds/<apworld>/pyproject.toml` exists:

- `[project].version`, `[project].authors`, and `[project].description` are
  **injected from `archipelago.json`** only when the field is absent or blank
  in your `pyproject.toml`. `archipelago.json` is the single source of truth;
  do not hard-code these.
- Entry points under `[project.scripts]` and `[project.entry-points]` are
  **merged** with any auto-discovered `mwgg.client` entries; yours take
  precedence if the key collides.
- The `pyproject.toml` you provide is deleted from the output tree. Only the
  synthesized root-level `pyproject.toml` is canonical in the built wheel.
- Everything else in your `pyproject.toml` passes through unchanged.

---

## Recommended `pyproject.toml` skeleton

Place this at `worlds/<apworld>/pyproject.toml` in your repo:

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "worlds.<apworld>"
# version, authors, description left out — shape_orphan.py injects from archipelago.json
requires-python = ">=3.13"
dependencies = [
    # list your non-default deps here, e.g.:
    # "pillow>=10.0",
]
classifiers = ["Private :: Do Not Upload"]

[tool.setuptools.packages.find]
where = ["src"]
include = ["worlds.<apworld>"]
namespaces = true
```

Replace `<apworld>` with your actual apworld slug (lowercase, no hyphens —
matches your `worlds/<apworld>/` folder name and the stem of your release tag).

Do not hard-code `version`, `authors`, or `description` in this file. The build
reads them from `archipelago.json` and injects them. Hard-coding creates a drift
risk where the wheel metadata disagrees with the manifest.

---

## Workflow file

The workflow is identical to the easy path. Add
`.github/workflows/make_pyproject.yml`:

```yaml
name: Create and Release Python Package
on:
  release:
    types: [published]
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  publish-wheel:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    # shape_orphan.py picks up worlds/<apworld>/pyproject.toml automatically.
    # No extra `with:` needed for single-world repos.

  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Your Game Name"
      apworld-source-ref: ${{ github.event.release.tag_name }}
```

Drop `publish-apworld` if you only need the wheel.

---

## One-time setup

Same three steps as the easy path:

1. Install **Oliver-Multiworld-Squirrel** on your repo:
   <https://github.com/apps/oliver-multiworld-squirrel>
2. Settings → Secrets and variables → Actions → Variables:
   `WORLD_FOLDER_NAME=<apworld>`
3. Add `.github/workflows/make_pyproject.yml` as above.

---

## Cutting a release

Same as the easy path: bump `world_version` in `archipelago.json`, push a tag
`<apworld>-<version>`, create the release on GitHub. The workflow picks up your
`pyproject.toml` automatically; no extra configuration is needed.

---

## Local development loop

For local testing, you have three options:

1. **Symlink + Launcher** — symlink `worlds/<apworld>/` into a MultiworldGG
   checkout and run `python Launcher.py "Build APWorlds" -- "<Game Name>"`.
   Produces a `.apworld` in `build/apworlds/`.

2. **Wheel dry-run** — trigger the `publish-wheel` job via
   `workflow_dispatch` with `dry-run: true` (the `build.yml@v3` workflow
   supports this input). The wheel is built but not uploaded, and you can
   download it from the workflow artifacts.

3. **`python -m build`** — run the build locally by constructing the orphan
   tree manually with `scripts/shape_orphan.py`, then running
   `python -m build --wheel` in the output directory. This is mostly useful for
   debugging `pyproject.toml` issues.

---

## Multiple worlds in one repo

To ship `worlds/worldA/` and `worlds/worldB/` from the same repo, add a
separate workflow job for each world using a different tag prefix:

```yaml
jobs:
  publish-world-a:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      source-ref: worlda-${{ github.event.release.tag_name }}

  publish-world-b:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      source-ref: worldb-${{ github.event.release.tag_name }}
```

Each world's `archipelago.json` and optional `pyproject.toml` are read from
its own `worlds/<apworld>/` directory. Oliver opens a separate Index PR per
world.

---

## Compatibility branches

If you need to support multiple MultiworldGG versions simultaneously, see
[Compatibility branches](compatibility-branches.md).

---

[Troubleshooting](../reference/troubleshooting.md){ .md-button }
