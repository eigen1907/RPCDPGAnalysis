#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MERGE_SCRIPT="${SCRIPT_DIR}/rpc-tnp-merge-hist.sh"
YEARS=(2022 2023 2024 2025 2026)

usage() {
    cat >&2 <<EOF
Usage: $0 [OPTIONS]

Options:
  --tight-match       Use tight-match input/output defaults
  --all-probe-pt      Use full-probe-pT histogram input/output defaults
  --bx-zero           Use BX == 0 numerator histogram input/output defaults
  --no-roll-blacklist Use no-roll-blacklist input/output defaults
  --no-blacklist      Alias for --no-roll-blacklist
  --no-run-blacklist  Use no-run-blacklist input/output defaults
  -h, --help          Show this help

Other options are passed through to rpc-tnp-merge-hist.sh.
EOF
}

parse_args() {
    TIGHT_MATCH=0
    PROBE_PT_GT15=1
    BX_ZERO=0
    NO_BLACKLIST=0
    NO_RUN_BLACKLIST=0
    EXTRA_ARGS=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tight-match)
                TIGHT_MATCH=1
                shift
                ;;
            --all-probe-pt)
                PROBE_PT_GT15=0
                shift
                ;;
            --bx-zero)
                BX_ZERO=1
                shift
                ;;
            --no-blacklist|--no-roll-blacklist)
                NO_BLACKLIST=1
                shift
                ;;
            --no-run-blacklist)
                NO_RUN_BLACKLIST=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                EXTRA_ARGS+=("$1")
                shift
                ;;
        esac
    done
}

run_all_years() {
    local label="$1"
    shift

    echo "[info] merging histograms for all years (${label})"
    for year in "${YEARS[@]}"; do
        bash "${MERGE_SCRIPT}" "${year}" "$@" "${EXTRA_ARGS[@]}"
    done
}

main() {
    parse_args "$@"

    local base_args=()
    local label="default"
    if [[ "${TIGHT_MATCH}" -eq 1 ]]; then
        base_args+=(--tight-match)
        label="tight-match"
    fi
    if [[ "${PROBE_PT_GT15}" -eq 0 ]]; then
        base_args+=(--all-probe-pt)
        label="${label}, all probe pT"
    fi
    if [[ "${BX_ZERO}" -eq 1 ]]; then
        base_args+=(--bx-zero)
        label="${label}, BX == 0 numerator"
    fi
    if [[ "${NO_BLACKLIST}" -eq 1 ]]; then
        base_args+=(--no-roll-blacklist)
        label="${label}, no roll blacklist"
    fi
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 ]]; then
        base_args+=(--no-run-blacklist)
        label="${label}, no run blacklist"
    fi
    run_all_years "${label}" "${base_args[@]}"

    echo "[info] done"
}

main "$@"
