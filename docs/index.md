# MultiworldGG-Index — APWorld author guide

This site is for APWorld authors who want their game to show up in the
MultiworldGG launcher and webhost, be installable by players, and want
to release hotfixes on their own schedule without needing to request
a full release of *everything*

"That's great, but I want it to stay how it is."
Hey, don't worry about it! We'll run the workflow for you the same way we've
been doing it since we started.

But if you're interested in a little more automation...

## Choose your path

=== "I want the easiest setup"

    You copy in one workflow file and install one GitHub App. You run one script
    which creates a draft release; clicking **Publish** is how you'll release to Oliver.

    - **[My code lives in a fork of Archipelago](easy/from-archipelago-fork.md)**
      — worlds live at `worlds/<apworld>/` inside a fork of
      `Archipelago`.

    [Get started with the easiest setup](easy/index.md){ .md-button .md-button--primary }

=== "I love automation and know what I want. Give me the components, I got this."

    You want a custom `pyproject.toml`, custom classifiers, explicit entry
    points, multiple worlds in one repo, or you already have a release workflow.
    You still use the same reusable workflows, but you own the caller workflow.

    - **[My code lives in a fork of Archipelago](advanced/from-archipelago-fork.md)**
    - **[My code lives in its own standalone repo](advanced/from-standalone-repo.md)**

    [Get started with the advanced setup](advanced/index.md){ .md-button }

---

## What a release looks like

When you cut a GitHub release on your per-world repo:

1. A reusable workflow builds a pip-installable wheel from your `worlds/<apworld>/` directory and attaches it to the release.
2. **Oliver** (Oliver-the-Multiworld-Squirrel GitHub App) sees your published release, reads the wheel asset URL and its SHA256 digest, and opens a PR on this Index repo that records exactly where your world lives.
3. **Karen** (Karen-the-Multiworld-Knight GitHub App) runs her security check suite on the PR and posts a summary comment.
4. On green, Karen requests review from a human CODEOWNER, who approves and merges.
5. The next daily rebuild picks up the merged manifest and publishes it to the `mwgg_igdb` package that the MultiworldGG launcher reads.

Players who install MultiworldGG get your world automatically at their next update.

!!! note "Why does Oliver open the PR for me?"
    Oliver pins your wheel asset URL with a `#sha256=<hex>` fragment so pip
    refuses to install bytes that don't match what was on disk when the PR
    was opened. Karen then runs automated security checks on top of that.
    This is a feature, not a bureaucratic hurdle. [Read the full explanation.](why-oliver.md)

!!! tip "Already shipping `.apworld` files with an older workflow?"
    If you have a workflow that zips your world manually, you can replace it
    with the setup below. Your existing release tags are fine; tags going
    forward must follow the `<apworld>-<version>` format.
    Jump to [Easy setup from an Archipelago fork](easy/from-archipelago-fork.md)
    for the migration callout.

---


## Quick links

- [Glossary](glossary.md) — apworld, slug, Oliver, Karen, module_location, and more
- [Troubleshooting](reference/troubleshooting.md) — Oliver didn't open a PR? Workflow failed?
- [archipelago.json schema reference](reference/archipelago-json.md)
- [Reusable workflow reference](reference/workflows.md)
- [Oliver /status page](https://oliver.multiworld.gg/status)
