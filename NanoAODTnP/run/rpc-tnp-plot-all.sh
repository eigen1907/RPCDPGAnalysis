#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for category in rpc efficiency pair probe; do
    echo "============================================================"
    echo "[plot] ${category}"
    "${SCRIPT_DIR}/rpc-tnp-plot-${category}.sh"
done
