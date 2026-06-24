# MultiworldGG-Index — APWorld author guide

This site is for APWorld authors who want their game to show up in the
MultiworldGG launcher and webhost, be installable by players, and to release
hotfixes on their own schedule without needing to request a full release of
*everything*.

There are three ways to publish, from fully by-hand to fully automated. If you
already build your `.apworld` and cut releases yourself and want to keep it that
way, start with **Basic Manual** — it adds exactly one local step (building the
`.whl`) and changes nothing else about your routine. Want it to stay how it is?
Don't worry — we'll keep running the workflow for you the same way we always have.

## Choose your path

=== "Basic — manual, no automation"

    You build the `.apworld` and `.whl` locally and attach both to your GitHub
    Release by hand, then publish. Install Oliver once and it opens the Index PR.
    No workflow files, no tokens, no CI.

    - **[My code lives in a fork of Archipelago](manual/from-archipelago-fork.md)**
      — worlds live at `worlds/<apworld>/` inside a fork of `Archipelago`.

    [Get started with the Basic Manual setup](manual/index.md)

=== "Standard — automated"

    You copy in one workflow file and install one GitHub App. You run one script
    which creates a draft release; clicking **Publish** is how you'll release to Oliver.

    - **[My code lives in a fork of Archipelago](standard/from-archipelago-fork.md)**

    [Get started with the Standard Automated setup](standard/index.md)

=== "Custom — automated"

    You want a custom `pyproject.toml`, custom classifiers, explicit entry
    points, multiple worlds in one repo, or you already have a release workflow.
    You still use the same reusable workflows, but you own the caller workflow.

    - **[My code lives in a fork of Archipelago](custom/from-archipelago-fork.md)**
    - **[My code lives in its own standalone repo](custom/from-standalone-repo.md)**

    [Get started with the Custom Automated setup](custom/index.md)

---

## What a release looks like

When you cut a GitHub release on your per-world repo:

1. A pip-installable wheel is built from your `worlds/<apworld>/` directory and attached to the release — by a reusable workflow on the automated paths, or by you on the Basic Manual path.
2. **Oliver** (Oliver-the-Multiworld-Squirrel GitHub App) sees your published release, reads the wheel asset URL and its SHA256 digest, and opens a PR on this Index repo that records exactly where your world lives.
3. **Karen** (Karen-Head-of-Multiworld-QA GitHub App) runs her security check suite on the PR and posts a summary comment.
4. On green, Karen requests review from a human CODEOWNER, who approves and merges.
5. The next daily rebuild picks up the merged manifest and publishes it to the `mwgg_igdb` package that the MultiworldGG launcher reads.

Players who install MultiworldGG get your world automatically at their next update.

!!! note "Why does Oliver open the PR for me?"
    Oliver pins your wheel asset URL with a `#sha256=<hex>` fragment so pip
    refuses to install bytes that don't match what was on disk when the PR
    was opened. Karen then runs automated security checks on top of that.
    This is a feature, not a bureaucratic hurdle. [Read the full explanation.](why-oliver.md)

!!! tip "Already shipping `.apworld` files with your own workflow?"
    If you have a workflow that zips your world into a `.apworld` manually, you can
    replace it with any of the paths above. To drop CI entirely and release by
    hand, see [Basic Manual](manual/from-archipelago-fork.md). For the automated
    route, tags going forward must follow the `<apworld>-<version>` format — see
    [Standard Automated from an Archipelago fork](standard/from-archipelago-fork.md).

---


## Quick links

- [Glossary](glossary.md) — apworld, Oliver, Karen, module_location, and more
- [FAQ](faq.md) — publishing by hand, opening the Index PR yourself
- [Troubleshooting](reference/troubleshooting.md) — Oliver didn't open a PR? Workflow failed?
- [archipelago.json schema reference](reference/archipelago-json.md)
- [Reusable workflow reference](reference/workflows.md)
- [Oliver /status page](https://oliver.multiworld.gg/status)
