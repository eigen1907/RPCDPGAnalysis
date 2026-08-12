#!/usr/bin/env bash
set -euo pipefail

: "${CMSSW_BASE:?Enter the CMSSW runtime before submitting CRAB jobs}"
WORK_DIR="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP"

exec python3 "${WORK_DIR}/scripts/rpc-tnp-crab-submit.py" \
    --pset "${WORK_DIR}/test/muRPCTnPFlatTableProducer_cfg.py" \
    --input "${WORK_DIR}/data/crab/Recover.json" \
    --storage-site T3_CH_CERNBOX \
    --user joshin \
    --name rpc/tnp \
    --units-per-job 10
