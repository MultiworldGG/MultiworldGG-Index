"""Karen's 7-check quality assurance review for `worlds/<apworld>.json` PRs.

Karen is our quality assurance bot, here to tell you what we maybe want to flag to fix.
If everything is perfect, you'll get her QA stamp of approval.
If it's not perfect, she'll let know what she didn't like. She's not a guard, though,
she can be bypassed by a human.

On every PR open/sync against `main`, the
`karen-pr-review.yml` workflow invokes this script with the list of changed
manifest paths. Each manifest is run through 8 checks:

    1. schema               — JSON-Schema validation against schema/world_manifest.schema.json
    2. manifest_consistency — apworld = filename; URL apworld matches; no duplicate keys
    3. url_reachability     — module_location, repo_url, tracker respond
    4. size_sanity          — world dir size <= cap (overridable via --size-cap-mb)
    5. no_rom_files         — no ROM/media-looking files in the fetched artifact
    6. no_network_at_import — AST scan: no networking calls at module top level
    7. bandit               — bandit -r on the fetched world directory
    8. pip_audit            — pip-audit on requirements.txt / pyproject.toml if present

Checks 4-8 require fetching the world's source. Currently supports
`https://github.com/<org>/<repo>/tree/<ref>/<path>` URLs (sparse-clone of the
referenced subpath) and `git+https://<host>/<org>/<repo>.git@<ref>` URLs
(shallow clone). Direct `.whl` URLs are downloaded and safely expanded before
deep checks run. Other URL shapes are reported as `skip` (with a clear reason in
the comment).

The script writes:
    - a markdown PR comment to --output-comment
    - a machine-readable JSON summary to --output-summary
    - exits 0 on overall pass, 1 on overall fail (any red check)

Usage:
    python scripts/karen_review.py \\
        --changed worlds/oot.json --changed worlds/alttp.json \\
        --schema schema/world_manifest.schema.json \\
        --size-cap-mb 250 \\
        --output-comment karen-comment.md \\
        --output-summary karen-summary.json

When the caller (e.g. the bot's container) has already downloaded and extracted
the wheel, pass --world-dir to run the deep checks against that directory
instead of re-downloading. Only one --changed target is allowed in this mode:
    python scripts/karen_review.py \\
        --changed worlds/oot.json \\
        --schema schema/world_manifest.schema.json \\
        --size-cap-mb 250 \\
        --world-dir /path/to/extracted-wheel \\
        --output-summary scan.json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

PR_COMMENT_MARKER = "<!-- karen-pr-review -->"

DEFAULT_SIZE_CAP_MB = 100

URL_FETCH_TIMEOUT_SECONDS = 10
URL_USER_AGENT = "MultiworldGG-Index-Karen/1.0 (+https://github.com/MultiworldGG/MultiworldGG-Index)"

ALL_CHECKS = (
    "schema",
    "manifest_consistency",
    "url_reachability",
    "size_sanity",
    "no_rom_files",
    "no_network_at_import",
    "bandit",
    "pip_audit",
)
DEEP_CHECKS = frozenset({
    "size_sanity",
    "no_rom_files",
    "no_network_at_import",
    "bandit",
    "pip_audit",
})

ROM_FILE_EXTENSIONS = frozenset({
    ".3ds",
    ".a26",
    ".cci",
    ".cue",
    ".gb",
    ".gba",
    ".gbc",
    ".gcm",
    ".gcz",
    ".iso",
    ".n64",
    ".nds",
    ".nes",
    ".rvz",
    ".sfc",
    ".smc",
    ".sms",
    ".z64",
})

# Removing 'websocket' because well...
NETWORK_MODULES = frozenset({
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "urllib2",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
})

# Top-level call attribute paths that indicate network use. Conservative —
# erring on the side of false positives, which Karen surfaces as warnings.
NETWORK_CALL_PATTERNS = (
    re.compile(r"^urllib(\.[A-Za-z_]+)*\.(urlopen|urlretrieve|Request)$"),
    re.compile(r"^requests\.(get|post|put|delete|head|patch|request)$"),
    re.compile(r"^httpx\.(get|post|put|delete|head|patch|request|Client|AsyncClient)$"),
    re.compile(r"^socket\.(socket|create_connection|gethostbyname)$"),
    re.compile(r"^http\.client\.(HTTPConnection|HTTPSConnection)$"),
)


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "fail" | "warn" | "skip"
    message: str = ""
    details: list[str] = field(default_factory=list)


@dataclass
class WorldReview:
    apworld: str
    manifest_path: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if any(c.status == "fail" for c in self.checks):
            return "fail"
        if any(c.status == "warn" for c in self.checks):
            return "warn"
        return "pass"


@dataclass
class ReviewRun:
    worlds: list[WorldReview] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if any(w.overall == "fail" for w in self.worlds):
            return "fail"
        if any(w.overall == "warn" for w in self.worlds):
            return "warn"
        return "pass"


# ---------------------------------------------------------------------------
# Check implementations


def check_schema(manifest_path: Path, schema_path: Path) -> CheckResult:
    """Validate the manifest against the JSON Schema."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return CheckResult("schema", "fail", "json schema not installed in CI runner")
    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return CheckResult("schema", "fail", f"could not load: {exc}")
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if not errors:
        return CheckResult("schema", "pass", "archipelago.json looking good!")
    details = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
    return CheckResult("schema", "fail", f"{len(errors)} schema violation(s)", details=details)


def check_manifest_consistency(manifest_path: Path) -> CheckResult:
    """Filename apworld = manifest 'apworld'; module_location URL apworld matches; no duplicate keys."""
    apworld = manifest_path.stem
    raw = manifest_path.read_text(encoding="utf-8")

    duplicate_keys: list[str] = []

    def detect_duplicates(pairs: list[tuple[str, object]]) -> dict:
        d: dict = {}
        for k, v in pairs:
            if k in d:
                duplicate_keys.append(k)
            d[k] = v
        return d

    try:
        manifest = json.loads(raw, object_pairs_hook=detect_duplicates)
    except json.JSONDecodeError as exc:
        return CheckResult("manifest_consistency", "fail", f"JSON doesn't look quite right: {exc}")

    issues: list[str] = []
    if duplicate_keys:
        issues.append(f"duplicate keys: {sorted(set(duplicate_keys))}")

    module_location = manifest.get("module_location", "")
    if module_location:
        github_tree = re.match(
            r"^https?://github\.com/[^/]+/[^/]+/tree/[^/]+/(?:.*/)?([^/]+)/?$",
            module_location,
        )
        if github_tree:
            url_apworld = github_tree.group(1)
            if url_apworld != apworld:
                issues.append(
                    f"module_location URL apworld '{url_apworld}' is not what I'm looking for: '{apworld}'"
                )

    if not re.match(r"^[a-z0-9_]+$", apworld):
        issues.append(
            f"apworld '{apworld}' should be lowercase alphanumeric + underscore, not '{apworld}'"
        )

    if issues:
        return CheckResult(
            "manifest_consistency",
            "fail",
            f"{len(issues)} issue(s)",
            details=issues,
        )
    return CheckResult("manifest_consistency", "pass", "filename, url, and JSON shape are all consistent, nice!")


def _http_check(url: str) -> tuple[bool, str]:
    """Return (ok, message). Tries HEAD first, falls back to GET."""
    req = urllib.request.Request(url, headers={"User-Agent": URL_USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=URL_FETCH_TIMEOUT_SECONDS) as resp:
            code = resp.getcode()
            if 200 <= code < 400:
                return True, f"HTTP {code}"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        if exc.code == 405:  # method not allowed -> retry GET
            try:
                req2 = urllib.request.Request(
                    url, headers={"User-Agent": URL_USER_AGENT}, method="GET"
                )
                with urllib.request.urlopen(req2, timeout=URL_FETCH_TIMEOUT_SECONDS) as resp:
                    code = resp.getcode()
                    if 200 <= code < 400:
                        return True, f"HTTP {code} (GET)"
                    return False, f"HTTP {code} (GET)"
            except Exception as exc2:
                return False, f"GET failed: {exc2}"
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"unreachable: {exc}"


def _git_check(url: str) -> tuple[bool, str]:
    """Reachability check for `git+...` URLs via `git ls-remote`.

    `git+https://` and `git+ssh://` are pip's clone-URL convention (PEP 440
    direct references); urllib doesn't know them. Use `git ls-remote` to
    confirm the remote responds AND the referenced ref exists.
    """
    params = _parse_module_location(url)
    if not params:
        return False, f"I couldn't figure out what git URL you're trying to use: {url}"
    clone_url = params["clone_url"]
    ref = params["ref"]
    try:
        result = subprocess.run(
            ["git", "ls-remote", clone_url, ref],
            capture_output=True,
            text=True,
            timeout=URL_FETCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"git ls-remote timed out after {URL_FETCH_TIMEOUT_SECONDS} seconds"
    except OSError as exc:
        return False, f"git ls-remote failed to run because: {exc}"
    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        return False, f"git ls-remote returned code {result.returncode}: {stderr}"
    stdout = result.stdout.strip()
    if not stdout:
        # Could be a SHA pinned ref (ls-remote doesn't list raw SHAs). Accept
        # if the ref looks like a 40-char hex SHA — confirming the SHA is
        # reachable would require a fetch, which is what the size_sanity
        # check does later anyway.
        if re.fullmatch(r"[0-9a-f]{40}", ref):
            return True, f"ref appears to be a SHA; deferring"
        return False, f"ref '{ref}' not found at {clone_url}"
    sha = stdout.split()[0][:8]
    return True, f"ref {ref} resolves to {sha}"


def check_url_reachability(manifest_path: Path, lenient: bool = False) -> CheckResult:
    """HEAD/GET module_location, repo_url, tracker.

    With lenient=True, unreachable URLs degrade to `warn` instead of `fail`. Used
    during the worlds-mirror transition when the canonical URLs are still being
    populated.
    """
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    fields = ("module_location", "repo_url", "tracker")
    results: list[str] = []
    any_failed = False
    for field_name in fields:
        url = manifest.get(field_name)
        if not url:
            continue
        # `git+https://` / `git+ssh://` aren't HTTP — probe via git ls-remote.
        if url.startswith("git+"):
            ok, msg = _git_check(url)
        else:
            ok, msg = _http_check(url)
        marker = "ok" if ok else "FAIL"
        results.append(f"{marker} {field_name}: {url} -> {msg}")
        if not ok:
            any_failed = True
    if not results:
        return CheckResult("url_reachability", "skip", "no URL fields to check")
    if any_failed:
        status = "warn" if lenient else "fail"
        message = (
            "one or more URLs unreachable (lenient: not blocking, but you should fix it)"
            if lenient
            else "one or more URLs unreachable, you should fix it"
        )
        return CheckResult("url_reachability", status, message, details=results)
    return CheckResult(
        "url_reachability", "pass", f"{len(results)} URLs are right where I looked", details=results
    )


def _parse_module_location(url: str) -> Optional[dict]:
    """Parse module_location into clone parameters.

    Returns dict with keys: clone_url, ref, subpath. None if not parseable.
    """
    m = re.match(
        r"^https?://github\.com/(?P<org>[^/]+)/(?P<repo>[^/]+)/tree/(?P<ref>[^/]+)(?P<subpath>/.*)?$",
        url,
    )
    if m:
        subpath = (m.group("subpath") or "").strip("/")
        return {
            "clone_url": f"https://github.com/{m.group('org')}/{m.group('repo')}.git",
            "ref": m.group("ref"),
            "subpath": subpath,
        }
    m = re.match(
        r"^git\+(?P<scheme>https?|ssh)://(?P<rest>[^@]+\.git)(?:@(?P<ref>[^#]+))?$",
        url,
    )
    if m:
        return {
            "clone_url": f"{m.group('scheme')}://{m.group('rest')}",
            "ref": m.group("ref") or "HEAD",
            "subpath": "",
        }
    return None


def _sparse_clone(clone_url: str, ref: str, subpath: str, dest: Path) -> tuple[bool, str]:
    """Sparse-checkout clone. Returns (ok, message). dest will hold the subpath contents directly."""
    work = dest.parent / (dest.name + "__clone")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    try:
        # Initialize, configure sparse, fetch ref, checkout.
        subprocess.run(
            ["git", "init", "-q", "--initial-branch=main"],
            cwd=work,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", clone_url],
            cwd=work,
            check=True,
            capture_output=True,
        )
        if subpath:
            subprocess.run(
                ["git", "sparse-checkout", "init", "--cone"],
                cwd=work,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "sparse-checkout", "set", subpath],
                cwd=work,
                check=True,
                capture_output=True,
            )
        subprocess.run(
            ["git", "fetch", "--depth=1", "--filter=blob:none", "origin", ref],
            cwd=work,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "FETCH_HEAD"],
            cwd=work,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        return False, f"git failed: {stderr or exc}"

    src_dir = work / subpath if subpath else work
    if not src_dir.is_dir():
        return False, f"subpath '{subpath}' missing after clone"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(src_dir), str(dest))
    shutil.rmtree(work, ignore_errors=True)
    return True, "ok"


def _is_wheel_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and Path(parsed.path).suffix.lower() == ".whl"


def _wheel_sha256(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    hashes = urllib.parse.parse_qs(parsed.fragment).get("sha256", [])
    return hashes[0].lower() if hashes else None


def _download_and_expand_wheel(url: str, dest: Path) -> tuple[bool, str]:
    """Download a wheel URL and safely expand it into dest."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    parsed = urllib.parse.urlparse(url)
    download_url = urllib.parse.urlunparse(parsed._replace(fragment=""))
    wheel_path = dest.parent / f"{dest.name}.whl"
    expected_hash = _wheel_sha256(url)
    digest = hashlib.sha256()

    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": URL_USER_AGENT})
        with urllib.request.urlopen(req, timeout=URL_FETCH_TIMEOUT_SECONDS) as response:
            with open(wheel_path, "wb") as wheel:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    wheel.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"wheel download failed: {exc}"

    actual_hash = digest.hexdigest()
    if expected_hash and actual_hash != expected_hash:
        return False, f"wheel SHA256 mismatch: expected {expected_hash}, got {actual_hash}"

    try:
        dest_root = dest.resolve()
        with zipfile.ZipFile(wheel_path) as wheel:
            for member in wheel.infolist():
                target = dest / member.filename
                if not target.resolve().is_relative_to(dest_root):
                    return False, f"wheel contains unsafe path: {member.filename}, you should fix it"
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with wheel.open(member) as source, open(target, "wb") as output:
                    shutil.copyfileobj(source, output)
    except (OSError, zipfile.BadZipFile) as exc:
        return False, f"wheel expansion failed because: {exc}"
    finally:
        try:
            wheel_path.unlink()
        except OSError:
            pass

    return True, "wheel inflated and ready to zoom."


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        # Skip .git inside cloned worlds
        if ".git" in Path(root).parts:
            continue
        for fn in files:
            fp = Path(root) / fn
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def check_size_sanity(world_dir: Path, size_cap_mb: int) -> CheckResult:
    """World dir size <= cap. Override comes from --size-cap-mb at the call site."""
    if not world_dir.is_dir():
        return CheckResult("size_sanity", "skip", "world source not fetched")
    size_bytes = _dir_size_bytes(world_dir)
    size_mb = size_bytes / (1024 * 1024)
    cap_str = f"{size_mb:.1f}MB / cap {size_cap_mb}MB"
    if size_mb > size_cap_mb:
        return CheckResult(
            "size_sanity",
            "fail",
            f"size: DAAAAAMN BRO! {cap_str}",
            details=[
                "You can override this, by setting the 'karen/size-override' label on this PR.",
                "But boy howdy there's probably something wrong there."
            ],
        )
    return CheckResult("size_sanity", "pass", f"a very reasonable {cap_str}")


def check_no_rom_files(world_dir: Path) -> CheckResult:
    """Fail if the fetched artifact contains ROM or disc-image-looking files."""
    if not world_dir.is_dir():
        return CheckResult("no_rom_files", "skip", "nothing to see here, move along")

    rom_paths: list[str] = []
    for path in world_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in ROM_FILE_EXTENSIONS:
            rom_paths.append(path.relative_to(world_dir).as_posix())

    if not rom_paths:
        return CheckResult("no_rom_files", "pass", "no illegal games here")

    rom_paths.sort()
    displayed = rom_paths[:100]
    if len(rom_paths) > len(displayed):
        displayed.append(f"... {len(rom_paths) - len(displayed)} more")

    return CheckResult(
        "no_rom_files",
        "fail",
        f"I found a few files in there you maybe don't want to be shipping: {len(rom_paths)}",
        details=displayed,
    )


def _attribute_chain(node: ast.AST) -> Optional[str]:
    """Reduce 'a.b.c.d' attribute chain to 'a.b.c.d', or None if not a pure chain."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _scan_module_for_network(path: Path) -> tuple[list[str], list[str]]:
    """Walk a single .py file's AST.

    Returns (calls, imports):
      calls   — top-level network *call* statements (fail-level: actual side effect)
      imports — top-level imports of network modules (warn-level: imports themselves
                are harmless but a human reviewer should know they're present)

    We deliberately ignore nested-in-function network use: at-import-time is what
    matters; runtime network is the world's job.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return [], []
    calls: list[str] = []
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in NETWORK_MODULES:
                    imports.append(f"top-level `import {alias.name}` at line {node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in NETWORK_MODULES or mod.split(".")[0] in NETWORK_MODULES:
                imports.append(f"top-level `from {mod} import ...` at line {node.lineno}")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            chain = _attribute_chain(node.value.func)
            if chain and any(p.match(chain) for p in NETWORK_CALL_PATTERNS):
                calls.append(f"top-level `{chain}(...)` call at line {node.lineno}")
    return calls, imports


def check_no_network_at_import(world_dir: Path) -> CheckResult:
    """Static AST scan for top-level network use. Cheaper and safer than actually importing."""
    if not world_dir.is_dir():
        return CheckResult("no_network_at_import", "skip", "nada")
    flagged_calls: list[str] = []
    flagged_imports: list[str] = []
    for py in world_dir.rglob("*.py"):
        if any(part in {".git", "__pycache__"} for part in py.parts):
            continue
        rel = py.relative_to(world_dir)
        calls, imports = _scan_module_for_network(py)
        flagged_calls.extend(f"{rel}: {c}" for c in calls)
        flagged_imports.extend(f"{rel}: {i}" for i in imports)
    if flagged_calls:
        return CheckResult(
            "no_network_at_import",
            "fail",
            f"A couple network calls in there that run immediately, I'm not a fan.",
            details=flagged_calls + flagged_imports,
        )
    if flagged_imports:
        return CheckResult(
            "no_network_at_import",
            "warn",
            f"{len(flagged_imports)} top-level network module imports, these are probably ok, but check them out.",
            details=flagged_imports,
        )
    return CheckResult(
        "no_network_at_import",
        "pass",
        "Only network I see is the one I'm responding on.",
    )


def check_bandit(world_dir: Path) -> CheckResult:
    """Run bandit -r on the world directory. Medium severity threshold."""
    if not world_dir.is_dir():
        return CheckResult("bandit", "skip", "zilch")
    if shutil.which("bandit") is None:
        return CheckResult("bandit", "fail", "I hired a bandit, but it looks like they bailed.")
    proc = subprocess.run(
        [
            "bandit",
            "-r",
            str(world_dir),
            "-f",
            "json",
            "-q",
            "--severity-level",
            "medium",
        ],
        capture_output=True,
        text=True,
    )
    # bandit exits 1 when issues found, 0 when clean. JSON is on stdout regardless.
    try:
        report = json.loads(proc.stdout) if proc.stdout else {}
    except json.JSONDecodeError:
        return CheckResult(
            "bandit",
            "fail",
            "Bandit doesn't speak JSON today, maybe try again later?",
            details=[(proc.stdout or "")[-500:]],
        )
    results = report.get("results", [])
    if not results:
        return CheckResult("bandit", "pass", "Bandit didn't make out with anything worth mentioning.")
    details = [
        f"{r.get('filename', '?')}:{r.get('line_number', '?')} "
        f"[{r.get('test_id', '?')}/{r.get('issue_severity', '?')}] "
        f"{r.get('issue_text', '')}"
        for r in results
    ]
    return CheckResult("bandit", "fail", f"{len(results)} issues(s), we should look it over.", details=details)


def check_pip_audit(world_dir: Path) -> CheckResult:
    """Run pip-audit on requirements.txt or pyproject.toml if either exists."""
    if not world_dir.is_dir():
        return CheckResult("pip_audit", "skip", "no requirements, no problems")
    if shutil.which("pip-audit") is None:
        return CheckResult("pip_audit", "fail", "Uh, guys? Where's my pip-audit?")

    targets: list[list[str]] = []
    req = world_dir / "requirements.txt"
    pyproj = world_dir / "pyproject.toml"
    if req.is_file():
        targets.append(["pip-audit", "-r", str(req), "--format", "json"])
    if pyproj.is_file() and not req.is_file():
        # pip-audit can read pyproject via project-path
        targets.append(["pip-audit", "--project-path", str(world_dir), "--format", "json"])
    if not targets:
        return CheckResult("pip_audit", "skip", "no requirements, no problems")

    all_vulns: list[str] = []
    for cmd in targets:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            report = json.loads(proc.stdout) if proc.stdout else {}
        except json.JSONDecodeError:
            return CheckResult(
                "pip_audit",
                "fail",
                "pip-audit gave me a funky JSON response",
                details=[(proc.stdout or "")[-500:]],
            )
        for dep in report.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                all_vulns.append(
                    f"{dep.get('name')}=={dep.get('version')}: "
                    f"{vuln.get('id')} ({vuln.get('description', '')[:80]})"
                )
    if not all_vulns:
        return CheckResult("pip_audit", "pass", "We are up to date and ready to roll.")
    return CheckResult(
        "pip_audit",
        "fail",
        "There are a few scary packages in there, let's check them out.`",
        details=all_vulns,
    )


# ---------------------------------------------------------------------------
# Driver


def review_one(
    manifest_path: Path,
    schema_path: Path,
    size_cap_mb: int,
    workdir: Path,
    selected_checks: frozenset[str],
    lenient_urls: bool = False,
    world_dir_override: Optional[Path] = None,
) -> WorldReview:
    """Review a single manifest.

    When ``world_dir_override`` is given, the download/clone/fetch step is
    skipped entirely and the deep checks run directly against that already-
    extracted directory (treated as the expanded wheel's ``world_dir``). This
    is how the bot's container reuses a wheel it has already downloaded and
    unzipped, e.g.::

        review_one(
            Path("worlds/oot.json"),
            Path("schema/world_manifest.schema.json"),
            250,
            Path("/tmp/karen-workdir"),
            selected_checks=DEEP_CHECKS,
            world_dir_override=Path("/tmp/extracted"),
        )
    """
    apworld = manifest_path.stem
    review = WorldReview(apworld=apworld, manifest_path=str(manifest_path))

    # Fast checks (no network / clone)
    if "schema" in selected_checks:
        review.checks.append(check_schema(manifest_path, schema_path))
    if "manifest_consistency" in selected_checks:
        review.checks.append(check_manifest_consistency(manifest_path))
    if "url_reachability" in selected_checks:
        review.checks.append(check_url_reachability(manifest_path, lenient=lenient_urls))

    # Skip the clone entirely if no deep checks were selected.
    deep_selected = selected_checks & DEEP_CHECKS
    if not deep_selected:
        return review

    # The bot's container may have already downloaded and extracted the wheel.
    # In that case, point the deep checks straight at it — no re-download.
    if world_dir_override is not None:
        world_dir = world_dir_override
        fetched = world_dir.is_dir()
        fetch_message = "" if fetched else f"--world-dir not a directory: {world_dir}"
        return _run_deep_checks(
            review, world_dir, size_cap_mb, selected_checks, lenient_urls, fetched, fetch_message
        )

    # Try to fetch the world for the deeper checks.
    world_dir = workdir / apworld
    fetched = False
    fetch_message = ""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        url = manifest.get("module_location", "")
        if _is_wheel_url(url):
            ok, msg = _download_and_expand_wheel(url, world_dir)
            if ok:
                fetched = True
            else:
                fetch_message = msg
        else:
            params = _parse_module_location(url)
            if params is None:
                fetch_message = f"module_location URL shape not supported by Karen yet: {url}"
            else:
                ok, msg = _sparse_clone(
                    params["clone_url"], params["ref"], params["subpath"], world_dir
                )
                if ok:
                    fetched = True
                else:
                    fetch_message = msg
    except (OSError, json.JSONDecodeError) as exc:
        fetch_message = f"could not load manifest for fetch: {exc}"

    return _run_deep_checks(
        review, world_dir, size_cap_mb, selected_checks, lenient_urls, fetched, fetch_message
    )


def _run_deep_checks(
    review: WorldReview,
    world_dir: Path,
    size_cap_mb: int,
    selected_checks: frozenset[str],
    lenient_urls: bool,
    fetched: bool,
    fetch_message: str,
) -> WorldReview:
    """Append the selected deep checks to ``review``, running them against
    ``world_dir``. When ``fetched`` is False the deep checks are recorded as
    skipped (or pass-with-note in lenient mode) with ``fetch_message``."""
    if not fetched:
        # Mark deeper checks as skipped (lenient mode: pass-with-note instead).
        skip_status = "pass" if lenient_urls else "skip"
        skip_message = (
            "world source not fetched (lenient: not blocking)"
            if lenient_urls
            else "world source not fetched"
        )
        for name in ("size_sanity", "no_rom_files", "no_network_at_import", "bandit", "pip_audit"):
            if name in selected_checks:
                review.checks.append(
                    CheckResult(name, skip_status, skip_message, details=[fetch_message])
                )
        return review

    if "size_sanity" in selected_checks:
        review.checks.append(check_size_sanity(world_dir, size_cap_mb))
    if "no_rom_files" in selected_checks:
        review.checks.append(check_no_rom_files(world_dir))
    if "no_network_at_import" in selected_checks:
        review.checks.append(check_no_network_at_import(world_dir))
    if "bandit" in selected_checks:
        review.checks.append(check_bandit(world_dir))
    if "pip_audit" in selected_checks:
        review.checks.append(check_pip_audit(world_dir))

    return review


_STATUS_GLYPH = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}


_DETAILED_RENDER_THRESHOLD = 20


def render_comment(run: ReviewRun) -> str:
    overall_glyph = _STATUS_GLYPH[run.overall]
    if len(run.worlds) > 1:
        overall_text = f"**Overall:** {overall_glyph} {run.overall.upper()} ({len(run.worlds)} world(s) checked)"
    else:
        overall_text = f"**TLDR:** {run.worlds[0].apworld} is {overall_glyph}"
    lines = [
        PR_COMMENT_MARKER,
        "## Karen: Quality Assurance Manager",
        "",
        "Here to give a seal of quality to your APWorld, because no one wants to be a vector for an exploit.",
        overall_text,
        "",
    ]
    # Compact mode: when many worlds are in scope (e.g. schema change re-validates
    # ALL manifests), only render fail/warn worlds in detail and roll passes into
    # a single summary line.
    compact = len(run.worlds) > _DETAILED_RENDER_THRESHOLD
    detailed_worlds = [w for w in run.worlds if w.overall in ("fail", "warn")] if compact else run.worlds

    if compact:
        passed = [w for w in run.worlds if w.overall == "pass"]
        if passed:
            lines.append(f"{_STATUS_GLYPH['pass']} **{len(passed)} world(s) passed:** "
                         + ", ".join(f"`{w.apworld}`" for w in passed[:50])
                         + ("…" if len(passed) > 50 else ""))
            lines.append("")

    for w in detailed_worlds:
        lines.append(f"### `{w.apworld}` — {_STATUS_GLYPH[w.overall]} {w.overall}")
        lines.append("")
        lines.append("| Check | Status | Notes |")
        lines.append("| --- | --- | --- |")
        for c in w.checks:
            note = c.message.replace("|", "\\|") if c.message else ""
            lines.append(f"| `{c.name}` | {_STATUS_GLYPH[c.status]} {c.status} | {note} |")
        details = [
            (c.name, c.details) for c in w.checks if c.details and c.status in ("fail", "warn")
        ]
        if details:
            lines.append("")
            lines.append("<details><summary>Details</summary>")
            lines.append("")
            for name, det in details:
                lines.append(f"**{name}**")
                lines.append("")
                for d in det:
                    lines.append(f"- {d}")
                lines.append("")
            lines.append("</details>")
        lines.append("")
    if run.overall == "pass":
        lines.append("All checks green, awesome job!")
    elif run.overall == "warn":
        lines.append("A few warnings to check out, but nothing too serious.")
    else:
        lines.append("There are some problems I'm not willing to overlook. Please fix them and try again.")
    lines.append("")
    return "\n".join(lines)


def render_summary(run: ReviewRun) -> dict:
    return {
        "overall": run.overall,
        "worlds": [
            {
                "apworld": w.apworld,
                "manifest_path": w.manifest_path,
                "overall": w.overall,
                "checks": [
                    {
                        "name": c.name,
                        "status": c.status,
                        "message": c.message,
                        "details": c.details,
                    }
                    for c in w.checks
                ],
            }
            for w in run.worlds
        ],
    }


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Karen's quality assurance review for apworld releases.")
    parser.add_argument(
        "--changed",
        action="append",
        default=[],
        help="Path to a changed manifest file (worlds/<apworld>.json). Repeatable.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schema/world_manifest.schema.json"),
    )
    parser.add_argument(
        "--size-cap-mb",
        type=int,
        default=DEFAULT_SIZE_CAP_MB,
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        choices=ALL_CHECKS,
        help=(
            "Limit to specific checks. Repeatable. Default: run all 8. "
            "Use to run a fast subset (e.g. --check schema --check manifest_consistency) "
            "when validating all worlds at once."
        ),
    )
    parser.add_argument(
        "--lenient-urls",
        action="store_true",
        help=(
            "Downgrade url_reachability fails to warns and convert deep-check "
            "fetch-skips to pass-with-note. Used during the worlds-mirror "
            "transition when canonical URLs aren't populated yet."
        ),
    )
    parser.add_argument(
        "--world-dir",
        type=Path,
        default=None,
        help=(
            "Run the deep checks against this already-extracted wheel directory "
            "instead of downloading/cloning. Only valid with a single --changed "
            "target (the bot's container reviews one world at a time)."
        ),
    )
    parser.add_argument("--output-comment", type=Path, default=None)
    parser.add_argument("--output-summary", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.world_dir is not None and len(args.changed) > 1:
        parser.error("--world-dir is only valid with a single --changed target")

    selected_checks = frozenset(args.check) if args.check else frozenset(ALL_CHECKS)

    if not args.changed:
        # No changed manifests — pass trivially. Still emit empty outputs so
        # downstream workflow steps don't have to special-case.
        run = ReviewRun(worlds=[])
        if args.output_comment:
            args.output_comment.write_text(
                f"{PR_COMMENT_MARKER}\n## Karen's review\n\nNo new or updated index entries in this PR.\n",
                encoding="utf-8",
            )
        if args.output_summary:
            args.output_summary.write_text(
                json.dumps(render_summary(run), indent=2), encoding="utf-8"
            )
        return 0

    with tempfile.TemporaryDirectory(prefix="karen-") as tmpdir:
        workdir = Path(tmpdir)
        run = ReviewRun()
        for raw in args.changed:
            manifest_path = Path(raw)
            if not manifest_path.is_file():
                review = WorldReview(apworld=manifest_path.stem, manifest_path=str(manifest_path))
                review.checks.append(
                    CheckResult("schema", "fail", f"file not found: {manifest_path}")
                )
                run.worlds.append(review)
                continue
            run.worlds.append(
                review_one(
                    manifest_path,
                    args.schema,
                    args.size_cap_mb,
                    workdir,
                    selected_checks=selected_checks,
                    lenient_urls=args.lenient_urls,
                    world_dir_override=args.world_dir,
                )
            )

    if args.output_comment:
        args.output_comment.write_text(render_comment(run), encoding="utf-8")
    if args.output_summary:
        args.output_summary.write_text(
            json.dumps(render_summary(run), indent=2), encoding="utf-8"
        )

    return 0 if run.overall != "fail" else 1


if __name__ == "__main__":
    sys.exit(_cli())
