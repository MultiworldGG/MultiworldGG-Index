# Advanced setup — choose your repo shape

The advanced path is for authors who want to write their own `pyproject.toml`:
non-default Python dependencies, custom classifiers, extra entry points (beyond
the auto-discovered `mwgg.client`), or multiple worlds in one repo.

You still use the same reusable workflows as the easy path. The difference is
that the build picks up your `pyproject.toml` from `worlds/<apworld>/` when it
exists, and only injects the fields that are missing.

Choose whichever description fits your repo:

---

## My code lives in a fork of MultiworldGG/Archipelago

[Go to: Advanced setup from an Archipelago fork](from-archipelago-fork.md){ .md-button .md-button--primary }

---

## My code lives in its own standalone repo

[Go to: Advanced setup from a standalone repo](from-standalone-repo.md){ .md-button .md-button--primary }

---

!!! note "Compatibility branches"
    If you need to support multiple MultiworldGG versions simultaneously, see
    [Compatibility branches](compatibility-branches.md) after you have the
    basic release pipeline working.
