#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 5 || $# -gt 6 ]]; then
    echo "Usage: $0 CMSSW_BASE INPUT_EOS CERT_PATH ROLL_BLACKLIST_PATH OUTPUT_EOS [TABLE_NAME]" >&2
    exit 2
fi

CMSSW_BASE="$1"
INPUT_EOS="$2"
CERT_PATH="$3"
ROLL_BLACKLIST_PATH="$4"
OUTPUT_EOS="$5"
TABLE_NAME="${6:-rpcTnP}"

ENDPOINT="root://eosuser.cern.ch"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/rpc-tnp-analyze-XXXXXX")"
INPUT_LOCAL="${WORKDIR}/input.root"
OUTPUT_LOCAL="${WORKDIR}/output.root"

[[ "${OUTPUT_EOS}" == *.root ]] || {
    echo "[error] analysis output must end in .root: ${OUTPUT_EOS}" >&2
    exit 1
}

cleanup() {
    rm -rf -- "${WORKDIR}"
}
trap cleanup EXIT

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "[error] missing command: $1" >&2
        exit 1
    }
}

to_xrootd_url() {
    local path="$1"
    if [[ "${path}" == /eos/* ]]; then
        echo "${ENDPOINT}//${path#/}"
    else
        echo "${path}"
    fi
}

[[ -d "${CMSSW_BASE}/src" ]] || {
    echo "[error] missing CMSSW src directory: ${CMSSW_BASE}/src" >&2
    exit 1
}
[[ -f "${CERT_PATH}" ]] || {
    echo "[error] missing certification JSON: ${CERT_PATH}" >&2
    exit 1
}
[[ -f "${ROLL_BLACKLIST_PATH}" ]] || {
    echo "[error] missing roll blacklist: ${ROLL_BLACKLIST_PATH}" >&2
    exit 1
}
require_command xrdcp
require_command xrdfs

echo "[info] host=${HOSTNAME}"
echo "[info] input=${INPUT_EOS}"
echo "[info] hist_output=${OUTPUT_EOS}"
echo "[info] roll_blacklist=${ROLL_BLACKLIST_PATH}"

# shellcheck source=/dev/null
source /cvmfs/cms.cern.ch/cmsset_default.sh
cd "${CMSSW_BASE}/src"
eval "$(scramv1 runtime -sh)"
cd "${WORKDIR}"

xrdcp -f "$(to_xrootd_url "${INPUT_EOS}")" "${INPUT_LOCAL}"
python3 "${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/scripts/rpc-tnp-analyze.py" \
    --input "${INPUT_LOCAL}" \
    --cert "${CERT_PATH}" \
    --output "${OUTPUT_LOCAL}" \
    --roll-blacklist-path "${ROLL_BLACKLIST_PATH}" \
    --name "${TABLE_NAME}"

[[ -s "${OUTPUT_LOCAL}" ]] || {
    echo "[error] missing histogram shard: ${OUTPUT_LOCAL}" >&2
    exit 1
}

xrdfs "${ENDPOINT}" mkdir -p "$(dirname "${OUTPUT_EOS}")"
xrdcp -f "${OUTPUT_LOCAL}" "$(to_xrootd_url "${OUTPUT_EOS}")"
echo "[done] ${INPUT_EOS}"
