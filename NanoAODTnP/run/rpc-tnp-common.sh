#!/usr/bin/env bash

EOS_XROOTD_ENDPOINT="${EOS_XROOTD_ENDPOINT:-root://eosuser.cern.ch}"
RETRY_MAX_ATTEMPTS=5

die() {
    echo "[error] $*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

require_file() {
    [[ -f "$1" ]] || die "missing file: $1"
}

require_dir() {
    [[ -d "$1" ]] || die "missing directory: $1"
}

retry_command() {
    local label="$1"
    shift
    local attempt=1
    local delay=10
    local status=0

    while true; do
        if "$@"; then
            return 0
        fi
        status=$?

        if [[ "${attempt}" -ge "${RETRY_MAX_ATTEMPTS}" ]]; then
            echo "[error] ${label} failed after ${attempt} attempts (exit ${status})" >&2
            return "${status}"
        fi

        echo "[warn] ${label} failed on attempt ${attempt}/${RETRY_MAX_ATTEMPTS} (exit ${status}); retrying in ${delay}s" >&2
        sleep "${delay}"
        attempt=$((attempt + 1))
        delay=$((delay * 2))
        [[ "${delay}" -le 60 ]] || delay=60
    done
}

is_positive_int() {
    [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

is_non_negative_int() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

canonical_eos_path() {
    local path="$1"
    if [[ "${path}" =~ ^/eos/home-([^/]+)/([^/]+)(/.*)?$ ]]; then
        local tail="${BASH_REMATCH[3]:-}"
        echo "/eos/user/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}${tail}"
    else
        echo "${path}"
    fi
}

histogram_mode_suffix() {
    local tight_match="$1"
    local probe_pt_gt15="$2"
    local bx_zero="$3"
    local no_blacklist="$4"
    local no_run_blacklist="$5"
    local suffix=""

    [[ "${tight_match}" == "1" ]] && suffix="${suffix}-tight"
    [[ "${probe_pt_gt15}" == "0" ]] && suffix="${suffix}-all-probe-pt"
    [[ "${bx_zero}" == "1" ]] && suffix="${suffix}-bx-zero"
    [[ "${no_blacklist}" == "1" ]] && suffix="${suffix}-wo-blacklist"
    [[ "${no_run_blacklist}" == "1" ]] && suffix="${suffix}-wo-run-blacklist"
    printf '%s\n' "${suffix}"
}

annual_recorded_lumi() {
    local run_meta_path="$1"
    local year="$2"
    local run_blacklist_path="${3:-}"
    local short_year="${year:2:2}"

    if [[ -z "${run_blacklist_path}" ]]; then
        awk -F, -v short_year="${short_year}" '
            $1 !~ /^#/ && substr($2, 7, 2) == short_year { sum += $4 }
            END { printf "%.3f", sum }
        ' "${run_meta_path}"
        return
    fi

    awk -F, -v short_year="${short_year}" '
        FNR == NR {
            line = $0
            sub(/#.*/, "", line)
            gsub(/,/, " ", line)
            split(line, fields, /[[:space:]]+/)
            if (fields[1] ~ /^[0-9]+$/) excluded[fields[1]] = 1
            next
        }
        $1 !~ /^#/ && substr($2, 7, 2) == short_year {
            run = $1
            sub(/:.*/, "", run)
            if (!(run in excluded)) sum += $4
        }
        END { printf "%.3f", sum }
    ' "${run_blacklist_path}" "${run_meta_path}"
}

to_xrootd_url() {
    local path="$1"
    if [[ "${path}" == /eos/* ]]; then
        echo "${EOS_XROOTD_ENDPOINT}//${path#/}"
    else
        echo "${path}"
    fi
}

reset_work_dir() {
    local work_dir="$1"
    [[ -n "${work_dir}" && "${work_dir}" != "/" ]] || die "refusing to reset unsafe work directory: ${work_dir}"
    rm -rf -- "${work_dir}"
    mkdir -p "${work_dir}"
}
