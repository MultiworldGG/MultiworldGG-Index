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
# Side effects:
#   On any per-world fuzz failure (>50% fail rate or crash),
#   ${GITHUB_WORKSPACE}/fuzz_output_all/<apworld>-report.json is preserved
#   so the codeowner can inspect it.

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

while IFS= read -r manifest_path; do
  [ -z "$manifest_path" ] && continue
  apworld="$(basename "$manifest_path" .json)"
  module_location="$(jq -r '.module_location // ""' "${GITHUB_WORKSPACE}/${manifest_path}")"

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

    # insert fuzz_bootstrap.py so it works on mwgg at line 14 in fuzz.py.
    # Use absolute path because cwd here is "$workdir/core", not the Index
    # checkout. GNU sed silently no-ops on a missing read-file, so a bare
    # relative path would leave fuzz.py un-bootstrapped and crash later with
    # "mwgg_igdb not found".
    bootstrap_path="${GITHUB_WORKSPACE}/scripts/fuzz_bootstrap.py"
    if [ ! -f "${bootstrap_path}" ]; then
      echo "::error::fuzz_bootstrap.py not found at ${bootstrap_path}"
      exit 1
    fi
    sed -i "14r ${bootstrap_path}" fuzz.py

    set +e
    timeout 15m python fuzz.py -r "${fuzz_runs}" -t "${fuzz_timeout}" -g "${apworld}" -j "${fuzz_threads}" -n "${fuzz_yamls}"
    fuzz_exit=$?
    set -e

    # Each fuzz invocation is `-g <one apworld>`, so report.json's `stats`
    # block is already scoped to this one world — the threshold check below
    # is per-world, not group-wide.
    if [ ! -f fuzz_output/report.json ]; then
      echo "::error::No report.json for ${apworld} (fuzz.py exit=${fuzz_exit})"
      exit 1
    fi

    fail_pct=$(jq -r '.stats | ((.failure + .timeout) / .total * 100)' fuzz_output/report.json)
    echo "${apworld}: failure rate = ${fail_pct}%"

    # bash arithmetic can't handle floats — let jq do the comparison.
    over_threshold=$(jq -r '.stats | ((.failure + .timeout) / .total) > 0.5' fuzz_output/report.json)
    if [ "${over_threshold}" = "true" ]; then
      cp fuzz_output/report.json "${fuzz_output_dir}/${apworld}-report.json"
      exit 1
    fi
  ) || world_exit=$?
  echo "::endgroup::"
  fuzz_rate=$(jq -r '.stats | ((.failure + .timeout) / .total)' fuzz_output/report.json)

  if [ "${world_exit}" -ne 0 ]; then
    fuzz_overall=fail
    fuzz_summary+="- ${apworld}: ❌ jagged, not fuzzy with ${fuzz_rate}% failure rate (see fuzz_output_all/${apworld}-report.json)\n"
  else
    fuzz_summary+="- ${apworld}: ✅ fuzzed with ${fuzz_rate}% failure rate\n"
    fuzz_overall=pass
  fi
done < karen-targets.txt

# Output for GitHub Actions
echo "fuzz_overall=${fuzz_overall}" >> "$GITHUB_OUTPUT"
{
  echo "fuzz_summary<<EOF"
  printf '%b' "${fuzz_summary}"
  echo "EOF"
} >> "$GITHUB_OUTPUT"
