#!/usr/bin/env bash
#set -euo pipefail

for d in "${CMSSW_BASE}"/src/RPCDPGAnalysis/NanoAODTnP/logs/crab/crab_*; do
  [ -d "$d" ] || continue
  echo "Resubmitting: $d"
  crab resubmit -d "$d"
done