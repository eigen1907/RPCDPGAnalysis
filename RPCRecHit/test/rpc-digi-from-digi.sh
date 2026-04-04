#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:-step2.root}"

python3 rpc-digi-from-digi.py \
  -i "step2.root" \
  -g "Run4D125.csv" \
  -o "./plots-rpc-digi" \
  --rpcdigi-label simMuonRPCDigis \
  --rpcdigi-phase2-label simMuonRPCDigisPhase2 \
  --irpcdigi-label simMuonIRPCDigis \
  --year Phase2 \
  --com 14 \
  --label "Private Work"