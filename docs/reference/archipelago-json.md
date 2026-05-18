# `archipelago.json` schema reference

Every APWorld must have `worlds/<apworld>/archipelago.json`. This file is the
single source of truth for the world's identity. The build workflow reads it,
the Index manifest records it, and MultiworldGG reads it at load time.

The schema below covers the fields as they appear in your **source-repo**
`archipelago.json` (not the Index manifest, which adds `module_location` and
other Index-controlled fields — see [Index-controlled fields](#index-controlled-fields) below).

Full schema source: [`schema/world_manifest.schema.json`](https://github.com/MultiworldGG/MultiworldGG-Index/blob/main/schema/world_manifest.schema.json)

---

## Required fields

### `game`

| | |
|---|---|
| Type | string |
| Required | yes |
| Written by | Author |
| Example | `"My Cool Game"` |

The display name of the game shown to players. This is the lookup key the
MultiworldGG launcher and generator use. It must match the `game` attribute on
your `World` class.

The `game` value (lowercased, spaces replaced with underscores) becomes the
apworld slug — the filename stem of your `worlds/<apworld>.json` manifest and
the name of your wheel package (`worlds.<apworld>`).

### `world_version`

| | |
|---|---|
| Type | string, semver shape |
| Required | yes |
| Written by | Author |
| Example | `"1.2.0"` |

Version of the world implementation. Must follow `major.minor.patch` format
(e.g. `"1.0.0"`). Used as the Python wheel version. Must match the version
portion of your release tag (e.g. tag `myclgm-1.2.0` requires
`world_version: "1.2.0"`).

The version comparison rule: if both an `.apworld` file and a wheel are
available for the same world, the higher `world_version` wins. Tiebreaker:
the installed wheel takes precedence over the `.apworld`.

### `module_location`

| | |
|---|---|
| Type | string (URI) |
| Required | yes in the Index manifest |
| Written by | **Oliver** (never the author directly) |
| Example | `"https://github.com/you/your-repo/releases/download/myclgm-1.2.0/worlds.myclgm-1.2.0-py3-none-any.whl#sha256=<hex>"` |

The pip-installable URL for the world's wheel, including a `#sha256=<hex>`
hash fragment that pip verifies at install time.

**Do not put this field in your source-repo `archipelago.json`.** Oliver writes
it into the Index manifest when opening the PR. If you hand-write it, Oliver
will overwrite it.

---

## Optional fields

### `minimum_ap_version`

| | |
|---|---|
| Type | string, semver shape |
| Required | no |
| Written by | Author |
| Example | `"0.6.4"` |

Oldest MultiworldGG version your world supports. MultiworldGG will refuse to
load your world below this version.

### `maximum_ap_version`

| | |
|---|---|
| Type | string, semver shape |
| Required | no |
| Written by | Author |
| Example | `"0.6.99"` |

Newest MultiworldGG version your world supports. Rarely needed; omit unless
you know your world breaks on a specific future version.

### `authors`

| | |
|---|---|
| Type | array of strings |
| Required | no |
| Written by | Author |
| Example | `["TreZc0", "DelilahIsDidi"]` |

List of author names shown in user-facing places (launcher, web host, package
metadata). At least one author is strongly recommended.

### `compatible_version` and `version`

| | |
|---|---|
| Type | integer |
| Required | only inside `.apworld` zip |
| Written by | **Launcher's "Build APWorlds" component** |

APContainer packaging version fields. Written automatically by
`Launcher.py "Build APWorlds"` when packaging a `.apworld` zip. Do not
write these yourself in your source `archipelago.json`.

### `repo_url`

| | |
|---|---|
| Type | string (URI) |
| Required | no |
| Written by | Author or Oliver |
| Example | `"https://github.com/you/your-repo"` |

URL to the world's source repository. Shown in the launcher. Karen checks
that this URL responds.

Some tooling also accepts `github` as a deprecated alias for this field;
new manifests should use `repo_url`. See [silasary/apworlds — `MANIFEST_EXTENSIONS.md`](https://github.com/silasary/apworlds/blob/main/MANIFEST_EXTENSIONS.md).

### `license`

| | |
|---|---|
| Type | string |
| Required | no |
| Written by | Author |
| Example | `"MIT"` |

Distribution license for the world. Either a recognized license identifier
(e.g. `"MIT"`, `"GPL-3.0"`) or a URL pointing to the license text. Documented
in [silasary/apworlds — `MANIFEST_EXTENSIONS.md`](https://github.com/silasary/apworlds/blob/main/MANIFEST_EXTENSIONS.md).

### `tracker`

| | |
|---|---|
| Type | string (URI) |
| Required | no |
| Written by | Author |
| Example | `"https://github.com/you/your-tracker"` |

URL to a tracker for this game, if one exists. Karen checks that this URL
responds.

### `igdb_id`

| | |
|---|---|
| Type | integer |
| Required | no |
| Written by | Author or via Index PR |

IGDB game ID. Added by the Index's IGDB-lookup workflow after merge if it's not
there already.

### `flags`

| | |
|---|---|
| Type | array of strings |
| Required | no |
| Written by | Author |
| Example | `["in_client", "tracker_included"]` |

Free-form capability flags. Unknown values are ignored by consumers. Well-known
values:

- `in_client` — world ships an in-game client component. Used by the Inno
  installer to decide which worlds appear in the per-world component list.
- `tracker_included` — world ships an in-tree tracker.
- `after_dark` — content rated 18+ or unrated. User-hideable in the
  updater.
- `prerelease` — beta version. Opt-in only for users.
- `unready` — early development. Hidden in the updater unless already
  installed.

Planned values (not yet acted on by any consumer):

- `supports_deathlink`
- `supports_energylink`
- `supports_ringlink`

The `after_dark` / `prerelease` / `unready` / `supports_*` values are
documented in [silasary/apworlds — `MANIFEST_EXTENSIONS.md`](https://github.com/silasary/apworlds/blob/main/MANIFEST_EXTENSIONS.md).

### `changelog`

| | |
|---|---|
| Type | string |
| Required | no |
| Written by | Author |

Human-readable changelog. Can be a markdown string. Shown in user-facing places
that display release notes.

---

## Index-controlled field

The following field appears in the Index manifest (`worlds/<apworld>.json` on
`main`) but can't be set by the author in their source `archipelago.json`:

| Field | Who sets it | When |
|---|---|---|
| `module_location` | Oliver | When opening the Index PR |

If you put this field in your source `archipelago.json`, Oliver will
overwrite it - your `archipelago.json` is part of the SHA it stores!

---

## Inline comment convention

Any field whose name matches `^_comment(_|$)` (e.g. `"_comment"`,
`"_comment_2"`) is treated as a human-readable note and ignored by all
consumers. You can use these to document unusual field values in your manifest:

```json
{
    "game": "My Cool Game",
    "world_version": "1.0.0",
    "_comment": "minimum_ap_version omitted intentionally — this world works on all versions"
}
```
