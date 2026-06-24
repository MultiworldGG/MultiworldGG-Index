# Basic Manual — from an Archipelago fork

This page is for authors whose world lives at `worlds/<apworld>/` inside a fork
of `MultiworldGG/MultiworldGG` or `ArchipelagoMW/Archipelago`, who already build
their `.apworld` with the Launcher and attach it to a GitHub Release by hand, and
who want to keep doing exactly that — no GitHub Actions workflow, no tokens, no
draft-release helper.

You will do one extra step at release time: build the `.whl` locally with a small
script and attach it to the same release alongside the `.apworld`. That is all.
Oliver takes it from there and opens the Index PR.

!!! tip "Prefer to automate this later?"
    Everything below is by hand on purpose. If you ever want a workflow to build
    and attach both assets for you on publish, switch to the
    [Standard Automated setup](../standard/index.md) — the world layout is the same.

---

## What you need in your repo

Your world folder must contain `worlds/<apworld>/archipelago.json` with at minimum
a `game` field and a `world_version` field:

```json
{
    "game": "My Cool Game",
    "world_version": "1.0.0",
    "minimum_ap_version": "0.6.4",
    "authors": ["NewSoupVi"]
}
```

`world_version` is used as the wheel's Python package version. See the
[archipelago.json reference](../reference/archipelago-json.md) for every field.
No `pyproject.toml` is required — the build script synthesizes one from
`archipelago.json`.

---

## One-time setup

### Install Oliver

Install the Oliver-Multiworld-Squirrel GitHub App on your fork (read-only
permissions):

**<https://github.com/apps/oliver-the-multiworld-squirrel>**

Oliver is **not** CI. It is the bot that watches your published releases and opens
the Index PR for you — recording the wheel's URL and its SHA256 so pip can verify
the exact bytes at install time. [Why Oliver opens the PR.](../why-oliver.md)

### Get the build script

The wheel builder ships in the `apworld-wheel-workflow-<tag>.zip` bundle on the
[`gen-pymod-release` releases page](https://github.com/MultiworldGG/gen-pymod-release/releases)
(look for tags matching `apworld-wheel-workflow-*`).

1. Download `apworld-wheel-workflow-<tag>.zip`.
2. Unzip it. The build script lives under `tools/build/scripts/`.

You do not need to copy anything into your fork or commit the bundled workflow
file — the Basic Manual path only uses the local build script.

---

## Cutting a release

### 1. Set the version

Bump `world_version` in `worlds/<apworld>/archipelago.json` to the new version and
commit it.

### 2. Build the `.apworld` (as you already do)

From your fork:

```bash
python Launcher.py "Build APWorlds" -- "My Cool Game"
```

This produces `build/apworlds/<apworld>.apworld`.

### 3. Build the `.whl`

Run the build script from the unzipped bundle, from your fork root, passing just
the apworld folder name:

```bash
python tools/build/scripts/<build-script>.py --apworld <apworld>
```

It reads `game` and `world_version` from `worlds/<apworld>/archipelago.json` and
produces `worlds_<apworld>-<world_version>-py3-none-any.whl`.

!!! note "Exact script name"
    The precise filename and flags are documented in the bundle; this page is
    finalized against the shipped `apworld-wheel-workflow-*` release. If the
    command differs from what you find under `tools/build/scripts/`, follow the
    bundle.

### 4. Create the release and attach both assets

Create a GitHub Release. **The Basic Manual path does not require a special tag
format** — name the release whatever you like; Oliver identifies your world from
the attached `<apworld>.apworld` asset.

Attach **both** assets to the release:

- `<apworld>.apworld`
- `worlds_<apworld>-<world_version>-py3-none-any.whl`

To make sure both files are present *before* the release goes public — so Oliver
sees a complete release — create it as a **draft**, upload both assets, and only
then publish. In the GitHub UI: **Draft a new release → Save draft → upload both
assets → Publish release**. (The `gh` CLI equivalent is in the
[FAQ](../faq.md#how-do-i-publish-so-oliver-sees-both-assets).)

### 5. Publish

Click **Publish release**. Within about 30 seconds Oliver opens the Index PR.

---

## What happens next

- Oliver reads your `.whl` asset URL and its SHA256 and opens a PR on the Index
  recording where your world lives.
- Karen runs her review checks against the wheel you uploaded and posts a comment.
- On green, a human CODEOWNER approves and merges.
- The next daily rebuild picks up your manifest, and your world appears in the
  MultiworldGG launcher.

This is identical to the automated paths from here on — the only difference is
that you built and attached the wheel yourself.

---

## Notes

- **Don't replace a `.whl` after the PR opens.** Oliver pins the exact bytes by
  SHA256; swapping the asset breaks that pin. To ship a fix, bump `world_version`
  and cut a new release. See
  [re-releasing](../reference/troubleshooting.md#i-need-to-re-release-the-same-tag).
- **Tired of doing this every release?** The
  [Standard Automated setup](../standard/index.md) builds and attaches both assets
  for you when you publish.

[Troubleshooting](../reference/troubleshooting.md){ .md-button .md-button--primary }
