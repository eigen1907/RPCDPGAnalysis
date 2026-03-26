#!/bin/bash

INPUT_BASE="/eos/user/j/joshin/rpc/tnp-flat"
OUTPUT_BASE="/eos/user/j/joshin/rpc/tnp-flat-merged"
BATCH_SIZE=20

shopt -s nullglob
mkdir -p "$OUTPUT_BASE"

for primary_dir in "$INPUT_BASE"/*; do
    [ -d "$primary_dir" ] || continue

    primary=$(basename "$primary_dir")
    mkdir -p "$OUTPUT_BASE/$primary"

    for dataset_dir in "$primary_dir"/*; do
        [ -d "$dataset_dir" ] || continue

        dataset=$(basename "$dataset_dir")
        out_file="$OUTPUT_BASE/$primary/${dataset}.root"

        files=( "$dataset_dir"/*/*/output_*.root )

        if [ ${#files[@]} -eq 0 ]; then
            echo "[skip] no files for $primary/$dataset"
            continue
        fi

        echo "[dataset] $primary/$dataset : ${#files[@]} files"

        tmpdir=$(mktemp -d /tmp/${USER}_hadd_${primary}_${dataset}_XXXXXX)
        parts=()
        part_idx=0

        for ((i=0; i<${#files[@]}; i+=BATCH_SIZE)); do
            part_file="$tmpdir/part_${part_idx}.root"
            batch_files=( "${files[@]:i:BATCH_SIZE}" )

            echo "  [stage1] part_${part_idx} : ${#batch_files[@]} files"
            hadd -f "$part_file" "${batch_files[@]}"
            status=$?

            if [ $status -ne 0 ]; then
                echo "  [fail] stage1 failed for $primary/$dataset batch=$part_idx"
                echo "  [hint] problematic files:"
                printf '    %s\n' "${batch_files[@]}"
                exit 1
            fi

            parts+=( "$part_file" )
            ((part_idx++))
        done

        echo "  [stage2] final merge -> $out_file"
        hadd -f "$out_file" "${parts[@]}"
        status=$?

        if [ $status -ne 0 ]; then
            echo "  [fail] final merge failed for $primary/$dataset"
            echo "  [hint] part files are kept in: $tmpdir"
            exit 1
        fi

        rm -rf "$tmpdir"
        echo "  [done] $out_file"
    done
done