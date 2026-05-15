# Why Oliver opens the PR for you

When you cut a release, you don't open a PR on the Index yourself. Oliver does.
Here is why that design choice matters, and what it actually protects against.

## The SHA256 pin

Oliver reads the `.whl` asset URL from your release **and** records its SHA256
digest in the `module_location` field of the Index manifest:

```
https://github.com/<you>/<repo>/releases/download/<tag>/<dist>-<ver>-py3-none-any.whl#sha256=<hex>
```

That `#sha256=<hex>` fragment is a [PEP 503](https://peps.python.org/pep-0503/)
direct-reference fragment. When pip installs your world, it verifies the
downloaded bytes against that hash **before** executing any code. If the
release asset is replaced or tampered with after the PR is merged, pip refuses
to install it and raises an error.

This is why Oliver reads the digest at PR-open time — it is a snapshot of what
was on disk at a known point, committed to a repo with an audit trail. An author
who accidentally pushed a broken asset (or a supply-chain attacker who replaced
a stale release) cannot silently land code on users' machines.

## What Karen checks

Karen is the automated reviewer that runs on every Index PR. She runs seven
checks via `scripts/karen_review.py`. The full source is public in this repo
at `.github/workflows/karen-pr-review.yml`.

| Check | What it does |
|---|---|
| **Schema** | Validates the manifest JSON against `schema/world_manifest.schema.json`. |
| **Manifest consistency** | Verifies the filename apworld matches the manifest's contents; catches duplicate JSON keys; checks URL shape. |
| **URL reachability** | Confirms `module_location`, `repo_url`, and `tracker` URLs actually respond. |
| **Size sanity** | Sparse-clones the world source and checks total directory size against a configurable cap (default 250 MB). |
| **No network at import** | Runs a static AST scan on every `.py` file in the world source, looking for top-level network imports or calls that would fire the moment someone does `import worlds.<apworld>`. |
| **Bandit** | Runs `bandit -r` on the cloned world directory at medium severity threshold — catches common Python security anti-patterns like `exec()`, `subprocess` with `shell=True`, hardcoded credentials, etc. |
| **Pip-audit** | Runs `pip-audit` against `requirements.txt` or `pyproject.toml` (if present) to check declared dependencies for known CVEs. |

In addition to Karen's seven-check suite, the workflow runs two further
automated analyses on the world source when a `module_location` pip-installable
URL is present:

- **CodeQL** — GitHub's semantic code analysis engine, run against the world's
  Python source. Results appear in the repo's Security tab, scoped to
  `world/<apworld>` so they don't collide across PRs.
- **Fuzzer** — Eijebong/Archipelago-fuzzer is run against the installed world
  for a configurable number of rounds. A non-zero exit fails the workflow and
  blocks Karen's approval.

!!! note "These checks run for you, not at you"
    None of the checks above are a preflight checklist you have to satisfy
    before cutting a release. You cut the release; Karen and the workflow run
    after. If a check flags something, Karen posts a review comment explaining
    what was found. The human CODEOWNER who merges will weigh in. The framing
    is: "here is what we found, here is why it matters" — not "go fix this
    before we accept you."

    The whole point is that anyone can have a stale reference that turned out
    to be a security breach. A single compromised dependency in a single
    world's transitive tree could otherwise quietly land on every MultiworldGG
    user's machine. Karen exists to catch that automatically.

## Why authors can't push directly to the orphan branches

The `game_index_*` orphan branches (the pip-installable `mwgg_igdb` packages
that the launcher reads) are built from `main` by a scheduled workflow. They
are never pushed manually. This means:

- Every world in the published package went through the `main` PR pipeline,
  including Oliver's SHA256 pin and Karen's automated checks.
- The orphan-branch history is force-pushed on every rebuild, so it is not an
  audit trail. The audit trail is `main`'s commit history of merged PRs.

## Transparency

The checks themselves are open source:

- Karen's seven-check logic: [`scripts/karen_review.py`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/scripts/karen_review.py)
- The full workflow: [`.github/workflows/karen-pr-review.yml`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/.github/workflows/karen-pr-review.yml)

You can read every check before you release. There are no hidden rules.
