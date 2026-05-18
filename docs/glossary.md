# Glossary

Terms used throughout this documentation.

---

**apworld**
: A world implementation packaged for MultiworldGG. Can be a loose folder
(`worlds/<apworld>/`) or a zip archive (`.apworld` file). The term "apworld"
refers to the unit of release, not to a specific file format. See
[`archipelago.json` schema reference](reference/archipelago-json.md).

**slug**
: The lowercase Python package identifier for an apworld. Used as the folder
name (`worlds/<slug>/`), the wheel package name (`worlds.<slug>`), the Index
manifest filename (`worlds/<slug>.json`), and the release tag prefix
(`<slug>-<world_version>`). Example: game "My Cool Game" has slug `myclgm`.

**`archipelago.json`**
: The metadata file that lives at `worlds/<apworld>/archipelago.json` in your
source repo. Contains `game`, `world_version`, `authors`, version guards, and
other author-controlled fields. The single source of truth for world identity.
Full field reference: [archipelago.json schema](reference/archipelago-json.md).

**module_location**
: The pip-installable URL for a world's wheel, including a `#sha256=<hex>`
digest fragment. Written by Oliver into the Index manifest when opening a PR.
Authors must not write this field themselves. Example:
`https://github.com/you/repo/releases/download/myclgm-1.0.0/worlds.myclgm-1.0.0-py3-none-any.whl#sha256=<hex>`.

**Oliver** (Oliver-Multiworld-Squirrel)
: The GitHub App that watches per-world repos for **published releases** whose
attached build workflow (`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`)
has finished and uploaded a `.whl` asset, and automatically opens PRs on the
MultiworldGG-Index. Oliver subscribes to both the `release` and `workflow_run`
webhook events so it can react whether the release was published directly or
the build workflow ran via a custom caller. Oliver pins the wheel asset URL
with a SHA256 hash so pip verifies the downloaded bytes. See
[Why Oliver opens the PR](why-oliver.md).

**Karen**
: The automated reviewer that runs on every Index PR opened by Oliver. She
runs seven checks (schema, manifest consistency, URL reachability, size,
AST scan, bandit, pip-audit) plus CodeQL and a fuzzer run, then posts a
sticky comment with the results. On all-green, she requests a human CODEOWNER
review. See [Why Oliver opens the PR](why-oliver.md#what-karen-checks).

**Index**
: The MultiworldGG-Index repository
(`https://github.com/MultiworldGG/MultiworldGG-Index`). The canonical source of
truth for which APWorlds exist, who wrote them, and where to fetch them from.
Manifest PRs land on the `main` branch; the four orphan branches
(`game_index_*`) are built from `main` by a scheduled workflow.

**orphan branch**
: A branch with no shared history with `main`. The four `game_index_*`
branches (`game_index_nr`, `game_index_ao`, `game_index_twelve`,
`game_index_sixteen`) are orphan branches that contain pip-installable
`mwgg_igdb` packages built from the Index manifests. They are force-pushed on
each daily release. Authors do not interact with orphan branches directly.

**`mwgg_igdb`**
: The Python package that the MultiworldGG launcher and generator read at
runtime to discover available worlds. Built from the Index `main` manifests
during the daily release. Installed from one of the four orphan branches
depending on the content-rating variant configured for the installation.

**Karen review**
: The automated check suite that Karen runs on every Index PR. Not a
checklist the author must satisfy before releasing — Karen runs after the
release is cut and reports what she found. Results are guidance for the human
CODEOWNER who merges. See [Why Oliver opens the PR](why-oliver.md).

**wheel (`.whl`)**
: A pip-installable Python package archive. The `build.yml@v3` reusable
workflow produces one per release, named
`worlds.<apworld>-<world_version>-py3-none-any.whl`. This is what Oliver
records in the Index manifest and what the MultiworldGG package manager
installs.

**`.apworld`**
: A zip archive containing a world's source files with `version` and
`compatible_version` fields added to the internal `archipelago.json`. Used
by players who install worlds directly into their `custom_worlds/` folder.
Built by the `build-apworld.yml@v3` reusable workflow. Not required for the
Index release.
