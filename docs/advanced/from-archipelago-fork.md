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

Bump `world_version` in `archipelago.json`, push a tag
`<apworld>-<version>`, and publish the release on GitHub. The reusable workflow
reads both `archipelago.json` and your optional `pyproject.toml` automatically.

---

[Troubleshooting](../reference/troubleshooting.md){ .md-button }
