# Easy setup — from an Archipelago fork

This page is for authors whose world lives at `worlds/<apworld>/` inside a fork
of `MultiworldGG/MultiworldGG` (or an older `ArchipelagoMW/Archipelago` fork).

---

!!! warning "Migrating from an older release workflow?"
    If you already have a `.github/workflows/` file that manually zips your
    world folder into a `.apworld` and uploads it as a release asset, **delete
    or disable that workflow before continuing**. The workflow below produces
    both a `.whl` (for the Index) and a `.apworld` (for direct installation),
    and having two workflows race each other produces confusing duplicate assets.

    Oliver ignores workflows that do not call
    `MultiworldGG/gen-pymod-release/.github/workflows/build.yml`, but it is
    still better to remove the old workflow than to ship a hand-built
    `.apworld` alongside the CI-built one.

    Your existing release tags are fine. Tags going forward must follow the
    `<apworld>-<version>` format described in step 3 below.

---

## What you need in your repo

Your world folder must contain `worlds/<apworld>/archipelago.json` with at
minimum a `game` field and a `world_version` field. The workflow reads both.

A complete minimal example:

```json
{
    "game": "My Cool Gamel Game",
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

Click "Install" and select your fork repo. Oliver will see your published
releases, wait for the build workflow to attach a `.whl` asset, and open Index
PRs on your behalf.

### Step 2 — Add the workflow file

Create `.github/workflows/make_pyproject.yml` in your repo with the following
content. Replace `"Your Game Name"` with the exact `game` value from your
`archipelago.json`.

```yaml
name: Create and Release Python Package
on:
  release:
    types: [published]

permissions:
  contents: write

jobs:
  publish-wheel:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3

  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Your Game Name"
      from-fork: true
```

The `publish-wheel` job is what Oliver consumes when opening the Index PR.
The `publish-apworld` job produces a `.apworld` file for players who install
worlds directly into their `custom_worlds/` folder. You can drop either job
if you only need the other.

`from-fork: true` tells the build to use your fork's own `Launcher.py` instead
of fetching `MultiworldGG/MultiworldGG`. This is what fork authors have always
done by hand, and it preserves any unreleased core changes your world depends
on.

---

## Cutting a release

1. Make sure `world_version` in `archipelago.json` reflects the new version
   (e.g. `"1.2.0"`).
2. Commit the version bump.
3. From your fork, run the draft-release helper. Replace the path with wherever
   you keep `gen-pymod-release`:

   ```bash
   python /path/to/gen-pymod-release/scripts/prepare_apworld_release.py --apworld myclgm --open
   ```

   The helper creates and pushes the `<apworld>-<version>` tag, creates a draft
   GitHub Release, and opens the draft release page.
4. Review the draft release in GitHub. Do not upload `.whl` or `.apworld`
   assets by hand.
5. Click **Publish release**.
6. The release workflow runs automatically. Within a minute or two, both assets
   are attached to your release.
7. Within about 30 seconds of the workflow finishing, Oliver opens a PR on the
   Index.

!!! note "Why a draft release?"
    Draft creation gives you the same review step as uploading an `.apworld`
    by hand, but the release is still immutable. The assets are attached only
    after you click **Publish release**, and the workflow pins the wheel bytes
    that Oliver records in the Index.

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
| Oliver didn't open a PR | Check [reference/troubleshooting.md](../reference/troubleshooting.md) for the common causes. |
| Workflow failed: version mismatch | Tag version and `archipelago.json:world_version` must agree exactly. |
| Karen left a comment with red checks | Read the check details in the comment; the human CODEOWNER will advise on next steps. |

[Full troubleshooting guide](../reference/troubleshooting.md){ .md-button }
