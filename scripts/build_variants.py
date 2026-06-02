"""Build the four variant `mwgg_igdb` packages for MultiworldGG-Index.

Faithful re-port of the old gui-changes pipeline
(`tools/game_indexing/igdb.py` + `tools/game_indexing/generate_game_index.py`),
adapted to the new Index-repo input layout:

- Per-world manifests at `worlds/<apworld>.json` (was: `worlds/<apworld>/archipelago.json`)
- Staged IGDB metadata at `output/igdb_game_details.json` (was: a fresh IGDB fetch)

Produces `dist/<variant>/{mwgg_igdb.py, pyproject.toml, README.md}` per variant.
The daily-release workflow force-pushes each `dist/<variant>/` directory to the
corresponding orphan branch (`game_index_<variant>`).

All four variants publish a package named `mwgg_igdb` regardless of which orphan
branch is the source. Variant choice is reflected in the orphan-branch name and
the package version, not in the import path — so consumer code keeps working
with `from mwgg_igdb import GameIndex` no matter which variant is installed.

Run from the Index repo root:

    python scripts/build_variants.py [--worlds-dir worlds] \\
                                     [--game-details output/igdb_game_details.json] \\
                                     [--template scripts/game_index_template.py] \\
                                     [--out-dir dist] \\
                                     [--version YYYY.MM.DD] \\
                                     [--variant nr|ao|twelve|sixteen]

If `--version` is omitted, today's UTC date is used.
If `--variant` is omitted, all four are built.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path
from re import match
from typing import Any, Iterable, Optional


# Age-rating filter sets, mirroring the old gui-changes pipeline.
filter_nr = ["MW", "3", "7", "12", "16", "18", "E", "T", "M", "NR"]
filter_ao = ["MW", "3", "7", "12", "16", "18", "E", "T", "M", "NR", "AO"]
filter_16 = ["MW", "3", "7", "12", "16", "E", "T"]
filter_12 = ["MW", "3", "7", "12", "E"]

VARIANT_FILTERS: dict[str, list] = {
    "nr": filter_nr,
    "ao": filter_ao,
    "sixteen": filter_16,
    "twelve": filter_12,
}

VARIANT_DESCRIPTIONS: dict[str, str] = {
    "nr": "IGDB database indexed for MultiworldGG use (No Adults Only)",
    "ao": "IGDB database indexed for MultiworldGG use (Adults Only included)",
    "sixteen": "IGDB database indexed for MultiworldGG use (16+ rated)",
    "twelve": "IGDB database indexed for MultiworldGG use (12+ rated)",
}

POPULAR_APWORLDS = {"alttp", "sc2", "oot", "kh2", "hk", "sm64ex"}

SEARCHABLE_FIELDS = {
    "igdb_name",
    "platforms",
    "genres",
    "themes",
    "keywords",
    "player_perspectives",
}


def clean_value(value: Any) -> str:
    """Clean a value for indexing: None -> '', else lowercased string."""
    if value is None:
        return ""
    return str(value).lower()


def load_world_manifests(worlds_dir: Path) -> dict[str, dict]:
    """Read every `worlds/*.json` and return `apworld -> manifest`. The
    filename stem is the apworld key; the parsed JSON is the manifest."""
    out: dict[str, dict] = {}
    for path in sorted(worlds_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            out[path.stem] = json.load(f)
    return out


def load_game_details(path: Path) -> dict[str, dict]:
    """Read the staged IGDB game details file. Returns `apworld -> metadata`."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assemble_games_data(
    manifests: dict[str, dict],
    game_details: dict[str, dict],
) -> dict[str, dict]:
    """Merge per-world manifests with staged IGDB metadata into the GAMES_DATA
    shape. Mirrors the entry shape produced by the old
    `igdb.py:generate_game_details_json`, with per-field defaulting so None
    values from IGDB never reach the renderer."""
    result: dict[str, dict] = {}
    for apworld, manifest in manifests.items():
        igdb_details = game_details.get(apworld, {})
        igdb_id = manifest.get("igdb_id") or igdb_details.get("igdb_id", "")
        game_name = manifest.get("game") or igdb_details.get("game_name") or apworld

        if "sex" in game_name.lower() or "hunie" in game_name.lower():
            age_rating = "AO"
        else:
            age_rating = igdb_details.get("age_rating") or "NR"

        has_igdb = bool(igdb_id) and str(igdb_id) != "0"
        if has_igdb:
            entry = {
                "igdb_id": str(igdb_id),
                "cover_url": igdb_details.get("cover_url") or "",
                "artwork_url": igdb_details.get("artwork_url") or "",
                "key_art_url": igdb_details.get("key_art_url") or "",
                "game_name": game_name,
                "igdb_name": igdb_details.get("igdb_name") or "",
                "age_rating": age_rating,
                "rating": igdb_details.get("rating") or [],
                "player_perspectives": igdb_details.get("player_perspectives") or [],
                "genres": igdb_details.get("genres") or [],
                "themes": igdb_details.get("themes") or [],
                "platforms": igdb_details.get("platforms") or [],
                "storyline": igdb_details.get("storyline") or "",
                "keywords": igdb_details.get("keywords") or [],
                "release_date": igdb_details.get("release_date") or "",
                "entry_point_module": f"worlds.{apworld}",
            }
        else:
            entry = {
                "igdb_id": "",
                "cover_url": "",
                "artwork_url": "",
                "key_art_url": "",
                "game_name": game_name,
                "igdb_name": "",
                "age_rating": "MW",
                "rating": [],
                "player_perspectives": [],
                "genres": ["Multiplayer"],
                "themes": [],
                "platforms": ["Archipelago"],
                "storyline": "",
                "keywords": ["hints", "archipelago", "multiworld"],
                "release_date": "2025",
                "entry_point_module": f"worlds.{apworld}",
            }
        if "module_location" in manifest:
            entry["module_location"] = manifest["module_location"]
        result[apworld] = entry
    return result


def clean_game_data(games_data: dict, rating_filter: list) -> dict:
    """Filter games by age rating. Mirrors the old pipeline minus the
    unconditional `age_filter = filter_nr` override — each variant now actually
    gets its declared filter."""
    return {
        world: data
        for world, data in games_data.items()
        if data.get("age_rating", "NR") in rating_filter
    }


def _add_to_index(index: dict[str, set[str]], term: str, world_name: str) -> None:
    term = clean_value(term)
    if term:
        if term not in index:
            index[term] = set()
        index[term].add(world_name)


def build_search_index(games_data: dict) -> dict[str, set[str]]:
    """Build the search index from game data. Mirrors the old pipeline:
    seeds a curated `popular` set, indexes the display name plus a fixed set of
    IGDB-derived fields, skips items containing `(`/`)`/`:`, and indexes both
    the full lowercased value and each whitespace-split word."""
    search_index: dict[str, set[str]] = {
        "popular": {s for s in POPULAR_APWORLDS if s in games_data}
    }
    for world_name, game_data in games_data.items():
        _add_to_index(search_index, game_data["game_name"], world_name)
        for field, value in game_data.items():
            if field not in SEARCHABLE_FIELDS:
                continue
            if isinstance(value, list):
                value_set = set(value) if value else set()
                for item in value_set:
                    if item and not match(r".*[():].*", item):
                        cleaned = clean_value(item)
                        _add_to_index(search_index, cleaned, world_name)
                        for word in cleaned.split():
                            _add_to_index(search_index, word, world_name)
            elif isinstance(value, (str, int, float, bool)):
                if value:
                    value_str = clean_value(value)
                    _add_to_index(search_index, value_str, world_name)
                    for word in value_str.split():
                        _add_to_index(search_index, word, world_name)
    return search_index


def validate_generated_index(games_data: dict, search_index: dict[str, set[str]]) -> bool:
    """Warn-only validation: every game reachable via its display name, no
    orphan references in the search index."""
    ok = True
    for world_name in games_data:
        game_name = games_data[world_name]["game_name"]
        if game_name not in games_data:  # never; just defensive
            continue
        indexed = search_index.get(clean_value(game_name), set())
        if world_name not in indexed:
            print(f"Warning: Game name '{game_name}' not properly indexed")
            ok = False
    for term, games in search_index.items():
        for game in games:
            if game not in games_data:
                print(f"Warning: Invalid game reference '{game}' in term '{term}'")
                ok = False
    return ok


def render_template(
    template_path: Path,
    variant: str,
    games_data: dict[str, dict],
    game_names: dict[str, str],
    search_index: dict[str, set[str]],
) -> str:
    """Render the template using JSON-style formatting to match the old
    pipeline's pretty output. SEARCH_INDEX uses sets, which JSON does not
    represent, so we emit list literals via json.dumps and then convert `[`/`]`
    to `{`/`}` — safe here because search terms and apworld names never contain
    bracket characters."""
    template = template_path.read_text(encoding="utf-8")
    games_data_str = json.dumps(games_data, indent=4)
    game_names_str = json.dumps(game_names, indent=4)
    search_index_json = {k: sorted(v) for k, v in search_index.items()}
    search_index_str = (
        json.dumps(search_index_json, indent=4).replace("[", "{").replace("]", "}")
    )
    return (
        template
        .replace("VARIANT_PLACEHOLDER", variant)
        .replace("GAMES_DATA_PLACEHOLDER", games_data_str)
        .replace("GAMES_NAMES_PLACEHOLDER", game_names_str)
        .replace("SEARCH_INDEX_PLACEHOLDER", search_index_str)
    )


def write_pyproject(out_dir: Path, version: str, description: str) -> None:
    pyproject = f'''[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "mwgg_igdb"
version = "{version}"
description = "{description}"
authors = [{{name = "MultiworldGG"}}]
requires-python = ">=3.8"
classifiers = [
    "Private :: Do Not Upload"
]

[tool.setuptools]
py-modules = ["mwgg_igdb"]
'''
    (out_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")


def write_readme(out_dir: Path, variant: str, version: str) -> None:
    readme = f'''# mwgg_igdb — {variant} variant ({version})

Published `{variant}` variant of the MultiworldGG game index. Force-pushed by
the daily-release workflow in the Index repo and tagged on each push as
`{variant}-YYYY-MM-DD`.

Install with:

```
pip install git+ssh://git@github.com/MultiworldGG/MultiworldGG-Index@game_index_{variant}
```

The package exports a `_GameIndexClass` singleton at `mwgg_igdb.GameIndex`.
'''
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def build_one_variant(
    variant: str,
    *,
    games_data: dict[str, dict],
    template_path: Path,
    out_dir: Path,
    version: str,
) -> dict:
    rating_filter = VARIANT_FILTERS[variant]
    filtered = clean_game_data(games_data, rating_filter)
    search_index = build_search_index(filtered)
    game_names = {data["game_name"]: world for world, data in filtered.items()}

    if not validate_generated_index(filtered, search_index):
        print(f"Warning: index validation failed for variant '{variant}', continuing")

    rendered = render_template(template_path, variant, filtered, game_names, search_index)

    variant_dir = out_dir / variant
    if variant_dir.exists():
        shutil.rmtree(variant_dir)
    variant_dir.mkdir(parents=True)

    (variant_dir / "mwgg_igdb.py").write_text(rendered, encoding="utf-8")
    write_pyproject(variant_dir, version, VARIANT_DESCRIPTIONS[variant])
    write_readme(variant_dir, variant, version)

    return {
        "variant": variant,
        "games_count": len(filtered),
        "search_terms": len(search_index),
        "out_dir": str(variant_dir),
    }


def build_all(
    *,
    worlds_dir: Path,
    game_details_path: Path,
    template_path: Path,
    out_dir: Path,
    version: str,
    variants: Optional[Iterable[str]] = None,
) -> list:
    manifests = load_world_manifests(worlds_dir)
    game_details = load_game_details(game_details_path)
    games_data = assemble_games_data(manifests, game_details)

    selected = list(variants) if variants else list(VARIANT_FILTERS.keys())
    out: list = []
    for variant in selected:
        if variant not in VARIANT_FILTERS:
            raise SystemExit(f"unknown variant: {variant}")
        result = build_one_variant(
            variant,
            games_data=games_data,
            template_path=template_path,
            out_dir=out_dir,
            version=version,
        )
        out.append(result)
    return out


def _today_version() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y.%m.%d")


def _cli(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build all four variant orphan-branch packages from worlds/*.json."
    )
    parser.add_argument("--worlds-dir", type=Path, default=Path("worlds"))
    parser.add_argument("--game-details", type=Path, default=Path("output/igdb_game_details.json"))
    parser.add_argument("--template", type=Path, default=Path("scripts/game_index_template.py"))
    parser.add_argument("--out-dir", type=Path, default=Path("dist"))
    parser.add_argument("--version", default=None, help="Package version, default: today's UTC date YYYY.MM.DD")
    parser.add_argument("--variant", default=None, help="Build only this variant (default: all four)")
    args = parser.parse_args(argv)

    version = args.version or _today_version()
    variants = [args.variant] if args.variant else None
    results = build_all(
        worlds_dir=args.worlds_dir,
        game_details_path=args.game_details,
        template_path=args.template,
        out_dir=args.out_dir,
        version=version,
        variants=variants,
    )
    for r in results:
        print(f"{r['variant']:>8s}: {r['games_count']:4d} games, {r['search_terms']:5d} search terms -> {r['out_dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
