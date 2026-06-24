# Basic Manual setup

The Basic Manual path is for authors who already release by hand and want to keep
it that way. You build the `.apworld` and the `.whl` on your own machine, attach
both to a GitHub Release yourself — exactly the way you already attach the
`.apworld` — and publish. There is **no workflow file to commit, no token to
configure, and no CI to learn.** Oliver opens the Index PR from your published
release.

This path is for worlds that live at `worlds/<apworld>/` inside a fork of
`MultiworldGG/MultiworldGG` or `ArchipelagoMW/Archipelago`.

[Continue to the Basic Manual Archipelago-fork setup](from-archipelago-fork.md){ .md-button .md-button--primary }

---

!!! tip "Want the build and upload done for you?"
    If you'd rather a workflow build and attach both assets automatically when you
    publish a release, use the [Standard Automated setup](../standard/index.md).

!!! note "Standalone per-world repos"
    The Basic Manual path is written for worlds inside an Archipelago fork (which
    is how you build the `.apworld` with the fork's own `Launcher.py`). If your
    world lives in its own standalone repository, use the
    [Custom Automated setup from a standalone repo](../custom/from-standalone-repo.md).
