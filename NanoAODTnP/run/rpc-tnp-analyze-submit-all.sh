#!/usr/bin/env bash
set -euo pipefail

MODE="all"
if [[ $# -gt 0 && "$1" != --* ]]; then
    MODE="$1"
    shift
fi
EXTRA_ARGS=("$@")

SUBMIT_SCRIPT=${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/run/rpc-tnp-analyze-submit.sh

if [[ "${MODE}" == "resubmit" ]]; then
    echo "[info] resubmitting jobs for all years"
else
    echo "[info] submitting jobs for all years"
fi

bash "${SUBMIT_SCRIPT}" 2022 "${MODE}" "${EXTRA_ARGS[@]}"
bash "${SUBMIT_SCRIPT}" 2023 "${MODE}" "${EXTRA_ARGS[@]}"
bash "${SUBMIT_SCRIPT}" 2024 "${MODE}" "${EXTRA_ARGS[@]}"
bash "${SUBMIT_SCRIPT}" 2025 "${MODE}" "${EXTRA_ARGS[@]}"
bash "${SUBMIT_SCRIPT}" 2026 "${MODE}" "${EXTRA_ARGS[@]}"

echo "[info] done"
