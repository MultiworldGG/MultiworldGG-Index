# Easy setup — choose your repo shape

The easy path gives you a working release pipeline in three steps: install one
GitHub App, set one variable, and paste one workflow file. No `pyproject.toml`
to write, no build tooling to configure.

Choose whichever description fits your repo:

---

## My code lives in a fork of MultiworldGG/Archipelago

Your world's source is at `worlds/<apworld>/` inside a fork of
`MultiworldGG/MultiworldGG` or an older `ArchipelagoMW/Archipelago` fork.

[Go to: Easy setup from an Archipelago fork](from-archipelago-fork.md){ .md-button .md-button--primary }

---

## My code lives in its own standalone repo

Your world lives in its own repository with `worlds/<apworld>/` at the root —
not a full MultiworldGG fork.

[Go to: Easy setup from a standalone repo](from-standalone-repo.md){ .md-button .md-button--primary }

---

!!! tip "Need more control?"
    If you have non-default Python dependencies, multiple worlds in one repo,
    or custom classifiers, the [advanced setup](../advanced/index.md) shows
    how to drop a `pyproject.toml` next to your `archipelago.json` and have
    the build pick it up automatically.
