"""IGDB game details for the MultiworldGG-Index repo.

Reads `worlds/<apworld>.json` for one or more apworlds, queries IGDB for the matching
game's metadata, and updates `output/igdb_game_details.json` in place. Existing
entries for unaffected apworlds are preserved.

Triggered by `.github/workflows/igdb-game-details.yml` on every push to `main` that
touches `worlds/*.json`. Can also be run locally:

    IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... \\
        python scripts/igdb_game_details.py --apworld oot --apworld alttp

    # Re-fetch game details for every world (slow, hits rate limits -- use sparingly):
    IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... \\
        python scripts/igdb_game_details.py --all

    # Re-run just the whole-file passes over the existing file (no credentials needed):
    python scripts/igdb_game_details.py --postprocess-only

Every write ends with `postprocess()`, which folds in the two passes the old
pipeline ran as separate scripts after each fetch
(`convert_to_readable_outputs.py`, `remove_specific_keywords.py`): epoch release
dates become years, rare and blocklisted keywords are culled, and entries whose
world manifest is gone are pruned. Keyword frequencies are corpus-wide, so these
passes run over the merged file rather than over the freshly fetched rows alone.

Adapted from the original `tools/game_indexing/igdb.py` in the MultiworldGG alpha client, with
file-based credential / token caching replaced by environment variables and
the manifest-walking removed (the Index repo's `worlds/<apworld>.json` is the
canonical input now, not the per-world `archipelago.json`).
"""

from __future__ import annotations

import argparse
import collections
import copy
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

IGDB_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"

USER_AGENT = "MultiworldGG-Index-IGDB-Game-Details/1.0"

# Fields a single IGDB row needs to populate, matching what build_variants.py
# reads from output/igdb_game_details.json.
GAME_DETAILS_FIELDS = (
    "igdb_id",
    "cover_url",
    "artwork_url",
    "key_art_url",
    "game_name",
    "igdb_name",
    "age_rating",
    "rating",
    "player_perspectives",
    "genres",
    "themes",
    "platforms",
    "storyline",
    "keywords",
    "release_date",
)

# APWorlds whose game name implies adult content regardless of IGDB age rating.
# Originally inlined in tools/game_indexing/igdb.py; kept for parity until a
# better tagging mechanism exists.
AO_NAME_HINTS = ("sex", "hunie", "fuck")

# Default game details row for original / hint worlds (igdb_id == 0 or missing).
DEFAULT_ORIGINAL_WORLD_ENTRY = {
    "igdb_id": "",
    "cover_url": "",
    "artwork_url": "",
    "key_art_url": "",
    "game_name": "",  # filled in from the manifest's `game` field
    "igdb_name": "",
    "age_rating": "MW",
    "rating": [],
    "player_perspectives": [],
    "genres": ["Multiplayer"],
    "themes": [],
    "platforms": ["Archipelago"],
    "storyline": "",
    "keywords": ["hints", "archipelago", "multiworld"],
    "release_date": "",
}

# Keywords rarer than this are dropped: too thin to be useful search terms.
KEYWORD_MIN_COUNT = 5

# IGDB keywords describing storefronts, hardware re-releases or award trivia
# rather than the game itself. Culled regardless of how often they occur.
KEYWORD_BLOCKLIST = frozenset({
    "4 player co-op",
    "60 fps on consoles",
    "battery save",
    "boss fight",
    "cheat code",
    "collectibles",
    "color cartridges",
    "crowdfunding - kickstarter",
    "downloadable content",
    "e3 1997",
    "e3 2000",
    "e3 2001",
    "e3 2002",
    "e3 2003",
    "e3 2004",
    "e3 2005",
    "e3 2006",
    "e3 2008",
    "e3 2017",
    "fan translation - ancient greek",
    "fan translation - arabic",
    "fan translation - dutch",
    "fan translation - english",
    "fan translation - french",
    "fan translation - galician",
    "fan translation - german",
    "fan translation - greek",
    "fan translation - indonesian",
    "fan translation - irish",
    "fan translation - italian",
    "fan translation - korean",
    "fan translation - latin",
    "fan translation - norwegian",
    "fan translation - polish",
    "fan translation - portuguese",
    "fan translation - romanian",
    "fan translation - spanish",
    "fan translation - swedish",
    "fan translation - tagalog",
    "female antagonist",
    "fictional currencies",
    "greatest hits",
    "high score",
    "humble bundle",
    "in-game anti-piracy effects",
    "interquel",
    "leaderboard",
    "level selection",
    "licensed game",
    "male protagonist",
    "media type - cartridge",
    "media type - digital file",
    "mod support",
    "multi-phase boss",
    "new game plus",
    "nintendo 3ds",
    "nintendo 3ds virtual console",
    "nintendo 64",
    "nintendo 64 exclusive",
    "nintendo 64 virtual console",
    "nintendo gateway system",
    "nintendo switch",
    "nintendo switch online",
    "nintendo switch online - expansion pack",
    "non-player character",
    "online",
    "open-source",
    "optional boss",
    "original soundtrack release",
    "pax prime 2014",
    "pax west 2017",
    "pixel graphics",
    "platform exclusive",
    "played for charity",
    "player's choice",
    "playstation network",
    "playstation plus",
    "playstation trophies",
    "playstation tv support",
    "post-credits plot twist",
    "pre-release public testing",
    "prequel",
    "promo vhs",
    "protagonist's name in the title",
    "single-player only",
    "split-screen multiplayer",
    "steam",
    "steam achievements",
    "steam cloud",
    "steam families",
    "steam trading cards",
    "steam workshop",
    "super game boy enhancement",
    "the game awards - best independent game - winner",
    "the game awards - best score or music - nominee",
    "the game awards - game of the year - nominee",
    "the game awards - nominee",
    "the game awards 2016",
    "the game awards 2017",
    "transforming boss",
    "treasure chest",
    "trilogy",
    "unlockable difficulty level",
    "unlockables",
    "unofficial",
    "virtual console",
    "vore",
    "wii u virtual console",
    "wii virtual console",
    "xbox controller support for pc",
    "young protagonist",
})


def _http_post(url: str, *, data: bytes, headers: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def get_access_token(client_id: str, client_secret: str) -> str:
    """Hit Twitch OAuth for a fresh IGDB access token. No on-disk cache (CI-friendly)."""
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }).encode("utf-8")
    payload = _http_post(
        IGDB_TOKEN_URL,
        data=params,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    token = payload.get("access_token")
    if not token:
        raise SystemExit(f"IGDB OAuth response missing access_token: {payload}")
    return token


def _igdb_query(client_id: str, token: str, body: str) -> list:
    """POST an APICalypse query to /v4/games. Returns the parsed JSON list."""
    req = urllib.request.Request(
        IGDB_GAMES_URL,
        data=body.encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
        if not text:
            return []
        result = json.loads(text)
        return result if isinstance(result, list) else []


def fetch_igdb_details(client_id: str, token: str, igdb_id: int) -> dict:
    """Fetch the canonical detail blob for a single IGDB game id.

    Returns the same shape as the original `tools/game_indexing/igdb.py`:
    igdb_name, cover_url, artwork_url, key_art_url, age_rating, rating,
    themes, player_perspectives, genres, platforms, storyline, release_date,
    keywords. Empty dict if IGDB returns no row.
    """
    body = (
        "fields name, cover.url, artworks.artwork_type, artworks.url, "
        "age_ratings.organization.name, age_ratings.rating_category.rating, "
        "age_ratings.rating_content_descriptions.description, "
        "first_release_date, player_perspectives.name, genres.name, "
        "themes.name, keywords.name, platforms.name, storyline; "
        f"where id = {int(igdb_id)};"
    )
    rows = _igdb_query(client_id, token, body)
    if not rows:
        return {}
    g = rows[0]

    # Age rating: prefer PEGI, fall back to ESRB. Mirrors the original script.
    age_rating = "NR"
    content_descriptions: list[str] = []
    for r in g.get("age_ratings", []):
        org = (r.get("organization") or {}).get("name")
        cat = r.get("rating_category") or {}
        if org == "PEGI" and "rating" in cat:
            age_rating = cat["rating"]
        if org == "ESRB":
            for d in r.get("rating_content_descriptions", []) or []:
                if "description" in d:
                    content_descriptions.append(d["description"])
            if age_rating == "NR" and "rating" in cat:
                age_rating = cat["rating"]

    artwork_url = ""
    key_art_url = ""
    for art in g.get("artworks", []):
        atype = art.get("artwork_type")
        url = art.get("url", "")
        if atype in (1, 5):
            artwork_url = (
                url.replace("t_thumb", "t_logo_med")
                   .replace("//", "https://")
                   .replace(".jpg", ".png")
            )
        elif atype == 2:
            key_art_url = (
                url.replace("t_thumb", "t_cover_big")
                   .replace("//", "https://")
                   .replace(".jpg", ".png")
            )

    cover_url = (
        (g.get("cover") or {}).get("url", "")
        .replace("//", "https://")
        .replace(".jpg", ".png")
    )

    return {
        "igdb_name": g.get("name", ""),
        "cover_url": cover_url,
        "artwork_url": artwork_url,
        "key_art_url": key_art_url,
        "age_rating": age_rating,
        "rating": content_descriptions,
        "themes": [t["name"] for t in g.get("themes", []) if "name" in t],
        "player_perspectives": [
            p["name"] for p in g.get("player_perspectives", []) if "name" in p
        ],
        "genres": [genre["name"] for genre in g.get("genres", []) if "name" in genre],
        "platforms": [p["name"] for p in g.get("platforms", []) if "name" in p],
        "storyline": g.get("storyline", ""),
        "release_date": g.get("first_release_date", ""),
        "keywords": [k["name"] for k in g.get("keywords", []) if "name" in k],
    }


def build_entry_for_apworld(
    apworld: str,
    manifest: dict,
    *,
    client_id: str,
    token: str,
) -> dict:
    """Return the game details row for one apworld, matching GAME_DETAILS_FIELDS."""
    game_name = manifest.get("game", "")
    igdb_id = manifest.get("igdb_id", 0)
    if not igdb_id:
        entry = dict(DEFAULT_ORIGINAL_WORLD_ENTRY)
        entry["game_name"] = game_name
        return entry

    details = fetch_igdb_details(client_id, token, int(igdb_id))
    if not details:
        # IGDB id was set but lookup failed (deleted? wrong id?). Emit a stub
        # so downstream variant builds still see a row, but mark it for review.
        entry = dict(DEFAULT_ORIGINAL_WORLD_ENTRY)
        entry["game_name"] = game_name
        entry["igdb_id"] = str(igdb_id)
        entry["age_rating"] = "NR"
        return entry

    age_rating = details.get("age_rating", "NR")
    name_lower = game_name.lower()
    if any(hint in name_lower for hint in AO_NAME_HINTS):
        age_rating = "AO"

    return {
        "igdb_id": str(igdb_id),
        "cover_url": details.get("cover_url", ""),
        "artwork_url": details.get("artwork_url", ""),
        "key_art_url": details.get("key_art_url", ""),
        "game_name": game_name,
        "igdb_name": details.get("igdb_name", ""),
        "age_rating": age_rating,
        "rating": details.get("rating", []),
        "player_perspectives": details.get("player_perspectives", []),
        "genres": details.get("genres", []),
        "themes": details.get("themes", []),
        "platforms": details.get("platforms", []),
        "storyline": details.get("storyline", ""),
        "keywords": details.get("keywords", []),
        "release_date": details.get("release_date", ""),
    }


def discover_apworlds(worlds_dir: Path) -> list[str]:
    return sorted(p.stem for p in worlds_dir.glob("*.json"))


def release_year(value: object) -> int | str:
    """Normalize IGDB's `first_release_date` (Unix seconds, UTC) to a four-digit year.

    Values already stored as a year pass through unchanged; anything missing or
    unparseable becomes `""`. UTC rather than local time so a New Year's Eve
    release does not land in a different year depending on the runner's zone.
    """
    if value in (None, "", []):
        return ""
    try:
        timestamp = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if 1000 <= timestamp <= 3000:
        return timestamp
    try:
        return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).year
    except (OSError, OverflowError, ValueError):
        return ""


def cull_keywords(game_details: dict) -> int:
    """Drop blocklisted and too-rare keywords across every entry. Returns the number removed.

    Frequencies are counted over the whole file, so an incremental run judges a
    freshly fetched world's keywords against the corpus rather than against itself.
    """
    counts: collections.Counter[str] = collections.Counter()
    for entry in game_details.values():
        keywords = entry.get("keywords")
        if isinstance(keywords, list):
            counts.update(kw for kw in keywords if kw)

    removed = 0
    for entry in game_details.values():
        keywords = entry.get("keywords")
        if not isinstance(keywords, list):
            continue
        kept = [
            kw
            for kw in keywords
            if kw and counts[kw] > KEYWORD_MIN_COUNT and kw not in KEYWORD_BLOCKLIST
        ]
        removed += len(keywords) - len(kept)
        entry["keywords"] = kept
    return removed


def prune_orphans(game_details: dict, worlds_dir: Path) -> list[str]:
    """Drop entries whose `worlds/<apworld>.json` is gone (renamed or removed worlds)."""
    orphans = sorted(set(game_details) - set(discover_apworlds(worlds_dir)))
    for apworld in orphans:
        del game_details[apworld]
    return orphans


def postprocess(game_details: dict, worlds_dir: Path) -> tuple[list[str], int]:
    """Apply the whole-file passes the per-world fetch cannot do on its own.

    Ported from the old pipeline's `convert_to_readable_outputs.py` and
    `remove_specific_keywords.py`, which ran after every full IGDB fetch.
    """
    orphans = prune_orphans(game_details, worlds_dir)
    for entry in game_details.values():
        entry["release_date"] = release_year(entry.get("release_date"))
        for key, value in entry.items():
            if value is None:
                entry[key] = ""
    return orphans, cull_keywords(game_details)


def load_manifest(worlds_dir: Path, apworld: str) -> Optional[dict]:
    path = worlds_dir / f"{apworld}.json"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_game_details(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_game_details(path: Path, data: dict) -> None:
    # newline pinned: the repo is LF, and the default would emit CRLF on Windows.
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(sorted(data.items())), f, indent=4, ensure_ascii=False)
        f.write("\n")


def game_details(
    apworlds: Iterable[str],
    *,
    worlds_dir: Path,
    game_details_path: Path,
    client_id: str,
    client_secret: str,
    sleep_between: float = 0.25,
    dry_run: bool = False,
) -> dict[str, str]:
    """Fetch game details for the given apworlds. Returns a `apworld -> status` mapping for the report."""
    original = load_game_details(game_details_path)
    updated = copy.deepcopy(original)
    statuses: dict[str, str] = {}
    fetched: list[str] = []

    token = get_access_token(client_id, client_secret) if apworlds else ""
    for apworld in apworlds:
        manifest = load_manifest(worlds_dir, apworld)
        if manifest is None:
            statuses[apworld] = "skipped:no-manifest"
            continue
        try:
            updated[apworld] = build_entry_for_apworld(
                apworld, manifest, client_id=client_id, token=token
            )
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            statuses[apworld] = f"failed:{exc}"
            continue
        fetched.append(apworld)
        # Be polite to IGDB.
        time.sleep(sleep_between)

    # Statuses are read off the post-processed result: the raw fetch still holds
    # epoch release dates and unculled keywords, so comparing it to the stored
    # file would mark every world as updated.
    orphans, _ = postprocess(updated, worlds_dir)
    for apworld in fetched:
        old_entry = original.get(apworld)
        if old_entry == updated[apworld]:
            statuses[apworld] = "unchanged"
        else:
            statuses[apworld] = "updated" if old_entry is not None else "added"
    for apworld in orphans:
        statuses[apworld] = "removed:no-manifest"

    if updated != original and not dry_run:
        write_game_details(game_details_path, updated)
    return statuses


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch game details for the given apworlds.")
    parser.add_argument(
        "--apworld", action="append", default=[], help="APWorld to fetch game details for. Repeatable."
    )
    parser.add_argument("--all", action="store_true", help="Fetch game details for every apworld under --worlds-dir")
    parser.add_argument(
        "--postprocess-only",
        action="store_true",
        help="Re-run the whole-file passes (release years, keyword culling, orphan pruning) "
             "over the existing file without contacting IGDB. Needs no credentials.",
    )
    parser.add_argument("--worlds-dir", type=Path, default=Path("worlds"))
    parser.add_argument(
        "--game-details-path", type=Path, default=Path("output/igdb_game_details.json")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.apworld and not args.all and not args.postprocess_only:
        print("nothing to do (no --apworld given and --all not set)", file=sys.stderr)
        return 0

    client_id = os.environ.get("IGDB_CLIENT_ID", "").strip()
    client_secret = os.environ.get("IGDB_CLIENT_SECRET", "").strip()
    if args.postprocess_only:
        apworlds: list[str] = []
    elif not client_id or not client_secret:
        print(
            "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET env vars must be set.",
            file=sys.stderr,
        )
        return 2
    elif args.all:
        apworlds = discover_apworlds(args.worlds_dir)
    else:
        apworlds = list(dict.fromkeys(args.apworld))

    statuses = game_details(
        apworlds,
        worlds_dir=args.worlds_dir,
        game_details_path=args.game_details_path,
        client_id=client_id,
        client_secret=client_secret,
        dry_run=args.dry_run,
    )

    n_updated = sum(1 for s in statuses.values() if s in ("updated", "added"))
    n_unchanged = sum(1 for s in statuses.values() if s == "unchanged")
    n_failed = sum(1 for s in statuses.values() if s.startswith("failed"))
    n_skipped = sum(1 for s in statuses.values() if s.startswith("skipped"))
    n_removed = sum(1 for s in statuses.values() if s.startswith("removed"))
    print(
        f"{'(dry-run) ' if args.dry_run else ''}"
        f"updated/added: {n_updated}, unchanged: {n_unchanged}, "
        f"failed: {n_failed}, skipped: {n_skipped}, removed: {n_removed}"
    )
    for apworld, status in sorted(statuses.items()):
        if status not in ("unchanged",):
            print(f"  {apworld}: {status}")

    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_cli())
