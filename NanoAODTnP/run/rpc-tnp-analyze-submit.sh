#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR_RAW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run/rpc-tnp-common.sh
source "${SCRIPT_DIR_RAW}/rpc-tnp-common.sh"
SCRIPT_DIR="$(canonical_eos_path "${SCRIPT_DIR_RAW}")"

usage() {
    cat >&2 <<EOF
Usage: $0 YEAR {all|resubmit} [OPTIONS]

Options:
  --input-base PATH       Input NanoAOD base directory (default: /eos/user/j/joshin/rpc/tnp)
  --output-base PATH      Histogram output base directory
                          (default: /eos/user/j/joshin/rpc/tnp-hist, with suffixes
                           -tight, -all-probe-pt, -bx-zero, -wo-blacklist,
                           and/or -wo-run-blacklist as needed)
  --roll-blacklist PATH   Roll blacklist file to apply (default: data/blacklist/roll/blackListYYYY.txt)
  --run-blacklist PATH    Run blacklist file to apply (default: data/blacklist/run/blackList.txt)
  --no-blacklist          Do not apply the roll blacklist
  --no-roll-blacklist     Do not apply the roll blacklist
  --no-run-blacklist      Do not apply the run blacklist
  --tight-match           Use abs(residual_x) <= 20 cm or abs(pull_x) <= 4 as the matched selection
  --all-probe-pt          Disable the default pT > 15 GeV probe selection
  --bx-zero               Require BX == 0 in the efficiency numerator; the fiducial denominator is unchanged
  --files-per-job N       Number of NanoAOD files per job in all mode (default: 100);
                          resubmit mode reuses the chunks saved in items_all
  -h, --help              Show this help
EOF
}

usage_error() {
    usage
    exit 2
}

valid_year() {
    case "$1" in
        2022|2023|2024|2025|2026) return 0 ;;
        *) return 1 ;;
    esac
}

cert_file_for_year() {
    case "$1" in
        2022) echo "${CERT_DIR}/Cert_Collisions2022_355100_362760_Golden.json" ;;
        2023) echo "${CERT_DIR}/Cert_Collisions2023_366442_370790_Golden.json" ;;
        2024) echo "${CERT_DIR}/Cert_Collisions2024_378981_386951_Golden.json" ;;
        2025) echo "${CERT_DIR}/Cert_Collisions2025_391658_398903_Golden.json" ;;
        2026) echo "${CERT_DIR}/Cert_Collisions2026_401624_403493_Golden.json" ;;
        *) die "unsupported dataset year: $1" ;;
    esac
}

parse_args() {
    [[ $# -ge 1 ]] || usage_error
    case "$1" in
        -h|--help) usage; exit 0 ;;
    esac
    [[ $# -ge 2 ]] || usage_error

    YEAR="$1"
    MODE="$2"
    shift 2

    valid_year "${YEAR}" || usage_error
    case "${MODE}" in
        all|resubmit) ;;
        *) usage_error ;;
    esac

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input-base)
                [[ $# -ge 2 ]] || usage_error
                INPUT_BASE="$2"
                shift 2
                ;;
            --output-base)
                [[ $# -ge 2 ]] || usage_error
                OUTPUT_BASE="$2"
                OUTPUT_BASE_SET=1
                shift 2
                ;;
            --roll-blacklist)
                [[ $# -ge 2 ]] || usage_error
                ROLL_BLACKLIST_PATH="$2"
                shift 2
                ;;
            --run-blacklist)
                [[ $# -ge 2 ]] || usage_error
                RUN_BLACKLIST_PATH="$2"
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
            --files-per-job)
                [[ $# -ge 2 ]] || usage_error
                FILES_PER_JOB="$2"
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

configure_paths() {
    PACKAGE_DIR="$(canonical_eos_path "$(cd "${SCRIPT_DIR}/.." && pwd)")"
    CMSSW_BASE="$(canonical_eos_path "$(cd "${PACKAGE_DIR}/../../.." && pwd)")"
    ITEMS_TOOL="${PACKAGE_DIR}/scripts/rpc-tnp-analyze-items.py"
    SUB_FILE="${SCRIPT_DIR}/rpc-tnp-analyze.sub"
    CERT_DIR="${PACKAGE_DIR}/data/cert"
    ROLL_BLACKLIST_DIR="${PACKAGE_DIR}/data/blacklist/roll"
    RUN_BLACKLIST_DIR="${PACKAGE_DIR}/data/blacklist/run"
    LOG_BASE="${PACKAGE_DIR}/logs/condor"
    DATASET_CONFIG="${PACKAGE_DIR}/data/crab/Run${YEAR}.json"
    SUBMIT_TAG="$(date +%y%m%d_%H%M%S)"
    ITEMS_SUBMIT_BASE="${LOG_BASE}/${SUBMIT_TAG}/items"
    MATCH_MODE="default"
    if [[ "${TIGHT_MATCH}" -eq 1 ]]; then
        MATCH_MODE="tight"
    fi

    local item_mode=""
    if [[ "${TIGHT_MATCH}" -eq 1 ]]; then
        item_mode="tight"
    fi
    if [[ "${PROBE_PT_GT15}" -eq 0 ]]; then
        item_mode="${item_mode:+${item_mode}-}all-probe-pt"
    fi
    if [[ "${BX_ZERO}" -eq 1 ]]; then
        item_mode="${item_mode:+${item_mode}-}bx-zero"
    fi
    if [[ "${NO_BLACKLIST}" -eq 1 ]]; then
        item_mode="${item_mode:+${item_mode}-}no-blacklist"
    fi
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 ]]; then
        item_mode="${item_mode:+${item_mode}-}no-run-blacklist"
    fi
    if [[ -n "${item_mode}" ]]; then
        ITEMS_ALL_BASE="${LOG_BASE}/items/${item_mode}/all"
        ITEMS_RESUBMIT_BASE="${LOG_BASE}/items/${item_mode}/resubmit"
    else
        ITEMS_ALL_BASE="${LOG_BASE}/items/all"
        ITEMS_RESUBMIT_BASE="${LOG_BASE}/items/resubmit"
    fi
}

configure_blacklist() {
    if [[ "${NO_BLACKLIST}" -eq 1 && -n "${ROLL_BLACKLIST_PATH}" ]]; then
        die "--no-blacklist/--no-roll-blacklist and --roll-blacklist cannot be used together"
    fi
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 && -n "${RUN_BLACKLIST_PATH}" ]]; then
        die "--no-run-blacklist and --run-blacklist cannot be used together"
    fi
    if [[ "${OUTPUT_BASE_SET}" -eq 0 ]]; then
        OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-hist$(histogram_mode_suffix "${TIGHT_MATCH}" "${PROBE_PT_GT15}" "${BX_ZERO}" "${NO_BLACKLIST}" "${NO_RUN_BLACKLIST}")"
    fi

    CERT_FILE="$(cert_file_for_year "${YEAR}")"
    if [[ "${NO_BLACKLIST}" -eq 1 ]]; then
        ROLL_BLACKLIST_FILE="${ROLL_BLACKLIST_DIR}/blackListEmpty.txt"
        ROLL_BLACKLIST_MODE="skip-roll"
    elif [[ -n "${ROLL_BLACKLIST_PATH}" ]]; then
        ROLL_BLACKLIST_FILE="${ROLL_BLACKLIST_PATH}"
    else
        ROLL_BLACKLIST_FILE="${ROLL_BLACKLIST_DIR}/blackList${YEAR}.txt"
    fi
    if [[ "${NO_RUN_BLACKLIST}" -eq 1 ]]; then
        RUN_BLACKLIST_FILE="${RUN_BLACKLIST_DIR}/blackList.txt"
        RUN_BLACKLIST_MODE="skip-run"
    elif [[ -n "${RUN_BLACKLIST_PATH}" ]]; then
        RUN_BLACKLIST_FILE="${RUN_BLACKLIST_PATH}"
    else
        RUN_BLACKLIST_FILE="${RUN_BLACKLIST_DIR}/blackList.txt"
    fi
}

validate_config() {
    is_positive_int "${FILES_PER_JOB}" || die "--files-per-job must be a positive integer: ${FILES_PER_JOB}"
    require_command jq
    require_command python3
    require_file "${ITEMS_TOOL}"
    require_file "${SUB_FILE}"
    require_file "${DATASET_CONFIG}"
    require_file "${CERT_FILE}"
    if [[ "${ROLL_BLACKLIST_MODE}" == "apply-roll" ]]; then
        require_file "${ROLL_BLACKLIST_FILE}"
    fi
    if [[ "${RUN_BLACKLIST_MODE}" == "apply-run" ]]; then
        require_file "${RUN_BLACKLIST_FILE}"
    fi
}

configure_condor_pool() {
    command -v module >/dev/null 2>&1 || die "module command not found; run this from an lxplus shell"
    case "${PACKAGE_DIR}" in
        /eos/*)
            module load lxbatch/eossubmit
            SUBMIT_POOL="eossubmit"
            ;;
        /afs/*)
            module unload lxbatch/eossubmit >/dev/null 2>&1 || true
            module load lxbatch/share
            SUBMIT_POOL="share"
            ;;
        *)
            die "package must be located in AFS or EOS for Condor submission: ${PACKAGE_DIR}"
            ;;
    esac
    require_command condor_submit
}

load_datasets() {
    mapfile -t DATASETS < <(jq -er '.[] | .input_dataset | split("/") | "\(.[1])/\(.[2])"' "${DATASET_CONFIG}")
    [[ ${#DATASETS[@]} -gt 0 && -n "${DATASETS[0]}" ]] || die "no datasets configured"
}

prepare_item_dirs() {
    mkdir -p "${ITEMS_ALL_BASE}" "${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}" "${ITEMS_SUBMIT_BASE}"
}

make_items_for_dataset() {
    local dataset="$1"
    local pd="$2"
    local dataset_name="$3"
    local dataset_input="$4"
    local dataset_output="$5"
    local items_all_file="${ITEMS_ALL_BASE}/items_all_${pd}_${dataset_name}.txt"

    if [[ "${MODE}" == "all" ]]; then
        python3 "${ITEMS_TOOL}" make \
            --files-per-job "${FILES_PER_JOB}" \
            "${dataset_input}" \
            "${dataset_output}" \
            "${CERT_FILE}" \
            "${items_all_file}"
        ITEMS_FILE="${items_all_file}"
    else
        require_file "${items_all_file}"
        ITEMS_FILE="${ITEMS_RESUBMIT_BASE}/${SUBMIT_TAG}/items_resubmit_${pd}_${dataset_name}.txt"
        python3 "${ITEMS_TOOL}" missing "${items_all_file}" "${ITEMS_FILE}"
    fi
}

submit_items_for_dataset() {
    local pd="$1"
    local dataset_name="$2"
    local items_submit_file="${ITEMS_SUBMIT_BASE}/items_${MODE}_${pd}_${dataset_name}.txt"
    local log_dir="${LOG_BASE}/${SUBMIT_TAG}/${pd}/${dataset_name}"
    local submit_output=""
    local cluster_id=""

    cp -f "${ITEMS_FILE}" "${items_submit_file}"
    mkdir -p "${log_dir}/log"

    echo "          items      : ${items_submit_file}"
    submit_output="$(condor_submit \
        ITEMS_FILE="${items_submit_file}" \
        SUBMIT_TAG="${SUBMIT_TAG}" \
        CMSSW_BASE="${CMSSW_BASE}" \
        ROLL_BLACKLIST_PATH="${ROLL_BLACKLIST_FILE}" \
        RUN_BLACKLIST_PATH="${RUN_BLACKLIST_FILE}" \
        MATCH_MODE="${MATCH_MODE}" \
        ROLL_BLACKLIST_MODE="${ROLL_BLACKLIST_MODE}" \
        RUN_BLACKLIST_MODE="${RUN_BLACKLIST_MODE}" \
        PROBE_PT_GT15="${PROBE_PT_GT15}" \
        BX_ZERO="${BX_ZERO}" \
        "${SUB_FILE}" 2>&1)" || {
        printf '%s\n' "${submit_output}" >&2
        exit 1
    }
    printf '%s\n' "${submit_output}" | tee "${log_dir}/submit.txt"

    cluster_id="$(sed -n 's/.*cluster \([0-9][0-9]*\).*/\1/p' <<<"${submit_output}" | tail -n 1)"
    [[ -n "${cluster_id}" ]] || die "could not parse Condor cluster id for ${pd}/${dataset_name}"
    echo "[status] condor_q -nobatch ${cluster_id}"
}

print_dataset_header() {
    local dataset="$1"
    local dataset_input="$2"
    local dataset_output="$3"

    echo "============================================================"
    echo "[dataset] ${dataset}"
    echo "          mode       : ${MODE}"
    echo "          input      : ${dataset_input}"
    echo "          output     : ${dataset_output}"
    echo "          cert       : ${CERT_FILE}"
    echo "          roll bl    : ${ROLL_BLACKLIST_MODE}:${ROLL_BLACKLIST_FILE}"
    echo "          run bl     : ${RUN_BLACKLIST_MODE}:${RUN_BLACKLIST_FILE}"
    echo "          match mode : ${MATCH_MODE}"
    echo "          probe pT   : $([[ "${PROBE_PT_GT15}" -eq 1 ]] && echo '> 15 GeV' || echo 'all')"
    echo "          RPC BX     : $([[ "${BX_ZERO}" -eq 1 ]] && echo '0 (numerator only)' || echo 'all')"
    if [[ "${MODE}" == "all" ]]; then
        echo "          files/job  : ${FILES_PER_JOB}"
    else
        echo "          files/job  : from existing items_all"
    fi
}

submit_dataset() {
    local dataset="$1"
    local pd="${dataset%%/*}"
    local dataset_name="${dataset#*/}"
    local dataset_input="${INPUT_BASE}/${dataset}"
    local dataset_output="${OUTPUT_BASE}/${dataset}"

    [[ "${dataset_name}" == "Run${YEAR}"* ]] || die "dataset does not match requested year ${YEAR}: ${dataset}"
    require_dir "${dataset_input}"
    print_dataset_header "${dataset}" "${dataset_input}" "${dataset_output}"
    make_items_for_dataset "${dataset}" "${pd}" "${dataset_name}" "${dataset_input}" "${dataset_output}"

    if [[ ! -s "${ITEMS_FILE}" ]]; then
        echo "[done] nothing to submit for ${dataset}"
        return
    fi
    submit_items_for_dataset "${pd}" "${dataset_name}"
}

main() {
    INPUT_BASE="/eos/user/j/joshin/rpc/tnp"
    OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-hist"
    OUTPUT_BASE_SET=0
    ROLL_BLACKLIST_PATH=""
    RUN_BLACKLIST_PATH=""
    NO_BLACKLIST=0
    NO_RUN_BLACKLIST=0
    ROLL_BLACKLIST_MODE="apply-roll"
    RUN_BLACKLIST_MODE="apply-run"
    TIGHT_MATCH=0
    PROBE_PT_GT15=1
    BX_ZERO=0
    FILES_PER_JOB=100
    DATASETS=()

    parse_args "$@"
    configure_paths
    configure_blacklist
    validate_config
    configure_condor_pool
    load_datasets
    prepare_item_dirs

    echo "[submit] pool=${SUBMIT_POOL} package=${PACKAGE_DIR}"
    echo "[campaign] year=${YEAR} datasets=${#DATASETS[@]}"
    for dataset in "${DATASETS[@]}"; do
        submit_dataset "${dataset}"
    done

    echo "============================================================"
    echo "[done] submit_tag=${SUBMIT_TAG}"
}

main "$@"
