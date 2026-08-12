#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run/rpc-tnp-common.sh
source "${SCRIPT_DIR}/rpc-tnp-common.sh"
PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    cat >&2 <<EOF
Usage: $0 YEAR [OPTIONS]

Options:
  --input-base PATH   Histogram shard base directory (default: /eos/user/j/joshin/rpc/tnp-hist)
  --output-base PATH  Merged histogram output base directory (default: /eos/user/j/joshin/rpc/tnp-hist-merged)
  --tmp-base PATH     Temporary working directory (default: \${TMPDIR:-/tmp}/\${USER}/rpc-tnp-merge-hist)
  --no-roll-blacklist Use no-roll-blacklist input/output defaults
  --no-blacklist      Alias for --no-roll-blacklist
  --no-run-blacklist  Use no-run-blacklist input/output defaults
  --tight-match       Use tight-match input/output defaults
  --all-probe-pt      Use full-probe-pT histogram input/output defaults
  --bx-zero           Use BX == 0 numerator histogram input/output defaults
  -j, --jobs JOBS     Number of hadd worker processes; 0 disables multiprocessing (default: ${HADD_JOBS})
  -h, --help          Show this help
EOF
}

usage_error() {
    usage
    exit 2
}

parse_args() {
    [[ $# -ge 1 ]] || usage_error
    YEAR="$1"
    shift

    case "${YEAR}" in
        2022|2023|2024|2025|2026) ;;
        -h|--help) usage; exit 0 ;;
        *) usage_error ;;
    esac

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input-base)
                [[ $# -ge 2 ]] || usage_error
                INPUT_BASE="$2"
                INPUT_BASE_SET=1
                shift 2
                ;;
            --output-base)
                [[ $# -ge 2 ]] || usage_error
                OUTPUT_BASE="$2"
                OUTPUT_BASE_SET=1
                shift 2
                ;;
            --tmp-base)
                [[ $# -ge 2 ]] || usage_error
                TMP_BASE="$2"
                shift 2
                ;;
            --no-blacklist|--no-roll-blacklist)
                NO_BLACKLIST=1
                shift
                ;;
            --no-run-blacklist)
                NO_RUN_BLACKLIST=1
                shift
                ;;
            --tight-match)
                TIGHT_MATCH=1
                shift
                ;;
            --all-probe-pt)
                PROBE_PT_GT15=0
                shift
                ;;
            --bx-zero)
                BX_ZERO=1
                shift
                ;;
            -j|--jobs)
                [[ $# -ge 2 ]] || usage_error
                HADD_JOBS="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "[error] unknown argument: $1" >&2
                usage_error
                ;;
        esac
    done
}

apply_defaults() {
    local default_base
    default_base="/eos/user/j/joshin/rpc/tnp-hist$(histogram_mode_suffix "${TIGHT_MATCH}" "${PROBE_PT_GT15}" "${BX_ZERO}" "${NO_BLACKLIST}" "${NO_RUN_BLACKLIST}")"

    if [[ "${INPUT_BASE_SET}" -eq 0 ]]; then
        INPUT_BASE="${default_base}"
    fi
    if [[ "${OUTPUT_BASE_SET}" -eq 0 ]]; then
        OUTPUT_BASE="${default_base}-merged"
    fi
    DATASET_CONFIG="${PACKAGE_DIR}/data/crab/Run${YEAR}.json"
}

validate_config() {
    is_non_negative_int "${HADD_JOBS}" || die "HADD_JOBS must be a non-negative integer: ${HADD_JOBS}"
    require_command hadd
    require_command jq
    require_command rootls
    require_command xrdcp
    require_command xrdfs
    require_file "${DATASET_CONFIG}"
}

load_datasets() {
    mapfile -t DATASETS < <(jq -er '.[] | .input_dataset | split("/") | "\(.[1])/\(.[2])"' "${DATASET_CONFIG}")
    [[ ${#DATASETS[@]} -gt 0 && -n "${DATASETS[0]}" ]] || die "no datasets configured"
}

latest_tag() {
    local dataset_dir="$1"
    local tags=()
    mapfile -t tags < <(find "${dataset_dir}" -mindepth 1 -maxdepth 1 -type d | sort)
    [[ ${#tags[@]} -gt 0 ]] || die "no tag directory under: ${dataset_dir}"
    echo "${tags[${#tags[@]} - 1]}"
}

collect_input_files() {
    local dataset_dir="$1"
    local direct_files=("${dataset_dir}"/output_*.root)
    INFILES=()
    CHUNK_COUNT=0

    if [[ ${#direct_files[@]} -gt 0 ]]; then
        echo "[tag]     flat"
        INFILES=("${direct_files[@]}")
        CHUNK_COUNT=1
        return
    fi

    local tag_dir
    tag_dir="$(latest_tag "${dataset_dir}")"
    echo "[tag]     $(basename "${tag_dir}")"

    local chunk_dirs=("${tag_dir}"/*)
    [[ ${#chunk_dirs[@]} -gt 0 ]] || die "no chunk directories under: ${tag_dir}"
    for chunk_dir in "${chunk_dirs[@]}"; do
        require_dir "${chunk_dir}"
        local chunk_files=("${chunk_dir}"/output_*.root)
        [[ ${#chunk_files[@]} -gt 0 ]] || die "no histogram shards in: ${chunk_dir}"
        INFILES+=("${chunk_files[@]}")
    done
    CHUNK_COUNT=${#chunk_dirs[@]}
}

validate_merged_root() {
    local output="$1"
    local reference="$2"
    local output_keys=""
    local reference_keys=""

    [[ -s "${output}" ]] || return 1
    output_keys="$(rootls -1 "${output}" | LC_ALL=C sort)" || return 1
    reference_keys="$(rootls -1 "${reference}" | LC_ALL=C sort)" || return 1
    [[ -n "${output_keys}" && "${output_keys}" == "${reference_keys}" ]]
}

run_hadd_once() {
    local tmp_output="$1"
    local reference="$2"
    shift 2

    rm -f -- "${tmp_output}"
    "$@" || return $?
    validate_merged_root "${tmp_output}" "${reference}"
}

run_hadd_logged_once() {
    local tmp_output="$1"
    local log_file="$2"
    local reference="$3"
    shift 3

    rm -f -- "${tmp_output}" "${log_file}"
    "$@" >"${log_file}" 2>&1 || {
        local status=$?
        cat "${log_file}"
        return "${status}"
    }
    cat "${log_file}"
    if grep -q "TFileMerger::MergeRecursive" "${log_file}"; then
        return 42
    fi
    validate_merged_root "${tmp_output}" "${reference}"
}

merge_root_files() {
    local output="$1"
    shift
    [[ $# -gt 0 ]] || die "no input files for merge output: ${output}"

    mkdir -p "$(dirname "${output}")"
    local tmp_output="${output%.root}.tmp.root"
    local input_list="${output%.root}.inputs.txt"
    local log_file="${output%.root}.hadd.log"
    rm -f -- "${tmp_output}" "${input_list}" "${log_file}"
    printf '%s\n' "$@" > "${input_list}"

    local command=(hadd -T -fk101 -v 0)
    if [[ "${HADD_JOBS}" -gt 0 ]]; then
        command+=(-j "${HADD_JOBS}" -d "$(dirname "${tmp_output}")")
    fi
    command+=("${tmp_output}" "@${input_list}")

    local start_seconds=${SECONDS}
    if [[ "${HADD_JOBS}" -gt 0 ]]; then
        local status=0
        run_hadd_logged_once "${tmp_output}" "${log_file}" "$1" "${command[@]}" || status=$?
        if [[ "${status}" -eq 42 ]]; then
            echo "  [warn] parallel hadd reported TFileMerger merge errors; retrying serial hadd" >&2
            local serial_command=(hadd -T -fk101 -v 0 "${tmp_output}" "@${input_list}")
            retry_command "serial hadd $(basename "${output}")" run_hadd_once "${tmp_output}" "$1" "${serial_command[@]}"
        elif [[ "${status}" -ne 0 ]]; then
            echo "  [warn] parallel hadd failed or produced an invalid ROOT file (exit ${status}); retrying serial hadd" >&2
            local serial_command=(hadd -T -fk101 -v 0 "${tmp_output}" "@${input_list}")
            retry_command "serial hadd $(basename "${output}")" run_hadd_once "${tmp_output}" "$1" "${serial_command[@]}"
        fi
    else
        retry_command "hadd $(basename "${output}")" run_hadd_once "${tmp_output}" "$1" "${command[@]}"
    fi
    mv -f -- "${tmp_output}" "${output}"
    rm -f -- "${input_list}" "${log_file}"
    echo "  [merge-done] $(basename "${output}") elapsed=$((SECONDS - start_seconds))s size=$(du -h "${output}" | cut -f1)"
}

create_eos_dir_once() {
    local eos_dir="$1"
    xrdfs "${EOS_XROOTD_ENDPOINT}" mkdir -p "${eos_dir}"
}

copy_merged_once() {
    local local_file="$1"
    local eos_file="$2"
    xrdcp -f "${local_file}" "$(to_xrootd_url "${eos_file}")"
}

copy_merged_file() {
    local local_file="$1"
    local pd="$2"
    local dataset_name="$3"
    local eos_dir="${OUTPUT_BASE}/${pd}"
    local eos_file="${eos_dir}/${dataset_name}.root"

    retry_command "create EOS output directory" create_eos_dir_once "${eos_dir}"
    retry_command "copy merged output" copy_merged_once "${local_file}" "${eos_file}"
    echo "  [done] ${eos_file}"
}

merge_dataset() {
    local dataset="$1"
    local pd="${dataset%%/*}"
    local dataset_name="${dataset#*/}"
    local dataset_dir="${INPUT_BASE}/${dataset}"
    local work_dir="${TMP_BASE}/${dataset}"
    local final_local="${work_dir}/${dataset_name}.root"

    require_dir "${dataset_dir}"
    echo "============================================================"
    echo "[dataset] ${dataset}"

    reset_work_dir "${work_dir}"
    collect_input_files "${dataset_dir}"
    echo "  [merge-dataset] ${dataset_name} (${#INFILES[@]} files from ${CHUNK_COUNT} chunks)"
    merge_root_files "${final_local}" "${INFILES[@]}"
    copy_merged_file "${final_local}" "${pd}" "${dataset_name}"
}

main() {
    INPUT_BASE="/eos/user/j/joshin/rpc/tnp-hist"
    OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-hist-merged"
    TMP_BASE="${TMPDIR:-/tmp}/${USER}/rpc-tnp-merge-hist"
    HADD_JOBS=2
    INPUT_BASE_SET=0
    OUTPUT_BASE_SET=0
    NO_BLACKLIST=0
    NO_RUN_BLACKLIST=0
    TIGHT_MATCH=0
    PROBE_PT_GT15=1
    BX_ZERO=0
    DATASETS=()

    parse_args "$@"
    apply_defaults
    validate_config
    load_datasets

    mkdir -p "${TMP_BASE}"
    echo "[config] year=${YEAR} datasets=${#DATASETS[@]} tight_match=${TIGHT_MATCH} probe_pt_gt15=${PROBE_PT_GT15} bx_zero=${BX_ZERO} no_blacklist=${NO_BLACKLIST} no_run_blacklist=${NO_RUN_BLACKLIST} input_base=${INPUT_BASE} output_base=${OUTPUT_BASE} hadd_jobs=${HADD_JOBS} tmp_base=${TMP_BASE}"
    for dataset in "${DATASETS[@]}"; do
        merge_dataset "${dataset}"
    done
}

main "$@"
