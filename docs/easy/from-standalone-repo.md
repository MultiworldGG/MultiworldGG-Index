# Easy setup — from a standalone repo

This page is for authors whose world lives in its own repository (not a full
MultiworldGG fork), with the world source at `worlds/<apworld>/` in that repo.

---

## What you need in your repo

Your repo must have `worlds/<apworld>/archipelago.json` with at minimum a
`game` field and a `world_version` field:

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
the version portion of your release tag.

No `pyproject.toml` is needed. The build workflow synthesizes one from your
`archipelago.json` automatically.

---

## One-time setup

### Step 1 — Install the Oliver-Multiworld-Squirrel GitHub App

Install the app on your repo (it requests read-only permissions):

**<https://github.com/apps/oliver-multiworld-squirrel>**

Click "Install" and select your per-world repo.

### Step 2 — Set the `WORLD_FOLDER_NAME` variable

In your repo, go to **Settings → Secrets and variables → Actions → Variables**
and create a new variable:

| Name | Value |
|---|---|
| `WORLD_FOLDER_NAME` | `<apworld>` (e.g. `clique`) |

### Step 3 — Add the workflow file

Create `.github/workflows/make_pyproject.yml` in your repo:

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
```

This produces the `.whl` asset that Oliver consumes when opening the Index PR.

!!! note "Want a `.apworld` file too?"
    The `publish-wheel` job above is all you need for the Index release. If
    you also want a `.apworld` artifact that players can drop directly into
    their `custom_worlds/` folder, add a second job:

    ```yaml
      publish-apworld:
        uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
        with:
          game: "Your Game Name"
          apworld-source-ref: ${{ github.event.release.tag_name }}
    ```

    The `build-apworld.yml` workflow checks out a MultiworldGG instance
    internally and runs `Launcher.py "Build APWorlds"` against your world —
    you do not need to be a MultiworldGG fork to use it.

---

## Cutting a release

1. Make sure `world_version` in `archipelago.json` reflects the new version.
2. Push a tag in the format `<apworld>-<version>` — for example, `clique-1.2.0`.
   The version in the tag must match `world_version` exactly.
3. Go to **Releases → Draft a new release**, select your tag, and click
   **Publish release**.
4. The workflow runs and attaches the `.whl` to the release.
5. Within about 30 seconds of the workflow finishing, Oliver opens a PR on the
   Index.

---

## Local development loop

To test your world locally before releasing, symlink your world repo's
`worlds/<apworld>/` directory into a MultiworldGG checkout's `worlds/`
directory, then run the Launcher's "Build APWorlds" component:

=== "Windows"

    ```
    mklink /J C:\path\to\MultiworldGG\worlds\<apworld> C:\path\to\your-repo\worlds\<apworld>
    cd C:\path\to\MultiworldGG
    python Launcher.py "Build APWorlds" -- "<Game Name>"
    ```

=== "macOS / Linux"

    ```bash
    ln -s /path/to/your-repo/worlds/<apworld> /path/to/MultiworldGG/worlds/<apworld>
    cd /path/to/MultiworldGG
    python Launcher.py "Build APWorlds" -- "<Game Name>"
    ```

This is for local testing only. The release artifact is built by CI from your
repo. The `.apworld` file is written to `build/apworlds/` relative to the
MultiworldGG root.

---

## What happens next

- Karen runs her automated review checks on the Index PR. [See what she checks.](../why-oliver.md)
- On green, Karen requests a human CODEOWNER review.
- The CODEOWNER approves and merges.
- The next daily rebuild publishes your world to the MultiworldGG launcher.

[Full troubleshooting guide](../reference/troubleshooting.md){ .md-button }
