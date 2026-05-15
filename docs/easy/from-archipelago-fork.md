# Easy setup — from an Archipelago fork

This page is for authors whose world lives at `worlds/<apworld>/` inside a fork
of `MultiworldGG/MultiworldGG` (or an older `ArchipelagoMW/Archipelago` fork).

---

!!! warning "Migrating from an older release workflow (user 3)?"
    If you already have a `.github/workflows/` file that manually zips your
    world folder into a `.apworld` and uploads it as a release asset, **delete
    or disable that workflow before continuing**. The workflow below produces
    both a `.whl` (for the Index) and a `.apworld` (for direct installation),
    and having two workflows race each other produces confusing duplicate assets.

    If your old workflow is named anything other than
    `Create and Release Python Package`, it will not collide with Oliver's
    event filter — but it is still better to remove it than to ship a
    hand-built `.apworld` alongside the CI-built one.

    Your existing release tags are fine. Tags going forward must follow the
    `<apworld>-<version>` format described in step 3 below.

---

## What you need in your repo

Your world folder must contain `worlds/<apworld>/archipelago.json` with at
minimum a `game` field and a `world_version` field. The workflow reads both.

A complete minimal example:

```json
{
    "game": "Clique",
    "world_version": "1.0.0",
    "minimum_ap_version": "0.6.4",
    "authors": ["NewSoupVi"]
}
```

The `world_version` field must follow `major.minor.patch` format (e.g.
`"1.0.0"`). It is used as the wheel's Python package version and must match
the version in your release tag.

No `pyproject.toml` is needed. The build workflow synthesizes one from your
`archipelago.json` automatically.

---

## One-time setup

### Step 1 — Install the Oliver-Multiworld-Squirrel GitHub App

Install the app on your repo (it requests read-only permissions):

**<https://github.com/apps/oliver-multiworld-squirrel>**

Click "Install" and select your fork repo. Oliver will watch for completed
`Create and Release Python Package` workflow runs and open Index PRs on your behalf.

### Step 2 — Set the `WORLD_FOLDER_NAME` variable

In your repo, go to **Settings → Secrets and variables → Actions → Variables**
and create a new variable:

| Name | Value |
|---|---|
| `WORLD_FOLDER_NAME` | `<apworld>` (e.g. `clique`) |

This tells the reusable workflow which subfolder of `worlds/` to build.

### Step 3 — Add the workflow file

Create `.github/workflows/make_pyproject.yml` in your repo with the following
content. Replace `"Your Game Name"` with the exact `game` value from your
`archipelago.json`.

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
    # No `with:` needed for single-world repos.
    # No `secrets:` — no Oliver secrets needed in your repo.

  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Your Game Name"
```

The `publish-wheel` job is what Oliver consumes when opening the Index PR.
The `publish-apworld` job produces a `.apworld` file for players who install
worlds directly into their `custom_worlds/` folder. You can drop either job
if you only need the other.

---

## Cutting a release

1. Make sure `world_version` in `archipelago.json` reflects the new version
   (e.g. `"1.2.0"`).
2. Push a tag in the format `<apworld>-<version>` — for example, `clique-1.2.0`.
   The tag's version part must match `world_version` exactly, or the workflow
   will fail with a version-mismatch error.
3. Go to **Releases → Draft a new release**, select your tag, fill in the
   release notes, and click **Publish release**.
4. The `Create and Release Python Package` workflow runs automatically. Within
   a minute or two, both assets are attached to your release.
5. Within about 30 seconds of the workflow finishing, Oliver opens a PR on the
   Index.

!!! tip "First release?"
    If the world is new, Oliver will label the Index PR **New APWorld**. If the
    world already exists on the Index, it gets **APWorld Update**. Either way
    the process is the same.

---

## What happens next

- Karen runs her automated review checks on the PR and posts a comment with
  the results. [See what she checks.](../why-oliver.md)
- On green, Karen requests review from a human CODEOWNER.
- The CODEOWNER approves and merges.
- The next daily rebuild picks up your manifest, and your world appears in the
  MultiworldGG launcher.

---

## Troubleshooting

| Symptom | Quick fix |
|---|---|
| Oliver didn't open a PR | Check [reference/troubleshooting.md](../reference/troubleshooting.md) for the six most common causes. |
| Workflow failed: version mismatch | Tag version and `archipelago.json:world_version` must agree exactly. |
| Karen left a comment with red checks | Read the check details in the comment; the human CODEOWNER will advise on next steps. |

[Full troubleshooting guide](../reference/troubleshooting.md){ .md-button }
