# Easy setup

The easy path gives you a working release pipeline in two steps: install one
GitHub App and paste one workflow file. When it is time to release, a helper
script creates a draft GitHub Release for you to review and publish. No
`pyproject.toml` to write, no build tooling to configure.

The easy path is for worlds that live at `worlds/<apworld>/` inside a fork of
`MultiworldGG/MultiworldGG` (or an older `ArchipelagoMW/Archipelago` fork).

[Continue to the easy Archipelago-fork setup](from-archipelago-fork.md){ .md-button .md-button--primary }

---

!!! note "Standalone per-world repos"
    If your world lives in its own standalone repository — not inside a
    MultiworldGG fork — the easy path does not apply. Use the
    [advanced setup from a standalone repo](../advanced/from-standalone-repo.md)
    instead. It is the maintained path for that shape.

!!! tip "Need more control?"
    If you have non-default Python dependencies, multiple worlds in one repo,
    or custom classifiers, the [advanced setup](../advanced/index.md) shows
    how to drop a `pyproject.toml` next to your `archipelago.json` and have
    the build pick it up automatically.
