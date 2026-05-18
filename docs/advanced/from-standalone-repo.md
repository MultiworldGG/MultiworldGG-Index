# Advanced setup — from a standalone repo

This page is for authors whose world lives in its own repository and who want
to provide their own `pyproject.toml`, call the reusable workflows from an
existing release workflow, or ship more than one world from the same repo.

The easy path does not cover the standalone-repo shape — this advanced page is
the maintained path for that layout.

---

## When you want this

Use the advanced path when:

- You want package metadata beyond the generated default, such as custom
  classifiers or explicit entry points.
- You want dependencies declared in `pyproject.toml`. If all you need is a
  simple dependency list, `worlds/<apworld>/requirements.txt` also works.
- You already have a release workflow and want to add the reusable wheel build
  job to it.
- You ship multiple worlds from one repo under separate `worlds/<apworld>/`
  folders.

---

## How the build consumes your `pyproject.toml`

`gen-pymod-release`'s `shape_tree.py` script applies these rules when
`worlds/<apworld>/pyproject.toml` exists:

- `[project].version` is injected from `archipelago.json:world_version` when it
  is absent or blank.
- `[project].authors` is injected from `archipelago.json:authors` when it is
  absent or blank.
- `[project].description` is always overwritten as `MultiWorld: <game>` from
  `archipelago.json:game`.
- If your `pyproject.toml` already declares `[project].dependencies`, it wins
  over `worlds/<apworld>/requirements.txt`.
- Auto-discovered `mwgg.client` entry points are injected only when you have not
  declared `[project.entry-points."mwgg.client"]` yourself.
- The nested `worlds/<apworld>/pyproject.toml` is removed from the wheel source
  tree. The synthesized root-level `pyproject.toml` is what gets built.

Do not hard-code `version`, `authors`, or `description` in your source
`pyproject.toml`. `archipelago.json` stays the source of truth for release
identity.

---

## Good `pyproject.toml`

Place this at `worlds/<apworld>/pyproject.toml`, replacing `your_apworld` and
the fake dependencies with real values:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "worlds.your_apworld"
requires-python = ">=3.13"
dependencies = [
    "pillow>=10.3",
    "platformdirs>=4.2",
]
classifiers = ["Private :: Do Not Upload"]

[project.entry-points."mwgg.client"]
"worlds.your_apworld.Client" = "worlds.your_apworld.mwgg_client:launch_client"

[tool.setuptools.packages.find]
where = ["src"]
include = ["worlds.your_apworld"]
namespaces = true
```

If you do not ship a client, omit the `mwgg.client` block. If you do ship one
and rely on the legacy `Component(..., component_type=Type.CLIENT)` registration,
the build can auto-discover it; the explicit entry point above is just less
magic.

---

## Good `mwgg_client.py`

This is a launcher-integrated text-style client. It follows the same hooks as
the built-in text client in `CommonClient.py`: subclass `CommonContext`, override
`server_auth`, use `on_package` for server messages you care about, and expose a
zero-argument `launch_client` entry point.

```python
from __future__ import annotations

import argparse
import asyncio
import logging

from CommonClient import CommonContext, get_base_parser, server_loop
from Utils import async_start, init_logging

logger = logging.getLogger("YourGameClient")


class YourGameContext(CommonContext):
    game = "Your Game Name"
    items_handling = 0b111
    want_slot_data = True

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)

        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "Connected":
            logger.info("Connected as %s in slot %s", self.auth, self.slot)


async def _main(args: argparse.Namespace) -> None:
    ctx = YourGameContext(server_address=args.connect, password=args.password)
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

    if ctx._can_takeover_existing_ui():
        await ctx._takeover_existing_ui()
    else:
        ctx.takeover_complete.set()
        ctx.run_gui()

    await ctx.server_auth()
    await ctx.exit_event.wait()
    await ctx.shutdown()


def launch_client() -> None:
    init_logging("YourGameClient")
    parser = get_base_parser("Your Game Name Client")
    args = parser.parse_args()
    async_start(_main(args), name="YourGameClient")
```

---

## Calling the reusable workflows yourself

Oliver opens an Index PR via its `workflow_run.completed` handler for
successful `release`-event runs that call
`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`. The caller
workflow name is up to you.

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
      with `contents: write` and `workflows: write` on this repo,
      [stored as a repository secret](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
      such as `secrets.RELEASE_PAT`, and passed in as
      `token: ${{ secrets.RELEASE_PAT }}`; or
    - A GitHub App token minted by
      [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token),
      from a GitHub App that has `Contents` and `Workflows` write permission on
      this repo.

```yaml
name: Create and Release Python APWorld
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
  publish-wheel:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      apworld: ${{ inputs.apworld || '' }}
      source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}

  publish-apworld:
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build-apworld.yml@v3
    with:
      game: "Your Game Name"
      apworld: ${{ inputs.apworld || '' }}
      apworld-source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}
```

On a release run, the reusable workflows ignore `apworld` and parse the slug
from the tag prefix. On a manual run, there is no release tag, so `apworld` is
required and `dry-run: true` avoids uploading release assets.

---

## Multiple worlds in one repo

For `worlds/worlda/` and `worlds/worldb/`, gate each job by the release tag
prefix. A `worlda-1.2.0` release builds only `worlda`; a manual dry-run builds
the world selected by the `apworld` input.

```yaml
jobs:
  publish-worlda:
    if: ${{ startsWith(github.event.release.tag_name || '', 'worlda-') || inputs.apworld == 'worlda' }}
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      apworld: worlda
      source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}

  publish-worldb:
    if: ${{ startsWith(github.event.release.tag_name || '', 'worldb-') || inputs.apworld == 'worldb' }}
    uses: MultiworldGG/gen-pymod-release/.github/workflows/build.yml@v3
    with:
      apworld: worldb
      source-ref: ${{ inputs.source_ref || '' }}
      dry-run: ${{ github.event_name == 'workflow_dispatch' }}
```

Cut releases as `<apworld>-<version>`, for example `worlda-1.2.0`. Oliver opens
one Index PR for the world whose wheel was attached to that release.

---

## Local development loop

For local testing, you have three options:

1. **Symlink + Launcher** — symlink `worlds/<apworld>/` into a MultiworldGG
   checkout and run `python Launcher.py "Build APWorlds" -- "<Game Name>"`.
   Produces a `.apworld` in `build/apworlds/`.
2. **Manual dry-run** — run the workflow from the Actions tab with `apworld`
   set to your world folder. The wheel is built but not uploaded to a release.
3. **`python -m build`** — construct the orphan tree manually with
   `scripts/shape_tree.py`, then run `python -m build --wheel` in the output
   directory. This is mostly useful for debugging `pyproject.toml` issues.

---

[Troubleshooting](../reference/troubleshooting.md){ .md-button }
