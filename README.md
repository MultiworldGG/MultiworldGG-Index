# MultiworldGG-Index

Canonical game-index manifest repository for [MultiworldGG](https://github.com/MultiworldGG/MultiworldGG).

This repo is the source of truth for which APWorlds exist, who wrote them, and
where to fetch them from. The MultiworldGG launcher and generator read it at
runtime via the `mwgg_igdb` package, which is built from this repo's `main`
branch on a daily schedule.

## Author how-to docs

**[MultiworldGG-Index docs site](https://lallaria.github.io/MultiworldGG-Index/)** — step-by-step guide for APWorld authors: setting up Oliver, cutting a release, and understanding what Karen checks.

Reading on GitHub? Start at **[docs/index.md](docs/index.md)**.

## Branch layout

| Branch | Purpose |
|---|---|
| `main` | Per-world manifests (`worlds/<apworld>.json`), schema, scripts, and workflows. Author PRs land here (opened by Oliver; reviewed by Karen). |
| `game_index_nr` | Orphan release branch — No Rating variant. Operator-facing; do not push manually. |
| `game_index_ao` | Orphan release branch — Adults Only variant. |
| `game_index_twelve` | Orphan release branch — 12+ variant. |
| `game_index_sixteen` | Orphan release branch — 16+ variant (canonical default). |

The four orphan branches are rebuilt from `main` by `.github/workflows/daily-release.yml`
and tagged `<variant>-YYYY-MM-DD` on each release. They are operator-facing; authors
only need to get their manifest onto `main`.

## Per-world manifest schema

Source of truth: [`schema/world_manifest.schema.json`](schema/world_manifest.schema.json)
(JSON Schema Draft 2020-12).

Required fields: `game`, `world_version`, `module_location`.

## License

GPL-3.0. See [LICENSE](LICENSE).
