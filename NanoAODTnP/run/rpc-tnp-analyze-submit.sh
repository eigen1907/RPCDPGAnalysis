#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 YEAR {all|resubmit}" >&2
}

[[ $# -eq 2 ]] || { usage; exit 2; }
YEAR="$1"
MODE="$2"
case "${YEAR}" in
    2022|2023|2024|2025|2026) ;;
    *) usage; exit 2 ;;
esac
case "${MODE}" in
    all|resubmit) ;;
    *) usage; exit 2 ;;
esac

# Edit the year-specific JSON files under data/crab before submitting a different production.
INPUT_BASE="${INPUT_BASE:-/eos/user/j/joshin/rpc/tnp}"
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/j/joshin/rpc/tnp-hist}"

canonical_eos_path() {
    local path="$1"
    if [[ "${path}" =~ ^/eos/home-([^/]+)/([^/]+)(/.*)?$ ]]; then
        echo "/eos/user/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
    else
        echo "${path}"
    fi
}

require_file() {
    [[ -f "$1" ]] || { echo "[error] missing file: $1" >&2; exit 1; }
}

SCRIPT_DIR="$(canonical_eos_path "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
PACKAGE_DIR="$(canonical_eos_path "$(cd "${SCRIPT_DIR}/.." && pwd)")"
CMSSW_BASE="$(canonical_eos_path "$(cd "${PACKAGE_DIR}/../../.." && pwd)")"
ITEMS_TOOL="${PACKAGE_DIR}/scripts/rpc-tnp-analyze-items.py"
SUB_FILE="${SCRIPT_DIR}/rpc-tnp-analyze.sub"
CERT_DIR="${PACKAGE_DIR}/data/cert"
ROLL_BLACKLIST_DIR="${PACKAGE_DIR}/data/blacklist/roll"
LOG_BASE="${PACKAGE_DIR}/logs/condor"
ITEMS_ALL_BASE="${LOG_BASE}/items/all"
ITEMS_RESUBMIT_BASE="${LOG_BASE}/items/resubmit"
SUBMIT_TAG="$(date +%y%m%d_%H%M%S)"
ITEMS_SUBMIT_BASE="${LOG_BASE}/${SUBMIT_TAG}/items"
DATASET_CONFIG="${PACKAGE_DIR}/data/crab/Run${YEAR}.json"

get_cert_file() {
    case "$1" in
        2022) echo "${CERT_DIR}/Cert_Collisions2022_355100_362760_Golden.json" ;;
        2023) echo "${CERT_DIR}/Cert_Collisions2023_366442_370790_Golden.json" ;;
        2024) echo "${CERT_DIR}/Cert_Collisions2024_378981_386951_Golden.json" ;;
        2025) echo "${CERT_DIR}/Cert_Collisions2025_391658_398903_Golden.json" ;;
        2026) echo "${CERT_DIR}/Cert_Collisions2026_401624_403493_Golden.json" ;;
        *) echo "[error] unsupported dataset year: $1" >&2; exit 1 ;;
    esac
}

if ! command -v module >/dev/null 2>&1; then
    echo "[error] module command not found; run this from an lxplus shell" >&2
    exit 1
fi
case "${PACKAGE_DIR}" in
    /eos/*)
        module load lxbatch/eossubmit
        submit_pool="eossubmit"
        ;;
    /afs/*)
        module unload lxbatch/eossubmit >/dev/null 2>&1 || true
        module load lxbatch/share
        submit_pool="share"
        ;;
    *)
        echo "[error] package must be located in AFS or EOS for Condor submission: ${PACKAGE_DIR}" >&2
        exit 1
        ;;
esac
echo "[submit] pool=${submit_pool} package=${PACKAGE_DIR}"
command -v condor_submit >/dev/null 2>&1 || { echo "[error] missing command: condor_submit" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "[error] missing command: jq" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "[error] missing command: python3" >&2; exit 1; }
require_file "${ITEMS_TOOL}"
require_file "${SUB_FILE}"
require_file "${DATASET_CONFIG}"
cert_file="$(get_cert_file "${YEAR}")"
roll_blacklist_file="${ROLL_BLACKLIST_DIR}/blackList${YEAR}.txt"
require_file "${cert_file}"
require_file "${roll_blacklist_file}"
datasets_output="$(jq -er '.[] | .input_dataset | split("/") | "\(.[1])/\(.[2])"' "${DATASET_CONFIG}")"
mapfile -t DATASETS <<< "${datasets_output}"
[[ ${#DATASETS[@]} -gt 0 && -n "${DATASETS[0]}" ]] || {
    echo "[error] no datasets configured" >&2
    exit 1
}
echo "[campaign] year=${YEAR} datasets=${#DATASETS[@]}"
mkdir -p "${ITEMS_ALL_BASE}" "${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}" "${ITEMS_SUBMIT_BASE}"

for dataset in "${DATASETS[@]}"; do
    pd="${dataset%%/*}"
    dataset_name="${dataset#*/}"
    [[ "${dataset_name}" == "Run${YEAR}"* ]] || {
        echo "[error] dataset does not match requested year ${YEAR}: ${dataset}" >&2
        exit 1
    }

    dataset_input="${INPUT_BASE}/${dataset}"
    dataset_output="${OUTPUT_BASE}/${dataset}"
    items_all_file="${ITEMS_ALL_BASE}/items_all_${pd}_${dataset_name}.txt"
    [[ -d "${dataset_input}" ]] || {
        echo "[error] missing configured NanoAOD dataset directory: ${dataset_input}" >&2
        exit 1
    }

    echo "============================================================"
    echo "[dataset] ${dataset}"
    echo "          mode       : ${MODE}"
    echo "          input      : ${dataset_input}"
    echo "          output     : ${dataset_output}"
    echo "          cert       : ${cert_file}"
    echo "          blacklist  : ${roll_blacklist_file}"

    if [[ "${MODE}" == "all" ]]; then
        python3 "${ITEMS_TOOL}" make "${dataset_input}" "${dataset_output}" "${cert_file}" "${items_all_file}"
        items_file="${items_all_file}"
    else
        require_file "${items_all_file}"
        items_file="${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}/items_resubmit_${pd}_${dataset_name}.txt"
        python3 "${ITEMS_TOOL}" missing "${items_all_file}" "${items_file}"
    fi

    if [[ ! -s "${items_file}" ]]; then
        echo "[done] nothing to submit for ${dataset}"
        continue
    fi

    items_submit_file="${ITEMS_SUBMIT_BASE}/items_${MODE}_${pd}_${dataset_name}.txt"
    cp -f "${items_file}" "${items_submit_file}"
    log_dir="${LOG_BASE}/${SUBMIT_TAG}/${pd}/${dataset_name}"
    mkdir -p "${log_dir}/log"

    echo "          items      : ${items_submit_file}"
    submit_output="$(condor_submit ITEMS_FILE="${items_submit_file}" SUBMIT_TAG="${SUBMIT_TAG}" CMSSW_BASE="${CMSSW_BASE}" ROLL_BLACKLIST_PATH="${roll_blacklist_file}" "${SUB_FILE}" 2>&1)" || {
        printf '%s\n' "${submit_output}" >&2
        exit 1
    }
    printf '%s\n' "${submit_output}" | tee "${log_dir}/submit.txt"
    cluster_id="$(sed -n 's/.*cluster \([0-9][0-9]*\).*/\1/p' <<<"${submit_output}" | tail -n 1)"
    [[ -n "${cluster_id}" ]] || {
        echo "[error] could not parse Condor cluster id for ${dataset}" >&2
        exit 1
    }
    echo "[status] condor_q -nobatch ${cluster_id}"
done

echo "============================================================"
echo "[done] submit_tag=${SUBMIT_TAG}"
