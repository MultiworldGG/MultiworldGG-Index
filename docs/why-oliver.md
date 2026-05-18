# Why Oliver opens the PR for you

When you cut a release, the owner of the webhost that is hosting your apworld
doesn't move your world into their repository. In fact, your world stays exactly 
where you released it - with you.
Instead we have an index of release locations, and you don't open a PR on the 
Index yourself. Oliver does.

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
with a compromised repo cannot silently land code on users' machines.

## What Karen checks

Karen is the fabulous automated reviewer that runs on every Index PR. She runs eight
checks via `scripts/karen_review.py`. The full source is public in this repo
at `.github/workflows/karen-pr-review.yml`.

| Check | What it does |
|---|---|
| **Schema** | Validates the manifest JSON against `schema/world_manifest.schema.json`. |
| **Manifest consistency** | Verifies the filename apworld matches the manifest's contents; catches duplicate JSON keys; checks URL shape. |
| **URL reachability** | Confirms `module_location`, `repo_url`, and `tracker` URLs actually respond. |
| **Size sanity** | Sparse-clones the world source and checks total directory size against a configurable cap (default 250 MB). |
| **No ROM files** | Walks the cloned world tree and fails if any file has a ROM or disc-image extension (for example `.nes`, `.smc`, `.iso`, `.nds`, `.gba`). |
| **No network at import** | Runs a static AST scan on every `.py` file in the world source, looking for top-level network imports or calls that would fire the moment someone does `import worlds.<apworld>`. |
| **Bandit** | Runs `bandit -r` on the cloned world directory at medium severity threshold — catches common Python security anti-patterns like `exec()`, `subprocess` with `shell=True`, hardcoded credentials, etc. |
| **Pip-audit** | Runs `pip-audit` against `requirements.txt` or `pyproject.toml` (if present) to check declared dependencies for known CVEs. |

In addition to Karen's eight-check suite, the workflow runs two further
automated analyses on the world source when a `module_location` pip-installable
URL is present:

- **CodeQL** — GitHub's semantic code analysis engine, run against the world's
  Python source. Results appear in the repo's Security tab, scoped to
  `world/<apworld>` so they don't collide across PRs.
- **Fuzzer** — Eijebong/Archipelago-fuzzer is run against the installed world
  for I don't remember how many rounds. A non-zero exit fails the workflow and
  blocks Karen's approval (this will be improved upon at I don't know when)

!!! note "These checks run for you, not at you"
    None of the checks above are a preflight checklist you have to satisfy
    before cutting a release. You cut the release; Karen and the workflow run
    after. If a check flags something, Karen posts a review comment explaining
    what was found. The human CODEOWNER who merges will weigh in. The framing
    is: "here is what we found, here is why it matters" — not "go fix this
    before we accept you." (But in some cases, "go fix this")

    The whole point is that anyone can have a stale reference that turned out
    to be a security breach. A single compromised dependency in a single
    world's transitive tree could otherwise quietly land on every 
    user's machine. Karen exists to catch that automatically.

## Transparency

The checks themselves are open source:

- Karen's eight-check logic: [`scripts/karen_review.py`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/scripts/karen_review.py)
- The full workflow: [`.github/workflows/karen-pr-review.yml`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/.github/workflows/karen-pr-review.yml)

You can read every check before you release. There are no hidden rules.
