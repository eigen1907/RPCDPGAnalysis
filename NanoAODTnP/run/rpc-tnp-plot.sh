#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EOS_RPC_BASE="${EOS_RPC_BASE:-/eos/user/${USER:0:1}/${USER}/rpc}"
INPUT_BASE="${INPUT_BASE:-${EOS_RPC_BASE}/tnp-hist-merged}"
PLOT_OUTPUT_BASE="${PLOT_OUTPUT_BASE:-${WORK_DIR}/plots}"
RUN3_YEARS="${RUN3_YEARS:-2022 2023 2024 2025 2026}"
RUN_META_PATH="${RUN_META_PATH:-${WORK_DIR}/data/lumi/run3.csv}"
GEOM_PATH="${GEOM_PATH:-${WORK_DIR}/data/geometry/run3.csv}"

require_plot_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1" >&2; exit 1; }
}

annual_lumi() {
    local year="$1"
    local short_year="${year:2:2}"
    awk -F, -v short_year="${short_year}" '
        $1 !~ /^#/ && substr($2, 7, 2) == short_year { sum += $4 }
        END { printf "%.3f", sum }
    ' "${RUN_META_PATH}"
}

append_run3_datasets() {
    local command_name="$1"
    local -n command_ref="${command_name}"
    local year config dataset primary_dataset campaign input_file lumi
    local inputs=()
    local datasets=()

    require_plot_command jq
    [[ -f "${RUN_META_PATH}" ]] || { echo "[error] missing run metadata: ${RUN_META_PATH}" >&2; exit 1; }

    for year in ${RUN3_YEARS}; do
        config="${WORK_DIR}/data/crab/Run${year}.json"
        [[ -f "${config}" ]] || { echo "[error] missing dataset config: ${config}" >&2; exit 1; }
        mapfile -t datasets < <(jq -er '.[].input_dataset' "${config}")
        inputs=()
        for dataset in "${datasets[@]}"; do
            IFS=/ read -r _ primary_dataset campaign _ <<< "${dataset}"
            input_file="${INPUT_BASE}/${primary_dataset}/${campaign}.root"
            [[ -f "${input_file}" ]] || { echo "[error] missing merged histogram: ${input_file}" >&2; exit 1; }
            inputs+=("${input_file}")
        done
        lumi="$(annual_lumi "${year}")"
        command_ref+=(-i "${inputs[@]}" -y "${year}" --lumi "${lumi}")
        echo "[config] Run${year}: files=${#inputs[@]} lumi=${lumi}/fb" >&2
    done
}

cmd=(
    python3 "${WORK_DIR}/scripts/rpc-tnp-plot.py"
    -o "${PLOT_OUTPUT_BASE}"
    -g "${GEOM_PATH}"
    --run-meta-path "${RUN_META_PATH}"
)
append_run3_datasets cmd

if [[ "${PLOT_YEARLY_2D:-0}" == "1" ]]; then
    cmd+=(--yearly-2d)
fi
if [[ "${PLOT_ROLL_MAPS:-0}" == "1" ]]; then
    cmd+=(--roll-maps)
fi

# cmd+=(-s 13.6)
# cmd+=(-l "Private Work")
# cmd+=(--ext pdf)

"${cmd[@]}"
