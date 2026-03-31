#!/bin/bash
set -euo pipefail
shopt -s nullglob

MODE="${1:-all}"
case "${MODE}" in
    all|resubmit) ;;
    *)
        echo "Usage: $0 [all|resubmit]"
        exit 1
        ;;
esac

INPUT_BASE="/eos/user/j/joshin/rpc/tnp/v1"
OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-flatten/v1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CMSSW_BASE="$(cd "${PACKAGE_DIR}/../../.." && pwd)"

ITEMS_TOOL="${SCRIPT_DIR}/rpc-tnp-flatten-items.py"
SUB_FILE="${SCRIPT_DIR}/rpc-tnp-flatten.sub"
CERT_DIR="${PACKAGE_DIR}/data/cert"

LOG_BASE="${PACKAGE_DIR}/logs/condor"
ITEMS_ALL_BASE="${LOG_BASE}/items/all"
ITEMS_RESUBMIT_BASE="${LOG_BASE}/items/resubmit"

SUBMIT_TAG="$(date +%y%m%d_%H%M%S)"
MAX_FILES=0

PDS=(
    #"SingleMuon"
    #"Muon"
    #"Muon0"
    "Muon1"
)

YEARS=(
    #"2022"
    #"2023"
    #"2024"
    "2025"
)

get_cert_file() {
    local year="$1"
    case "${year}" in
        2022) echo "${CERT_DIR}/Cert_Collisions2022_355100_362760_Golden.json" ;;
        2023) echo "${CERT_DIR}/Cert_Collisions2023_366442_370790_Golden.json" ;;
        2024) echo "${CERT_DIR}/Cert_Collisions2024_378981_386951_Golden.json" ;;
        2025) echo "${CERT_DIR}/Cert_Collisions2025_391658_398903_Golden.json" ;;
        *) return 1 ;;
    esac
}

make_log_dirs() {
    local submit_tag="$1"
    local pd="$2"
    local dataset_name="$3"

    mkdir -p \
        "${LOG_BASE}/${submit_tag}/${pd}/${dataset_name}/stdout" \
        "${LOG_BASE}/${submit_tag}/${pd}/${dataset_name}/stderr" \
        "${LOG_BASE}/${submit_tag}/${pd}/${dataset_name}/log"
}

mkdir -p "${LOG_BASE}" "${ITEMS_ALL_BASE}" "${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}"

for pd in "${PDS[@]}"; do
    for year in "${YEARS[@]}"; do
        cert_file="$(get_cert_file "${year}")" || {
            echo "[error] unknown year: ${year}"
            exit 1
        }

        for dataset_input in "${INPUT_BASE}/${pd}"/Run${year}*; do
            [[ -d "${dataset_input}" ]] || continue

            dataset_name="$(basename "${dataset_input}")"
            dataset_output="${OUTPUT_BASE}/${pd}/${dataset_name}"
            items_all_file="${ITEMS_ALL_BASE}/items_all_${pd}_${dataset_name}.txt"

            echo "============================================================"
            echo "[dataset] ${pd}/${dataset_name}"
            echo "          mode       : ${MODE}"
            echo "          input      : ${dataset_input}"
            echo "          output     : ${dataset_output}"
            echo "          cert       : ${cert_file}"
            echo "          submit_tag : ${SUBMIT_TAG}"

            if [[ "${MODE}" == "all" ]]; then
                cmd=(
                    python3 "${ITEMS_TOOL}" make
                    "${dataset_input}"
                    "${dataset_output}"
                    "${cert_file}"
                    "${items_all_file}"
                )

                if [[ "${MAX_FILES}" -gt 0 ]]; then
                    cmd+=(--max-files "${MAX_FILES}")
                fi

                "${cmd[@]}"
                items_file="${items_all_file}"
            else
                if [[ ! -f "${items_all_file}" ]]; then
                    echo "[skip] missing items file: ${items_all_file}"
                    continue
                fi

                items_file="${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}/items_resubmit_${pd}_${dataset_name}.txt"
                python3 "${ITEMS_TOOL}" missing "${items_all_file}" "${items_file}"
            fi

            if [[ ! -s "${items_file}" ]]; then
                echo "[skip] nothing to submit"
                continue
            fi

            make_log_dirs "${SUBMIT_TAG}" "${pd}" "${dataset_name}"

            condor_submit \
                "${SUB_FILE}" \
                ITEMS_FILE="${items_file}" \
                SUBMIT_TAG="${SUBMIT_TAG}" \
                CMSSW_BASE="${CMSSW_BASE}"
        done
    done
done

echo "============================================================"
echo "[done] submit_tag=${SUBMIT_TAG}"