#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/rpc-tnp-plot-common.sh"

cmd=(
    python3 "${WORK_DIR}/scripts/rpc-tnp-plot-rpc.py"
    -o "${PLOT_OUTPUT_BASE}"
    -g "${GEOM_PATH}"
    --run-meta-path "${RUN_META_PATH}"
)
append_run3_datasets cmd

# cmd+=(-s 13.6)
# cmd+=(-l "Private Work")
# cmd+=(--ext pdf)

"${cmd[@]}"
