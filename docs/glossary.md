# Glossary

Terms used throughout this documentation.

---

**apworld**
: A world implementation packaged for Archipelago & forks. Can be a loose folder
(`worlds/<apworld>/`) or a zip archive (`.apworld` file). The term "apworld"
refers to the unit of release, not to a specific file format. See
[`archipelago.json` schema reference](reference/archipelago-json.md).

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

**Oliver** (Oliver-the-Multiworld-Squirrel)
: The GitHub App that watches per-world repos for **published releases** whose
attached build workflow (`MultiworldGG/gen-pymod-release/.github/workflows/build.yml`)
has finished and uploaded a `.whl` asset, and automatically opens PRs on the
MultiworldGG-Index. Oliver subscribes to both the `release` and `workflow_run`
webhook events so it can react whether the release was published directly or
the build workflow ran via a custom caller. Oliver pins the wheel asset URL
with a SHA256 hash so pip verifies the downloaded bytes. See
[Why Oliver opens the PR](why-oliver.md).

**Karen**
: The automated reviewer that runs on every Index PR opened by Oliver. On the
runner she runs the fast manifest checks (schema, manifest consistency, URL
reachability) and bases her `APPROVE` on those alone. The heavier
security/quality work — size, ROM scan, AST scan, bandit, pip-audit, a ruff
quality lint, and a generation fuzz — runs asynchronously in a sandboxed
container the MultiworldGG bot spawns against the sha256-verified wheel, and is
reported via the separate required `Karen / fuzz` Check Run. The
`karen/fuzz-runs:<N>`, `karen/fuzz-timeout:<sec>`, and `karen/size-cap-mb:<N>`
PR labels tune that bot run. Karen posts a sticky comment with both sets of
results; on all-green fast checks she requests a human CODEOWNER review. See
[Why Oliver opens the PR](why-oliver.md#what-karen-checks).

**Index**
: The MultiworldGG-Index repository
(`https://github.com/MultiworldGG/MultiworldGG-Index`). A list of community
approved APWorlds safe for install, who wrote them, and where to fetch them from.
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
: The automated check suite that runs on every Index PR — Karen's fast manifest
checks on the runner, plus the bot's asynchronous sandboxed scan gated by the
`Karen / fuzz` Check Run. Not a checklist the author must satisfy before
releasing — it runs after the release is cut and reports what it found. Results
are guidance for the human CODEOWNER and other approvers who merge. See
[Why Oliver opens the PR](why-oliver.md).

**wheel (`.whl`)**
: A pip-installable Python package archive. The `build.yml@v3` reusable
workflow produces one per release, named
`worlds.<apworld>-<world_version>-py3-none-any.whl`. This is what Oliver
records in the Index manifest and what the MultiworldGG package manager
installs.

**`.apworld`**
: A zip archive containing a world's source files in a bundle via Archipelago's
Launcher & build pipeline. These are for installing worlds into the `custom_worlds/`
for testing and distributing with Archipelago.
