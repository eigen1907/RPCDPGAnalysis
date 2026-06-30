#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${CMSSW_BASE:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
exec python3 "${WORK_DIR}/scripts/rpc-tnp-blacklist-summary.py" "$@"
