#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run/rpc-tnp-common.sh
source "${SCRIPT_DIR}/rpc-tnp-common.sh"
WORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EOS_RPC_BASE="${EOS_RPC_BASE:-/eos/user/${USER:0:1}/${USER}/rpc}"
RUN3_YEARS="${RUN3_YEARS:-2022 2023 2024 2025 2026}"
RUN_META_PATH="${RUN_META_PATH:-${WORK_DIR}/data/lumi/run3.csv}"
RUN_BLACKLIST_PATH="${RUN_BLACKLIST_PATH:-${WORK_DIR}/data/blacklist/run/blackList.txt}"
GEOM_PATH="${GEOM_PATH:-${WORK_DIR}/data/geometry/run3.csv}"

usage() {
    cat >&2 <<EOF
Usage: $0 [OPTIONS]

Options:
  --tight-match       Read tight-match merged histograms and write tight-match plot directories
  --all-probe-pt      Read full-probe-pT histograms and write all-probe-pt plot directories
  --bx-zero           Read BX == 0 numerator histograms and write bx-zero plot directories
  --no-roll-blacklist Read histograms produced without the roll blacklist
  --no-blacklist      Alias for --no-roll-blacklist
  --no-run-blacklist  Read histograms produced without the run blacklist
  --efficiency-maps   Draw per-year roll efficiency maps
  --roll-maps         Draw per-year RPC mean-CLS roll maps
  -h, --help          Show this help

Environment overrides:
  INPUT_BASE                  Selected campaign merged histogram base
  DEFAULT_INPUT_BASE          Blacklist-applied merged histogram base
  NO_BLACKLIST_INPUT_BASE     No-blacklist merged histogram base
  PLOT_OUTPUT_BASE            Plot output base directory
  RUN3_YEARS                  Space-separated year list
  RUN_META_PATH               Run metadata CSV path
  RUN_BLACKLIST_PATH          Run blacklist used for displayed luminosities
  PLOT_YEARLY_2D=1            Draw per-year 2D plots
  PLOT_EFFICIENCY_MAPS=1      Draw per-year roll efficiency maps
  PLOT_ROLL_MAPS=1            Draw per-year RPC mean-CLS roll maps
EOF
}

usage_error() {
    usage
    exit 2
}

parse_args() {
    TIGHT_MATCH=0
    PROBE_PT_GT15=1
    BX_ZERO=0
    NO_BLACKLIST=0
    NO_RUN_BLACKLIST=0
    EFFICIENCY_MAPS=0
    ROLL_MAPS=0

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
            --efficiency-maps)
                EFFICIENCY_MAPS=1
                shift
                ;;
            --roll-maps)
                ROLL_MAPS=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "[error] unknown argument: $1" >&2
                usage_error
                ;;
        esac
    done
}

apply_defaults() {
    local selection_suffix
    selection_suffix="$(histogram_mode_suffix "${TIGHT_MATCH}" "${PROBE_PT_GT15}" "${BX_ZERO}" "${NO_BLACKLIST}" "${NO_RUN_BLACKLIST}")"
    local input_base="${EOS_RPC_BASE}/tnp-hist${selection_suffix}-merged"
    local mode_name=""

    if [[ "${TIGHT_MATCH}" -eq 1 ]]; then
        mode_name="tight-match"
    fi
    if [[ "${PROBE_PT_GT15}" -eq 0 ]]; then
        mode_name="${mode_name:+${mode_name}-}all-probe-pt"
    fi
    if [[ "${BX_ZERO}" -eq 1 ]]; then
        mode_name="${mode_name:+${mode_name}-}bx-zero"
    fi
    if [[ "${NO_BLACKLIST}" -eq 1 ]]; then
        mode_name="${mode_name:+${mode_name}-}no-blacklist"
    fi
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 ]]; then
        mode_name="${mode_name:+${mode_name}-}no-run-blacklist"
    fi
    OUTPUT_SUBDIR="${mode_name:-default}"
    CAMPAIGN_LABEL="${mode_name:-default}"

    PLOT_OUTPUT_BASE="${PLOT_OUTPUT_BASE:-${WORK_DIR}/plots}"
    if [[ "${NO_BLACKLIST}" -eq 1 ]]; then
        CAMPAIGN_INPUT_BASE="${INPUT_BASE:-${NO_BLACKLIST_INPUT_BASE:-${input_base}}}"
        SHOW_EXCLUDED_ROLLS=0
    else
        CAMPAIGN_INPUT_BASE="${INPUT_BASE:-${DEFAULT_INPUT_BASE:-${input_base}}}"
        SHOW_EXCLUDED_ROLLS=1
    fi
}

require_plot_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1" >&2; exit 1; }
}

annual_lumi() {
    local year="$1"
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 ]]; then
        annual_recorded_lumi "${RUN_META_PATH}" "${year}"
    else
        annual_recorded_lumi "${RUN_META_PATH}" "${year}" "${RUN_BLACKLIST_PATH}"
    fi
}

append_run3_datasets() {
    local command_name="$1"
    local input_base="$2"
    local -n command_ref="${command_name}"
    local year config dataset primary_dataset campaign input_file lumi
    local inputs=()
    local datasets=()

    require_plot_command jq
    [[ -f "${RUN_META_PATH}" ]] || { echo "[error] missing run metadata: ${RUN_META_PATH}" >&2; exit 1; }
    if [[ "${NO_RUN_BLACKLIST}" -eq 0 ]]; then
        [[ -f "${RUN_BLACKLIST_PATH}" ]] || { echo "[error] missing run blacklist: ${RUN_BLACKLIST_PATH}" >&2; exit 1; }
    fi

    for year in ${RUN3_YEARS}; do
        config="${WORK_DIR}/data/crab/Run${year}.json"
        [[ -f "${config}" ]] || { echo "[error] missing dataset config: ${config}" >&2; exit 1; }
        mapfile -t datasets < <(jq -er '.[].input_dataset' "${config}")
        inputs=()
        for dataset in "${datasets[@]}"; do
            IFS=/ read -r _ primary_dataset campaign _ <<< "${dataset}"
            input_file="${input_base}/${primary_dataset}/${campaign}.root"
            [[ -f "${input_file}" ]] || { echo "[error] missing merged histogram: ${input_file}" >&2; exit 1; }
            inputs+=("${input_file}")
        done
        lumi="$(annual_lumi "${year}")"
        command_ref+=(-i "${inputs[@]}" -y "${year}" --lumi "${lumi}")
        echo "[config] Run${year}: files=${#inputs[@]} lumi=${lumi}/fb" >&2
    done
}

run_plot_campaign() {
    local label="$1"
    local input_base="$2"
    local output_dir="$3"
    local show_excluded_rolls="$4"
    local cmd=(
        python3 "${WORK_DIR}/scripts/rpc-tnp-plot.py"
        -o "${output_dir}"
        -g "${GEOM_PATH}"
        --run-meta-path "${RUN_META_PATH}"
    )

    echo "============================================================"
    echo "[plot-campaign] ${label}"
    echo "  input : ${input_base}"
    echo "  output: ${output_dir}"

    append_run3_datasets cmd "${input_base}"

    if [[ "${PLOT_YEARLY_2D:-0}" == "1" ]]; then
        cmd+=(--yearly-2d)
    fi
    if [[ "${EFFICIENCY_MAPS}" == "1" || "${PLOT_EFFICIENCY_MAPS:-0}" == "1" ]]; then
        cmd+=(--efficiency-maps)
    fi
    if [[ "${ROLL_MAPS}" == "1" || "${PLOT_ROLL_MAPS:-0}" == "1" ]]; then
        cmd+=(--roll-maps)
    fi
    if [[ "${show_excluded_rolls}" != "1" ]]; then
        cmd+=(--no-excluded-rolls)
    fi
    if [[ "${PROBE_PT_GT15}" == "0" ]]; then
        cmd+=(--all-probe-pt)
    fi

    # cmd+=(-s 13.6)
    # cmd+=(-l "Private Work")
    # cmd+=(--ext pdf)

    "${cmd[@]}"
}

main() {
    parse_args "$@"
    apply_defaults

    run_plot_campaign "${CAMPAIGN_LABEL}" "${CAMPAIGN_INPUT_BASE}" "${PLOT_OUTPUT_BASE}/${OUTPUT_SUBDIR}" "${SHOW_EXCLUDED_ROLLS}"
}

main "$@"
