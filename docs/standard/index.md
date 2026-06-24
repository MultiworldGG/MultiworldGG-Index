# Standard Automated setup

The Standard Automated path gives you a working release pipeline in two steps:
install one GitHub App and paste one workflow file. When it is time to release, a
helper script creates a draft GitHub Release for you to review and publish. No
`pyproject.toml` to write, no build tooling to configure.

This path is for worlds that live at `worlds/<apworld>/` inside a fork of
`MultiworldGG/MultiworldGG` or `ArchipelagoMW/Archipelago`.

[Continue to the Standard Automated Archipelago-fork setup](from-archipelago-fork.md){ .md-button .md-button--primary }

---

!!! tip "Don't want any automation?"
    If you'd rather build the `.whl` locally and attach it to your release by
    hand — no workflow file, no tokens — use the
    [Basic Manual setup](../manual/from-archipelago-fork.md) instead.

!!! note "Standalone per-world repos"
    If your world lives in its own standalone repository — not inside a
    MultiworldGG fork — this path does not apply. Use the
    [Custom Automated setup from a standalone repo](../custom/from-standalone-repo.md)
    instead. It is the maintained path for that shape.

!!! tip "Need more control?"
    If you have non-default Python dependencies, multiple worlds in one repo,
    or custom classifiers, the [Custom Automated setup](../custom/index.md) shows
    how to drop a `pyproject.toml` next to your `archipelago.json` and have
    the build pick it up automatically.
