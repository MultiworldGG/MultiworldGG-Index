# Advanced setup — from an Archipelago fork

This page is for authors whose world lives inside a fork of
`MultiworldGG/MultiworldGG` (or an older `ArchipelagoMW/Archipelago` fork)
and who want a custom `pyproject.toml`.

The `pyproject.toml` rules, skeleton, and workflow file are identical to the
[standalone-repo advanced setup](from-standalone-repo.md) — read that page
for the full `pyproject.toml` walkthrough. This page adds the fork-specific
considerations.

---

!!! warning "Migrating from an older release workflow?"
    Same advice as the easy fork guide: delete or disable any existing workflow
    that manually packages your world before adding the one below. Your existing
    release tags are fine; tags going forward must be `<apworld>-<version>`.

---

## One-time setup

Same three steps as the easy fork path:

1. Install **Oliver-Multiworld-Squirrel** on your fork:
   <https://github.com/apps/oliver-multiworld-squirrel>
2. Settings → Secrets and variables → Actions → Variables:
   `WORLD_FOLDER_NAME=<apworld>`
3. Add `.github/workflows/make_pyproject.yml` as below.

---

## Workflow file

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

  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Your Game Name"
      # mwgg-ref defaults to canonical MultiworldGG main.
      # Override if you want the .apworld built against your fork's Launcher.py:
      # mwgg-ref: "your-fork-branch-or-tag"
```

---

## The `mwgg-ref` input

Because your repo is a MultiworldGG fork, `build-apworld.yml` has two sensible
options for which MultiworldGG to use when building the `.apworld`:

- **Default (recommended):** omit `mwgg-ref`. The workflow checks out canonical
  `MultiworldGG/MultiworldGG` at its default branch. This gives you a `.apworld`
  that works with the canonical release, which is what your players will have.

- **Override:** set `mwgg-ref` to a tag or branch in your fork (e.g.
  `mwgg-ref: "my-fork-main"`). This is useful if your world relies on a custom
  `Launcher.py` or modified core that is not yet in canonical MultiworldGG.
  Be aware that players will still install canonical MultiworldGG; the override
  only affects what the build uses to produce the `.apworld` artifact.

For most fork-based worlds, leaving `mwgg-ref` at the default is correct.

---

## `pyproject.toml`

See [Advanced setup from a standalone repo — Recommended skeleton](from-standalone-repo.md#recommended-pyprojecttoml-skeleton)
for the full `pyproject.toml` content. Place it at
`worlds/<apworld>/pyproject.toml` in your fork. The rules are identical:
don't hard-code `version`, `authors`, or `description`.

---

## Cutting a release

Same as the easy path: bump `world_version` in `archipelago.json`, push a tag
`<apworld>-<version>`, publish the release on GitHub. The workflow reads both
your `archipelago.json` and your `pyproject.toml` automatically.

---

## Compatibility branches

[Compatibility branches](compatibility-branches.md){ .md-button }

[Troubleshooting](../reference/troubleshooting.md){ .md-button }
