#!/usr/bin/env bash
set -euo pipefail

INPUT_BASE="/eos/user/j/joshin/rpc/tnp-flatten"
OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-flatten-merged"
ENDPOINT="root://eosuser.cern.ch"
TMP_BASE="${TMPDIR:-/tmp}/${USER}/rpc-tnp-hadd"

mkdir -p "${TMP_BASE}"

for version_dir in "${INPUT_BASE}"/v*; do
    [ -d "${version_dir}" ] || continue
    version="$(basename "${version_dir}")"

    for pd_dir in "${version_dir}"/Muon1; do
        [ -d "${pd_dir}" ] || continue
        pd="$(basename "${pd_dir}")"

        for dataset_dir in "${pd_dir}"/Run2025*; do
            [ -d "${dataset_dir}" ] || continue
            dataset="$(basename "${dataset_dir}")"

            latest_tag="$(find "${dataset_dir}" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
            [ -n "${latest_tag}" ] || continue

            echo "============================================================"
            echo "[dataset] ${version}/${pd}/${dataset}"
            echo "[tag]     $(basename "${latest_tag}")"

            work_dir="${TMP_BASE}/${version}/${pd}/${dataset}"
            rm -rf "${work_dir}"
            mkdir -p "${work_dir}/chunks"

            merged_chunks=()

            for chunk_dir in "${latest_tag}"/*; do
                [ -d "${chunk_dir}" ] || continue
                chunk="$(basename "${chunk_dir}")"

                shopt -s nullglob
                infiles=( "${chunk_dir}"/output_*.root )
                shopt -u nullglob

                if [ ${#infiles[@]} -eq 0 ]; then
                    echo "  [skip] ${chunk} : no input files"
                    continue
                fi

                chunk_out="${work_dir}/chunks/${chunk}.root"

                echo "  [merge-chunk] ${chunk} (${#infiles[@]} files)"
                hadd -fk -k "${chunk_out}" "${infiles[@]}"

                if [ ! -s "${chunk_out}" ]; then
                    echo "  [error] failed chunk merge: ${chunk_out}"
                    exit 1
                fi

                merged_chunks+=( "${chunk_out}" )
            done

            if [ ${#merged_chunks[@]} -eq 0 ]; then
                echo "  [skip] no merged chunk files"
                continue
            fi

            final_local="${work_dir}/${dataset}.root"

            echo "  [merge-dataset] ${dataset} (${#merged_chunks[@]} chunks)"
            hadd -fk -k "${final_local}" "${merged_chunks[@]}"

            if [ ! -s "${final_local}" ]; then
                echo "  [error] failed dataset merge: ${final_local}"
                exit 1
            fi

            final_eos_dir="${OUTPUT_BASE}/${version}/${pd}"
            final_eos_file="${final_eos_dir}/${dataset}.root"

            xrdfs "${ENDPOINT}" mkdir -p "${final_eos_dir}"
            xrdcp -f "${final_local}" "${ENDPOINT}//${final_eos_file}"

            echo "  [done] ${final_eos_file}"
        done
    done
done