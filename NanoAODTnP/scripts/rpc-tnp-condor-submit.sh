#!/bin/bash
set -euo pipefail

INPUT_BASE="/hdfs/user/joshin/rpc/tnp"
OUTPUT_BASE="/hdfs/user/joshin/rpc/tnp-flatten"

SUBMIT_CMD="rpc-tnp-flatten-submit.py"
SCRIPT_PATH="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/scripts/rpc-tnp-flatten.py"
CERT_PATH="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/cert"

SUBMIT_DIR_BASE="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/logs/condor"
SLEEP_BETWEEN_SUBMITS=2

if [ -z "${CMSSW_BASE:-}" ]; then
    echo "[error] CMSSW_BASE is not set."
    exit 1
fi

if ! command -v "${SUBMIT_CMD}" >/dev/null 2>&1; then
    echo "[error] ${SUBMIT_CMD} not found in PATH"
    exit 1
fi

if [ ! -f "${SCRIPT_PATH}" ]; then
    echo "[error] flatten script not found: ${SCRIPT_PATH}"
    exit 1
fi

if [ ! -d "${CERT_PATH}" ]; then
    echo "[error] cert path not found: ${CERT_PATH}"
    exit 1
fi

count_dataset=0

find "${INPUT_BASE}" -type d | while read -r dataset_dir; do
    shopt -s nullglob
    chunk_dirs=( "${dataset_dir}"/000* )
    shopt -u nullglob

    [ ${#chunk_dirs[@]} -gt 0 ] || continue

    rel_path="${dataset_dir#${INPUT_BASE}/}"
    output_path="${OUTPUT_BASE}/${rel_path}"
    submit_dir="${SUBMIT_DIR_BASE}/${rel_path}"

    batch_name="rpc-tnp-flatten-$(echo "${rel_path}" | tr '/' '-')"

    echo "============================================================"
    echo "[submit] ${rel_path}"
    echo "         input      : ${dataset_dir}"
    echo "         output     : ${output_path}"
    echo "         submit-dir : ${submit_dir}"
    echo "         batch-name : ${batch_name}"

    ${SUBMIT_CMD} \
        -i "${dataset_dir}" \
        -o "${output_path}" \
        -s "${SCRIPT_PATH}" \
        -c "${CERT_PATH}" \
        --submit-dir "${submit_dir}" \
        --batch-name "${batch_name}"

    count_dataset=$((count_dataset + 1))
    sleep "${SLEEP_BETWEEN_SUBMITS}"
done

echo "============================================================"
echo "[done] submitted datasets: ${count_dataset}"