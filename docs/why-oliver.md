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

Karen is the fabulous automated reviewer that runs on every Index PR. Her work
splits across two stages: the fast manifest checks she runs herself on the
GitHub Actions runner, and the heavier security/quality scan that the
MultiworldGG bot runs asynchronously in a hardened sandbox. The full source is
public in this repo at `.github/workflows/karen-pr-review.yml` and
`scripts/karen_review.py`.

### Fast manifest checks (on the runner)

These are pure metadata checks. They never download the wheel or execute world
code, so they finish in seconds. Karen runs them inline and they are what her
`APPROVE` is based on:

| Check | What it does |
|---|---|
| **Schema** | Validates the manifest JSON against `schema/world_manifest.schema.json`. |
| **Manifest consistency** | Verifies the filename apworld matches the manifest's contents; catches duplicate JSON keys; checks URL shape. |
| **URL reachability** | Confirms `module_location`, `repo_url`, and `tracker` URLs actually respond. |

When all three pass, Karen posts her green sticky comment and submits her
`APPROVE` review. Her approval is **fast-checks-only** — it does not wait on the
sandbox. The sandbox is a separate branch-protection gate (see below), so a PR
still cannot merge until that gate is satisfied.

### Sandboxed security & quality scan (the bot)

Everything that has to fetch the wheel and look inside it now runs
asynchronously, off the runner, in a container the MultiworldGG GitHub bot
spawns for the PR. The bot downloads the wheel from `module_location`, verifies
the bytes against the `#sha256=<hex>` pin **before** unpacking, and only then
runs, against that exact verified wheel:

| Scan | What it does |
|---|---|
| **Size sanity** | Checks the unpacked world's total size against a configurable cap (default 250 MB). |
| **No ROM files** | Walks the world tree and fails if any file has a ROM or disc-image extension (for example `.nes`, `.smc`, `.iso`, `.nds`, `.gba`). |
| **No network at import** | Runs a static AST scan on every `.py` file, looking for top-level network imports or calls that would fire the moment someone does `import worlds.<apworld>`. |
| **Bandit** | Runs `bandit -r` on the world directory at medium severity threshold — catches common Python security anti-patterns like `exec()`, `subprocess` with `shell=True`, hardcoded credentials, etc. |
| **Pip-audit** | Runs `pip-audit` against `requirements.txt` or `pyproject.toml` (if present) to check declared dependencies for known CVEs. |
| **Ruff quality lint** | Runs a `ruff` lint pass over the world source for quality and obvious-bug signals. |
| **Generation fuzz** | Drives the installed world through repeated randomised generation, surfacing crashes and option-handling bugs that only appear at generate time. |

Running this in the bot's sandbox — rather than on the public-PR runner — means
untrusted world code is unpacked and exercised in an isolated, hardened
environment instead of in a workflow that has a write-scoped token. Because the
scan runs against the sha256-verified wheel, it is checking the exact artifact
that pip will later install, not a re-clone of the source.

The bot reports its result through a dedicated **`Karen / fuzz`** Check Run on
the PR head, and writes its findings into a fenced section of Karen's sticky
comment. `Karen / fuzz` is configured as a **required** status in branch
protection, so it is the gate that holds the merge — independently of Karen's
own fast-check `APPROVE`. A failing scan fails that Check Run and blocks merge;
it does not retroactively change Karen's manifest-check approval.

!!! note "These checks run for you, not at you"
    None of the checks above are a preflight checklist you have to satisfy
    before cutting a release. You cut the release; Karen's fast checks and the
    bot's sandboxed scan both run after. If anything flags, Karen posts a review
    comment explaining what was found — the bot's findings land in the fenced
    section of that same comment. The human CODEOWNER who merges will weigh in.
    The framing is: "here is what we found, here is why it matters" — not "go fix
    this before we accept you." (But in some cases, "go fix this")

    The whole point is that anyone can have a stale reference that turned out
    to be a security breach. A single compromised dependency in a single
    world's transitive tree could otherwise quietly land on every 
    user's machine. Karen exists to catch that automatically.

## Transparency

The checks themselves are open source:

- Karen's check logic (both the fast manifest checks and the sandbox scans): [`scripts/karen_review.py`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/scripts/karen_review.py)
- The full workflow: [`.github/workflows/karen-pr-review.yml`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/.github/workflows/karen-pr-review.yml)

You can read every check before you release. There are no hidden rules.
