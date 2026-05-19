# Advanced setup — from an Archipelago fork

This page is for authors whose world lives inside a fork of `Archipelago`, and
who want a custom `pyproject.toml` or a custom caller workflow.

The package rules and reusable workflow inputs are the same as the
[standalone-repo advanced setup](from-standalone-repo.md). The only difference
is where your world folder lives: still `worlds/<apworld>/`, but inside your
fork.

---

!!! warning "Migrating from an older release workflow?"
    If you have a workflow that zips your world into a `.apworld` without using
    the Launcher to compile it into an APWorld Container with a manifest, you
    should delete or disable it before adding this reusable workflow jobs. 
    New release tags must be `<apworld>-<version>` i.e. `wandofgamelon-0.0.1` 

---

## One-time setup

1. Install **Oliver-Multiworld-Squirrel** on your fork:
   <https://github.com/apps/oliver-multiworld-squirrel> - it only needs access
   to the repository where your code lives.
2. Add the reusable workflow jobs to your release workflow. If you want Oliver
   to open the Index PR via its `workflow_run.completed` handler, that workflow
   must be triggered by a `release` event and must call
   `MultiworldGG/gen-pymod-release/.github/workflows/build.yml`.
3. Place any custom package metadata at `worlds/<apworld>/pyproject.toml`.

!!! warning "Releases created by another workflow using `GITHUB_TOKEN`"
    If your release-creating step runs in another workflow under the default
    `GITHUB_TOKEN`, GitHub
    [will not trigger your downstream `release`-event build workflow](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow).
    Oliver's `release.published` handler still fires on the published release,
    but with no `workflow_run` to consume and no `.whl` asset attached, Oliver
    bails.

    Fix the chain by using a token that is allowed to trigger workflows on the
    step that creates the release:

    - A [fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
      with `contents: write` and `workflows: write` on this fork,
      [stored as a repository secret](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
      such as `secrets.RELEASE_PAT`, and passed in as
      `token: ${{ secrets.RELEASE_PAT }}`; or
    - A GitHub App token minted by
      [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token),
      from a GitHub App that has `Contents` and `Workflows` write permission on
      this fork.

---

## Building with your fork's own Launcher

Pass `from-fork: true` to `build-apworld.yml@v3`. The workflow then runs
`python Launcher.py "Build APWorlds" -- "<game>" --skip_open_folder` inside
your fork's checkout, so your fork's `Launcher.py` (and any unreleased core
changes it depends on) are what build the `.apworld`. This matches what fork
authors have always done by hand — the reusable workflow is just a convenience
wrapper around it.

`mwgg-ref` is ignored when `from-fork: true`. If your fork's `Launcher.py` is
broken at the ref you tagged, the build fails — that's intended; the fork is
the source of truth.

---

## `pyproject.toml`

See [Advanced setup from a standalone repo — Good `pyproject.toml`](from-standalone-repo.md#good-pyprojecttoml)
for the recommended file. Place it at `worlds/<apworld>/pyproject.toml` in your
fork.

---

## Cutting a release

Each apworld in your fork has its own `world_version` in its own
`worlds/<apworld>/archipelago.json` and is released on its own cadence. To
ship a new version of one apworld:

1. Bump `world_version` in `worlds/<apworld>/archipelago.json` for **that one
   apworld**.
2. Push a tag `<apworld>-<version>` (e.g. `wandofgamelon-0.0.1`) at the commit
   you want to build from. The tag can live on `main` or on a per-game
   branch — the reusable workflow checks out at the tag's commit either way.
3. Publish the release on GitHub.

The reusable workflow reads `worlds/<apworld>/archipelago.json` and your
optional `worlds/<apworld>/pyproject.toml` automatically. Each release event
builds **only** the apworld whose name prefixes the tag and produces exactly
one `.whl` + one `.apworld` for it. Other apworlds in the same fork are not
rebuilt or re-uploaded — they keep their existing versions until you tag and
release them in turn.

---

## Vendored build tooling (self-contained setup)

If you'd like to add the entire workflow and tool setup yourself, there is a
release at <https://github.com/MultiworldGG/gen-pymod-release/releases> (look
for tags matching `apworld-wheel-workflow-*`). Here's the steps to use that:

1. Download `apworld-wheel-workflow-<tag>.zip` from the Releases page.
2. Unzip it locally — the archive expands into a tree rooted at
   `.github/workflows/make_pyproject.yml` and
   `tools/build/{scripts,templates,games.json}`.
3. Copy those contents into the root of your Archipelago fork. The fork must
   have `Launcher.py` and `requirements.txt` at the root (i.e. be a full
   Archipelago source tree).
4. Edit `tools/build/games.json` once for the fork. It is a lookup table:
   add **one entry per apworld** in your fork mapping the
   `worlds/<apworld>/` directory name to the `World.game` display name (the
   `game` attribute on your Python class). The workflow consults this table
   per release tag to find the matching apworld's display name; it does not
   iterate over the table, so adding new entries here never causes other
   apworlds to be rebuilt.
5. Commit and push. Then, for each apworld you want to ship, cut a GitHub
   Release tagged `<apworld>-<version>` (e.g. `wandofgamelon-0.0.1`) matching
   the `world_version` in **that apworld's** `worlds/<apworld>/archipelago.json`.
   The tag can live on `main` or on a per-game branch. The bundled workflow
   runs on `release.published` and builds **only** `worlds/<apworld>/` for
   the apworld whose name prefixes the tag, uploading exactly one `.whl` and
   one `.apworld` for that apworld. Other apworlds in the fork are
   untouched — release them in turn under their own `<apworld>-<version>`
   tags as they're ready.
6. After the release assets are attached, either install the
   Oliver-Multiworld-Squirrel App (which auto-opens the Index PR) or open the
   `worlds/<apworld>.json` Index PR by hand, pointing `release_location` at the
   wheel's `browser_download_url#sha256=<hex>`.

---

[Troubleshooting](../reference/troubleshooting.md){ .md-button }
