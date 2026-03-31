#!/bin/bash
set -euo pipefail

CMSSW_BASE="$1"
INPUT_EOS="$2"
CERT_PATH="$3"
OUTPUT_EOS="$4"
NAME="${5:-rpcTnP}"

ENDPOINT="root://eosuser.cern.ch"
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/rpc-tnp-XXXXXX")"
INPUT_LOCAL="${WORKDIR}/input.root"
OUTPUT_LOCAL="${WORKDIR}/output.root"
EMPTY_LOCAL="${WORKDIR}/output.empty"

if [[ "${OUTPUT_EOS}" == *.root ]]; then
    EMPTY_EOS="${OUTPUT_EOS%.root}.empty"
else
    EMPTY_EOS="${OUTPUT_EOS}.empty"
fi

cleanup() {
    rm -rf "${WORKDIR}"
}
trap cleanup EXIT

to_xrootd_url() {
    local path="$1"
    if [[ "${path}" == /eos/* ]]; then
        echo "${ENDPOINT}//${path#/}"
    else
        echo "${path}"
    fi
}

echo "[info] host=${HOSTNAME}"
echo "[info] workdir=${WORKDIR}"
echo "[info] input=${INPUT_EOS}"
echo "[info] output=${OUTPUT_EOS}"
echo "[info] empty=${EMPTY_EOS}"

source /cvmfs/cms.cern.ch/cmsset_default.sh
cd "${CMSSW_BASE}/src"
eval "$(scramv1 runtime -sh)"
cd "${WORKDIR}"

if [[ ! -f "${CERT_PATH}" ]]; then
    echo "[error] missing cert file: ${CERT_PATH}"
    exit 1
fi

xrdcp -f "$(to_xrootd_url "${INPUT_EOS}")" "${INPUT_LOCAL}"

python3 "${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/scripts/rpc-tnp-flatten.py" \
    "${INPUT_LOCAL}" \
    "${CERT_PATH}" \
    "${OUTPUT_LOCAL}" \
    "${NAME}"

xrdfs "${ENDPOINT}" mkdir -p "$(dirname "${OUTPUT_EOS}")"

if [[ -s "${OUTPUT_LOCAL}" ]]; then
    xrdcp -f "${OUTPUT_LOCAL}" "$(to_xrootd_url "${OUTPUT_EOS}")"
else
    : > "${EMPTY_LOCAL}"
    xrdcp -f "${EMPTY_LOCAL}" "$(to_xrootd_url "${EMPTY_EOS}")"
fi

echo "[done] ${INPUT_EOS}"