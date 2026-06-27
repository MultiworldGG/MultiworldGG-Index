"""IGDB game details for the MultiworldGG-Index repo.

Reads `worlds/<apworld>.json` for one or more apworlds, queries IGDB for the matching
game's metadata, and updates `output/igdb_game_details.json` in place. Existing
entries for unaffected apworlds are preserved.

Triggered by `.github/workflows/igdb-game-details.yml` on every push to `main` that
touches `worlds/*.json`. Can also be run locally:

    IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... \\
        python scripts/igdb_game_details.py --apworld oot --apworld alttp

    # Re-fetch game details for every world (slow, hits rate limits — use sparingly):
    IGDB_CLIENT_ID=... IGDB_CLIENT_SECRET=... \\
        python scripts/igdb_game_details.py --all

Adapted from the original `tools/game_indexing/igdb.py` in the MultiworldGG alpha client, with
file-based credential / token caching replaced by environment variables and
the manifest-walking removed (the Index repo's `worlds/<apworld>.json` is the
canonical input now, not the per-world `archipelago.json`).
"""

from __future__ import annotations

import argparse
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
AO_NAME_HINTS = ("sex", "hunie")

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
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
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
    token = get_access_token(client_id, client_secret)
    game_details = load_game_details(game_details_path)
    statuses: dict[str, str] = {}
    changed = False

    for apworld in apworlds:
        manifest = load_manifest(worlds_dir, apworld)
        if manifest is None:
            statuses[apworld] = "skipped:no-manifest"
            continue
        try:
            new_entry = build_entry_for_apworld(
                apworld, manifest, client_id=client_id, token=token
            )
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            statuses[apworld] = f"failed:{exc}"
            continue
        old_entry = game_details.get(apworld)
        if old_entry == new_entry:
            statuses[apworld] = "unchanged"
        else:
            game_details[apworld] = new_entry
            changed = True
            statuses[apworld] = "updated" if old_entry is not None else "added"
        # Be polite to IGDB.
        time.sleep(sleep_between)

    if changed and not dry_run:
        write_game_details(game_details_path, game_details)
    return statuses


def _cli(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch game details for the given apworlds.")
    parser.add_argument(
        "--apworld", action="append", default=[], help="APWorld to fetch game details for. Repeatable."
    )
    parser.add_argument("--all", action="store_true", help="Fetch game details for every apworld under --worlds-dir")
    parser.add_argument("--worlds-dir", type=Path, default=Path("worlds"))
    parser.add_argument(
        "--game-details-path", type=Path, default=Path("output/igdb_game_details.json")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.apworld and not args.all:
        print("nothing to do (no --apworld given and --all not set)", file=sys.stderr)
        return 0

    client_id = os.environ.get("IGDB_CLIENT_ID", "").strip()
    client_secret = os.environ.get("IGDB_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(
            "IGDB_CLIENT_ID and IGDB_CLIENT_SECRET env vars must be set.",
            file=sys.stderr,
        )
        return 2

    if args.all:
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
    print(
        f"{'(dry-run) ' if args.dry_run else ''}"
        f"updated/added: {n_updated}, unchanged: {n_unchanged}, "
        f"failed: {n_failed}, skipped: {n_skipped}"
    )
    for apworld, status in sorted(statuses.items()):
        if status not in ("unchanged",):
            print(f"  {apworld}: {status}")

    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_cli())
