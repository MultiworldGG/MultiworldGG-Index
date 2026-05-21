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
#   fuzz_overall, fuzz_summary

set -euo pipefail

fuzz_runs="${FUZZ_RUNS:-50}"
fuzz_timeout="${FUZZ_TIMEOUT:-10}"

# Per-PR overrides via labels.
while IFS= read -r label; do
  case "$label" in
    karen/fuzz-runs:*)    fuzz_runs="${label#karen/fuzz-runs:}" ;;
    karen/fuzz-timeout:*) fuzz_timeout="${label#karen/fuzz-timeout:}" ;;
  esac
done < <(jq -r '.pull_request.labels[].name' < "$GITHUB_EVENT_PATH")
echo "Fuzz config: runs=${fuzz_runs} per-gen-timeout=${fuzz_timeout}s"

mkdir -p fuzz_output_all
fuzz_overall=pass
fuzz_summary=""

while IFS= read -r manifest_path; do
  [ -z "$manifest_path" ] && continue
  apworld="$(basename "$manifest_path" .json)"
  module_location="$(jq -r '.module_location // ""' "${GITHUB_WORKSPACE}/${manifest_path}")"

  # Strip fragment (sha256=...) for download.
  wheel_url="${module_location%%#*}"

  if ! echo "$wheel_url" | grep -qE '^https://.*\.whl(\?|$)'; then
    echo "::notice::Skipping fuzz for ${apworld}: module_location is not an https:// .whl URL (got: ${module_location:0:60}...)"
    fuzz_summary+="- ${apworld}: skipped (unsupported module_location)\n"
    continue
  fi

  echo "::group::Fuzz ${apworld}"
  workdir="$(mktemp -d)"
  (
    cd "$workdir"

    # Download the wheel.
    wheel_file="${apworld}.whl"
    echo "Downloading wheel: ${wheel_url}"
    curl -sSfL -o "${wheel_file}" "${wheel_url}"

    # Clone MultiworldGG core.
    git clone --depth 1 --branch "${MWGG_CORE_REF}" "https://github.com/${MWGG_CORE_REPO}.git" core
    cd core

    # Ensure worlds/ directory exists and extract wheel contents into it.
    mkdir -p worlds
    echo "Extracting wheel to worlds/"
    # A wheel is a ZIP file; extract directly into worlds/.
    unzip -q "${workdir}/${wheel_file}" -d worlds/

    python -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m pip install --upgrade pip
    # MultiworldGG core install — best-effort. If the repo doesn't ship a
    # canonical extra, fall back to its requirements file.
    if [ -f setup.py ] || [ -f pyproject.toml ]; then
      python -m pip install -e . || python -m pip install -r requirements.txt
    else
      python -m pip install -r requirements.txt
    fi
    # Install the mwgg_igdb variant package. Generate.py imports
    # `from mwgg_igdb import GameIndex` at module load; if missing,
    # fuzz.py crashes before the fuzzer ever runs.
    python -m pip install "git+https://github.com/${MWGG_IGDB_REPO}@${MWGG_IGDB_VARIANT_REF}"

    # Drop fuzz.py from Eijebong/Archipelago-fuzzer at the core repo root.
    curl -sSfL \
      "https://raw.githubusercontent.com/${FUZZER_REPO}/${FUZZER_REF}/fuzz.py" \
      -o fuzz.py

    set +e
    timeout 15m python fuzz.py -r "${fuzz_runs}" -t "${fuzz_timeout}" -g "${apworld}" -j 2
    fuzz_exit=$?
    set -e

    # Capture artifacts regardless of outcome.
    if [ -d fuzz_output ]; then
      mkdir -p "$GITHUB_WORKSPACE/fuzz_output_all/${apworld}"
      cp -r fuzz_output/. "$GITHUB_WORKSPACE/fuzz_output_all/${apworld}/" 2>/dev/null || true
    fi

    exit ${fuzz_exit}
  )
  world_exit=$?
  echo "::endgroup::"

  if [ "${world_exit}" -ne 0 ]; then
    fuzz_overall=fail
    fuzz_summary+="- ${apworld}: ❌ fuzz failed (exit=${world_exit})\n"
  else
    fuzz_summary+="- ${apworld}: ✅ fuzz passed\n"
  fi
done < karen-targets.txt

# Output for GitHub Actions
echo "fuzz_overall=${fuzz_overall}" >> "$GITHUB_OUTPUT"
{
  echo "fuzz_summary<<EOF"
  printf '%b' "${fuzz_summary}"
  echo "EOF"
} >> "$GITHUB_OUTPUT"
