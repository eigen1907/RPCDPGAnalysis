#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP"
exec python3 "${WORK_DIR}/scripts/rpc-tnp-lumi-summary.py" "$@"
