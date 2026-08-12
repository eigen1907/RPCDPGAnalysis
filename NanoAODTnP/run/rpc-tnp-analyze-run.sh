#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=run/rpc-tnp-common.sh
source "${SCRIPT_DIR}/rpc-tnp-common.sh"

usage() {
    echo "Usage: $0 CMSSW_BASE INPUT_EOS[|INPUT_EOS...] CERT_PATH ROLL_BLACKLIST_PATH RUN_BLACKLIST_PATH OUTPUT_EOS [default|tight] [apply-roll|skip-roll] [apply-run|skip-run] [probe-pt-gt15:0|1, default:1] [bx-zero:0|1]" >&2
}

[[ $# -ge 6 && $# -le 11 ]] || { usage; exit 2; }

CMSSW_BASE="$1"
INPUT_EOS_ARG="$2"
CERT_PATH="$3"
ROLL_BLACKLIST_PATH="$4"
RUN_BLACKLIST_PATH="$5"
OUTPUT_EOS="$6"
MATCH_MODE="${7:-default}"
ROLL_BLACKLIST_MODE="${8:-apply-roll}"
RUN_BLACKLIST_MODE="${9:-apply-run}"
PROBE_PT_GT15="${10:-1}"
BX_ZERO="${11:-0}"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rpc-tnp-analyze-XXXXXX")"
OUTPUT_LOCAL="${WORK_DIR}/output.root"
ANALYZE_SCRIPT="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/scripts/rpc-tnp-analyze.py"
INPUT_EOS_LIST=()
OUTPUT_PARTS=()

cleanup() {
    rm -rf -- "${WORK_DIR}"
}
trap cleanup EXIT

validate_inputs() {
    [[ "${OUTPUT_EOS}" == *.root ]] || die "analysis output must end in .root: ${OUTPUT_EOS}"
    [[ "${MATCH_MODE}" == "default" || "${MATCH_MODE}" == "tight" ]] || die "unknown match mode: ${MATCH_MODE}"
    [[ "${ROLL_BLACKLIST_MODE}" == "apply-roll" || "${ROLL_BLACKLIST_MODE}" == "skip-roll" ]] || die "unknown roll blacklist mode: ${ROLL_BLACKLIST_MODE}"
    [[ "${RUN_BLACKLIST_MODE}" == "apply-run" || "${RUN_BLACKLIST_MODE}" == "skip-run" ]] || die "unknown run blacklist mode: ${RUN_BLACKLIST_MODE}"
    [[ "${PROBE_PT_GT15}" == "0" || "${PROBE_PT_GT15}" == "1" ]] || die "probe-pt-gt15 must be 0 or 1: ${PROBE_PT_GT15}"
    [[ "${BX_ZERO}" == "0" || "${BX_ZERO}" == "1" ]] || die "bx-zero must be 0 or 1: ${BX_ZERO}"
    require_dir "${CMSSW_BASE}/src"
    require_file "${CERT_PATH}"
    if [[ "${ROLL_BLACKLIST_MODE}" == "apply-roll" ]]; then
        require_file "${ROLL_BLACKLIST_PATH}"
    fi
    if [[ "${RUN_BLACKLIST_MODE}" == "apply-run" ]]; then
        require_file "${RUN_BLACKLIST_PATH}"
    fi
    require_file "${ANALYZE_SCRIPT}"
}

split_input_list() {
    IFS='|' read -r -a INPUT_EOS_LIST <<< "${INPUT_EOS_ARG}"
    [[ ${#INPUT_EOS_LIST[@]} -gt 0 && -n "${INPUT_EOS_LIST[0]}" ]] || die "empty input list"
}

setup_cmssw_runtime() {
    # shellcheck source=/dev/null
    source /cvmfs/cms.cern.ch/cmsset_default.sh
    cd "${CMSSW_BASE}/src"
    eval "$(scramv1 runtime -sh)"
    cd "${WORK_DIR}"

    require_command hadd
    require_command python3
    require_command xrdcp
    require_command xrdfs
}

copy_input_once() {
    local input_eos="$1"
    local input_local="$2"

    rm -f -- "${input_local}"
    xrdcp -f "$(to_xrootd_url "${input_eos}")" "${input_local}" || return $?
    [[ -s "${input_local}" ]]
}

run_analysis_once() {
    local input_local="$1"
    local output_part="$2"
    local analyze_args=(
        --input "${input_local}"
        --cert "${CERT_PATH}"
        --output "${output_part}"
    )

    if [[ "${ROLL_BLACKLIST_MODE}" == "apply-roll" ]]; then
        analyze_args+=(--roll-blacklist-path "${ROLL_BLACKLIST_PATH}")
    else
        analyze_args+=(--no-roll-blacklist)
    fi
    if [[ "${RUN_BLACKLIST_MODE}" == "apply-run" ]]; then
        analyze_args+=(--run-blacklist-path "${RUN_BLACKLIST_PATH}")
    else
        analyze_args+=(--no-run-blacklist)
    fi
    if [[ "${MATCH_MODE}" == "tight" ]]; then
        analyze_args+=(--tight-match)
    fi
    if [[ "${PROBE_PT_GT15}" == "0" ]]; then
        analyze_args+=(--all-probe-pt)
    fi
    if [[ "${BX_ZERO}" == "1" ]]; then
        analyze_args+=(--bx-zero)
    fi

    rm -f -- "${output_part}"
    python3 "${ANALYZE_SCRIPT}" "${analyze_args[@]}" || return $?
    [[ -s "${output_part}" ]]
}

analyze_one_input() {
    local index="$1"
    local input_eos="$2"
    local input_local="${WORK_DIR}/input_${index}.root"
    local output_part="${WORK_DIR}/output_${index}.root"

    echo "[info] input[${index}]=${input_eos}"
    retry_command "copy input[${index}]" copy_input_once "${input_eos}" "${input_local}"
    retry_command "analyze input[${index}]" run_analysis_once "${input_local}" "${output_part}"
    OUTPUT_PARTS+=("${output_part}")
}

copy_single_part_once() {
    local input_part="$1"
    local output_local="$2"

    rm -f -- "${output_local}"
    cp -f "${input_part}" "${output_local}" || return $?
    [[ -s "${output_local}" ]]
}

merge_parts_once() {
    local output_local="$1"
    shift

    rm -f -- "${output_local}"
    hadd -T -fk101 -v 0 "${output_local}" "$@" || return $?
    [[ -s "${output_local}" ]]
}

merge_output_parts() {
    [[ ${#OUTPUT_PARTS[@]} -gt 0 ]] || die "no histogram shards were produced"
    if [[ ${#OUTPUT_PARTS[@]} -eq 1 ]]; then
        retry_command "copy single output part" copy_single_part_once "${OUTPUT_PARTS[0]}" "${OUTPUT_LOCAL}"
    else
        retry_command "merge output parts" merge_parts_once "${OUTPUT_LOCAL}" "${OUTPUT_PARTS[@]}"
    fi
}

create_output_dir_once() {
    local output_eos="$1"
    xrdfs "${EOS_XROOTD_ENDPOINT}" mkdir -p "$(dirname "${output_eos}")"
}

copy_output_once() {
    local output_local="$1"
    local output_eos="$2"
    xrdcp -f "${output_local}" "$(to_xrootd_url "${output_eos}")"
}

copy_output_to_eos() {
    retry_command "create EOS output directory" create_output_dir_once "${OUTPUT_EOS}"
    retry_command "copy output to EOS" copy_output_once "${OUTPUT_LOCAL}" "${OUTPUT_EOS}"
}

main() {
    validate_inputs
    split_input_list

    echo "[info] host=${HOSTNAME}"
    echo "[info] hist_output=${OUTPUT_EOS}"
    echo "[info] roll_blacklist=${ROLL_BLACKLIST_MODE}:${ROLL_BLACKLIST_PATH}"
    echo "[info] run_blacklist=${RUN_BLACKLIST_MODE}:${RUN_BLACKLIST_PATH}"
    echo "[info] match_mode=${MATCH_MODE}"
    echo "[info] probe_pt_gt15=${PROBE_PT_GT15}"
    echo "[info] bx_zero=${BX_ZERO}"
    echo "[info] inputs=${#INPUT_EOS_LIST[@]}"

    setup_cmssw_runtime
    for index in "${!INPUT_EOS_LIST[@]}"; do
        analyze_one_input "${index}" "${INPUT_EOS_LIST[$index]}"
    done
    merge_output_parts
    copy_output_to_eos
    echo "[done] ${OUTPUT_EOS}"
}

main "$@"
