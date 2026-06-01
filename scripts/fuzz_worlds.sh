#!/usr/bin/env bash
# Fuzz proposed worlds from PR manifests.
# Reads changed manifest paths from karen-targets.txt, downloads wheels,
# clones MultiworldGG core, and runs Eijebong's fuzzer against each world.
#
# Required env vars:
#   MWGG_CORE_REPO, MWGG_CORE_REF, MWGG_IGDB_REPO, MWGG_IGDB_VARIANT_REF
#   FUZZER_REPO, FUZZER_REF, GITHUB_WORKSPACE, GITHUB_EVENT_PATH
#
# Outputs (GITHUB_OUTPUT style):
#   fuzz_overall (pass|warn|fail), fuzz_summary
# Side effects:
#   Every world's full fuzz output (report.json + failure/timeout dumps) is
#   copied to ${GITHUB_WORKSPACE}/fuzz_output_all/<apworld>/ for the uploaded
#   artifact, so the codeowner can inspect any verdict.

set -euo pipefail

fuzz_runs="${FUZZ_RUNS:-50}"
fuzz_yamls="${FUZZ_YAMLS:-1-10}"
fuzz_threads="${FUZZ_THREADS:-10}"
fuzz_timeout="${FUZZ_TIMEOUT:-30}"

# Per-PR overrides via labels.
while IFS= read -r label; do
  case "$label" in
    karen/fuzz-runs:*)    fuzz_runs="${label#karen/fuzz-runs:}" ;;
    karen/fuzz-timeout:*) fuzz_timeout="${label#karen/fuzz-timeout:}" ;;
  esac
done < <(jq -r '.pull_request.labels[].name' < "$GITHUB_EVENT_PATH")
echo "Fuzz config: runs=${fuzz_runs} per-gen-timeout=${fuzz_timeout}s"

fuzz_output_dir="${GITHUB_WORKSPACE}/fuzz_output_all"
mkdir -p "${fuzz_output_dir}"
fuzz_overall=pass
fuzz_summary=""

# Classify one world's report.json into pass/warn/fail. Emits:
#   "<status> <success> <failure> <timeout> <ignored> <rom> <real> <total>"
# Buckets (per the codeowner's rules):
#   - timeout or non-ROM failure -> counts as a real failure (red past 50%)
#   - ROM/output failure (missing base-rom signature) -> warn, never red: it's
#     an environment limit (no ROM on the runner), not a world bug
#   - ignored (OptionError) -> warn only when nothing generated; a no-op
#   - clean generation -> pass
# `romlike` matches the FileNotFoundError signature ("no such file...") plus a
# few common console-ROM extensions; extend the alternation as new worlds land.
CLASSIFY_JQ='
  def romlike:
    test("no such file or directory|\\brom\\b|\\.(gba|gbc|gb|sfc|smc|z64|n64|nes|md|gen|iso|bin|pce|nds)([^a-z0-9]|$)"; "i");
  (.stats.success // 0) as $succ
  | (.stats.failure // 0) as $fail
  | (.stats.timeout // 0) as $to
  | (.stats.ignored // 0) as $ign
  | (.stats.total   // 0) as $total
  | [ (.errors // {}) | .[] | to_entries[] | select(.key | test("TimeoutError") | not) ] as $fk
  | ( [ $fk[] | select(.key | romlike)       | (.value | length) ] | add // 0 ) as $rom
  | ( [ $fk[] | select(.key | (romlike|not)) | (.value | length) ] | add // 0 ) as $real
  | ( $to + $real ) as $bad
  | ( if   ($total > 0) and (($bad / $total) > 0.5)                     then "fail"
      elif ($succ > 0) and ($to == 0) and ($real == 0) and ($rom == 0) then "pass"
      else "warn" end ) as $status
  | "\($status) \($succ) \($fail) \($to) \($ign) \($rom) \($real) \($total)"
'

# Read targets on FD 3, not stdin: inner commands (git clone, python fuzz.py,
# uv, ...) inherit stdin and any one that reads it would swallow the rest of the
# list, silently ending the loop after the first world.
while IFS= read -r manifest_path <&3; do
  [ -z "$manifest_path" ] && continue
  apworld="$(basename "$manifest_path" .json)"
  # Don't let a malformed/unreadable manifest abort the whole batch under set -e;
  # an empty module_location falls through to the skip below.
  module_location="$(jq -r '.module_location // ""' "${GITHUB_WORKSPACE}/${manifest_path}" 2>/dev/null || true)"

  # Strip fragment (sha256=...) for download.
  wheel_url="${module_location%%#*}"

  if ! echo "$wheel_url" | grep -qE '^https://.*\.whl(\?|$)'; then
    echo "::notice::Skipping fuzz for ${apworld}: module_location is not an https:// .whl URL (got: ${module_location:0:60}...)"
    fuzz_summary+="- ${apworld}: wheel lost in space (unsupported module_location)\n"
    continue
  fi

  echo "::group::Fuzz ${apworld}"
  workdir="$(mktemp -d)"
  world_exit=0
  (
    cd "$workdir"

    # Download the wheel from the manifest's module_location.
    echo "Downloading wheel: ${wheel_url}"
    curl -sSfLO "${wheel_url}"
    wheel_file="$(ls -1 *.whl | head -n1)"

    # Clone MultiworldGG core.
    git clone --depth 1 --branch "${MWGG_CORE_REF}" "https://github.com/${MWGG_CORE_REPO}.git" core
    cd core

    python -m pip install uv
    uv venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    uv pip install -r requirements.txt
    uv pip install "../${wheel_file}"

    # Drop fuzz.py from Eijebong/Archipelago-fuzzer at the core repo root.
    curl -sSfL \
      "https://raw.githubusercontent.com/${FUZZER_REPO}/${FUZZER_REF}/fuzz.py" \
      -o fuzz.py

    # Inject fuzz_bootstrap.py immediately BEFORE `from worlds import ...` so the
    # mwgg_igdb shim + SKIP_ALL_INSTALLS=1 are in place before worlds.* import.
    # fuzz.py comes from upstream main (a moving target), so anchor on the import
    # line instead of a hardcoded number. `sed Nr` inserts AFTER line N, so use
    # (worlds_line - 1) to land just before it. Absolute path because cwd here is
    # "$workdir/core", not the Index checkout; GNU sed silently no-ops on a
    # missing read-file, so a bad path would leave fuzz.py un-bootstrapped.
    bootstrap_path="${GITHUB_WORKSPACE}/scripts/fuzz_bootstrap.py"
    if [ ! -f "${bootstrap_path}" ]; then
      echo "::error::fuzz_bootstrap.py not found at ${bootstrap_path}"
      exit 1
    fi
    worlds_line="$(grep -n '^from worlds import' fuzz.py | head -n1 | cut -d: -f1)"
    if [ -z "${worlds_line}" ]; then
      echo "::error::could not find 'from worlds import' in fuzz.py to anchor bootstrap"
      exit 1
    fi
    sed -i "$((worlds_line - 1))r ${bootstrap_path}" fuzz.py

    set +e
    timeout 15m python fuzz.py -r "${fuzz_runs}" -t "${fuzz_timeout}" -g "${apworld}" -j "${fuzz_threads}" -n "${fuzz_yamls}"
    fuzz_exit=$?
    set -e

    # Preserve the whole per-world output (report.json + failure/timeout dumps)
    # for the uploaded artifact, whatever the verdict, before $workdir is
    # reclaimed. Classification happens outside the subshell against this copy.
    if [ -d fuzz_output ]; then
      cp -r fuzz_output "${fuzz_output_dir}/${apworld}"
    fi

    # No report at all = fuzz.py crashed or was killed by the 15m wall: a hard
    # fail, surfaced via world_exit below.
    if [ ! -f fuzz_output/report.json ]; then
      echo "::error::No report.json for ${apworld} (fuzz.py exit=${fuzz_exit})"
      exit 1
    fi
  ) || world_exit=$?
  echo "::endgroup::"

  # Classify from the report we copied into $fuzz_output_dir (it survives the
  # $workdir removal below). A non-zero subshell or a missing report means
  # fuzz.py crashed / hit the 15m wall -> hard fail.
  report_json="${fuzz_output_dir}/${apworld}/report.json"
  if [ "${world_exit}" -ne 0 ] || [ ! -f "${report_json}" ]; then
    status=fail
    detail="crashed or produced no report (exit ${world_exit})"
  else
    classified="$(jq -r "${CLASSIFY_JQ}" "${report_json}" 2>/dev/null || true)"
    read -r status s_succ s_fail s_to s_ign s_rom s_real s_total <<< "${classified}"
    if [ -z "${status}" ]; then
      status=fail
      detail="unparseable report.json"
    else
      detail="success=${s_succ} timeout=${s_to} fail=${s_real} rom/output=${s_rom} ignored=${s_ign} / ${s_total}"
    fi
  fi

  case "${status}" in
    fail)
      # Sticky: once any world is red, the overall result stays red.
      fuzz_overall=fail
      fuzz_summary+="- ${apworld}: ❌ ${detail} (see fuzz_output_all/${apworld}/)\n"
      ;;
    warn)
      # Yellow is a no-op, not a gate: only lift from pass, never mask a fail.
      [ "${fuzz_overall}" = "pass" ] && fuzz_overall=warn
      fuzz_summary+="- ${apworld}: ⚠️ no clean generation — ${detail} (see fuzz_output_all/${apworld}/)\n"
      ;;
    *)
      fuzz_summary+="- ${apworld}: ✅ fuzzed clean (${s_succ}/${s_total} generated)\n"
      ;;
  esac

  # Reclaim disk before the next world: each iteration leaves a full core clone
  # + venv (hundreds of MB); a many-world PR would exhaust the runner. The
  # report + dumps were already copied to $fuzz_output_dir, outside $workdir.
  rm -rf "${workdir}"
done 3< karen-targets.txt

# Output for GitHub Actions
echo "fuzz_overall=${fuzz_overall}" >> "$GITHUB_OUTPUT"
{
  echo "fuzz_summary<<EOF"
  printf '%b' "${fuzz_summary}"
  echo "EOF"
} >> "$GITHUB_OUTPUT"
