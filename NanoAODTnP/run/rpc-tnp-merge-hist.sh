#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

# Edit the year-specific JSON files under data/crab before merging a different production.
INPUT_BASE="${INPUT_BASE:-/eos/user/j/joshin/rpc/tnp-hist}"
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/j/joshin/rpc/tnp-hist-merged}"
ENDPOINT="${ENDPOINT:-root://eosuser.cern.ch}"
TMP_BASE="${TMP_BASE:-${TMPDIR:-/tmp}/${USER}/rpc-tnp-merge-hist}"
HADD_JOBS="${HADD_JOBS:-8}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    echo "Usage: $0 YEAR [-j JOBS]" >&2
    echo "  -j, --jobs JOBS  Number of hadd worker processes; 0 disables multiprocessing (default: ${HADD_JOBS})" >&2
}

[[ $# -ge 1 ]] || { usage; exit 2; }
YEAR="$1"
shift
case "${YEAR}" in
    2022|2023|2024|2025|2026) ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
esac
DATASET_CONFIG="${PACKAGE_DIR}/data/crab/Run${YEAR}.json"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -j|--jobs)
            [[ $# -ge 2 ]] || { usage; exit 2; }
            HADD_JOBS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

require_command() {
    command -v "$1" >/dev/null 2>&1 || { echo "[error] missing command: $1" >&2; exit 1; }
}

to_xrootd_url() {
    local path="$1"
    if [[ "${path}" == /eos/* ]]; then
        echo "${ENDPOINT}//${path#/}"
    else
        echo "${path}"
    fi
}

safe_reset_work_dir() {
    local work_dir="$1"
    [[ -n "${work_dir}" && "${work_dir}" != "/" ]] || {
        echo "[error] refusing to reset unsafe work directory: ${work_dir}" >&2
        exit 1
    }
    rm -rf -- "${work_dir}"
    mkdir -p "${work_dir}"
}

latest_tag() {
    local dataset_dir="$1"
    local tags=()
    mapfile -t tags < <(find "${dataset_dir}" -mindepth 1 -maxdepth 1 -type d | sort)
    [[ ${#tags[@]} -gt 0 ]] || { echo "[error] no tag directory under: ${dataset_dir}" >&2; exit 1; }
    echo "${tags[${#tags[@]} - 1]}"
}

merge_root_files() {
    local output="$1"
    shift
    [[ $# -gt 0 ]] || { echo "[error] no input files for merge output: ${output}" >&2; exit 1; }
    mkdir -p "$(dirname "${output}")"
    local tmp_output="${output%.root}.tmp.root"
    local input_list="${output%.root}.inputs.txt"
    rm -f -- "${tmp_output}" "${input_list}"
    printf '%s\n' "$@" > "${input_list}"

    local command=(hadd -T -fk101 -v 0)
    if [[ "${HADD_JOBS}" -gt 0 ]]; then
        command+=(-j "${HADD_JOBS}" -d "$(dirname "${tmp_output}")")
    fi
    command+=("${tmp_output}" "@${input_list}")
    local start_seconds=${SECONDS}
    "${command[@]}"
    mv -f -- "${tmp_output}" "${output}"
    rm -f -- "${input_list}"
    echo "  [merge-done] $(basename "${output}") elapsed=$((SECONDS - start_seconds))s size=$(du -h "${output}" | cut -f1)"
}

require_command hadd
require_command jq
require_command xrdcp
require_command xrdfs
[[ -f "${DATASET_CONFIG}" ]] || { echo "[error] missing file: ${DATASET_CONFIG}" >&2; exit 1; }
datasets_output="$(jq -er '.[] | .input_dataset | split("/") | "\(.[1])/\(.[2])"' "${DATASET_CONFIG}")"
mapfile -t DATASETS <<< "${datasets_output}"
[[ ${#DATASETS[@]} -gt 0 && -n "${DATASETS[0]}" ]] || {
    echo "[error] no datasets configured" >&2
    exit 1
}
[[ "${HADD_JOBS}" =~ ^[0-9]+$ ]] || { echo "[error] HADD_JOBS must be a non-negative integer: ${HADD_JOBS}" >&2; exit 1; }
mkdir -p "${TMP_BASE}"
echo "[config] year=${YEAR} datasets=${#DATASETS[@]} hadd_jobs=${HADD_JOBS} tmp_base=${TMP_BASE}"

for dataset in "${DATASETS[@]}"; do
    dataset_dir="${INPUT_BASE}/${dataset}"
    [[ -d "${dataset_dir}" ]] || { echo "[error] missing configured analysis output directory: ${dataset_dir}" >&2; exit 1; }
    tag_dir="$(latest_tag "${dataset_dir}")"
    chunk_dirs=("${tag_dir}"/*)
    [[ ${#chunk_dirs[@]} -gt 0 ]] || { echo "[error] no chunk directories under: ${tag_dir}" >&2; exit 1; }

    echo "============================================================"
    echo "[dataset] ${dataset}"
    echo "[tag]     $(basename "${tag_dir}")"
    work_dir="${TMP_BASE}/${dataset}"
    safe_reset_work_dir "${work_dir}"
    infiles=()

    for chunk_dir in "${chunk_dirs[@]}"; do
        [[ -d "${chunk_dir}" ]] || { echo "[error] expected chunk directory: ${chunk_dir}" >&2; exit 1; }
        chunk_files=("${chunk_dir}"/output_*.root)
        [[ ${#chunk_files[@]} -gt 0 ]] || { echo "[error] no histogram shards in: ${chunk_dir}" >&2; exit 1; }
        infiles+=("${chunk_files[@]}")
    done

    dataset_name="${dataset#*/}"
    pd="${dataset%%/*}"
    final_local="${work_dir}/${dataset_name}.root"
    echo "  [merge-dataset] ${dataset_name} (${#infiles[@]} files from ${#chunk_dirs[@]} chunks)"
    merge_root_files "${final_local}" "${infiles[@]}"

    final_eos_dir="${OUTPUT_BASE}/${pd}"
    final_eos_file="${final_eos_dir}/${dataset_name}.root"
    xrdfs "${ENDPOINT}" mkdir -p "${final_eos_dir}"
    xrdcp -f "${final_local}" "$(to_xrootd_url "${final_eos_file}")"
    echo "  [done] ${final_eos_file}"
done
