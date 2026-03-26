#!/usr/bin/env bash
set -euo pipefail

CRAB_BASE="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/logs/crab"
CERT_BASE="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/cert"
OUT_BASE="$(pwd)/lumi"

mkdir -p "${OUT_BASE}"

for year in Run2022 Run2023 Run2024 Run2025; do
  case "${year}" in
    Run2022) cert_json="${CERT_BASE}/Cert_Collisions2022_355100_362760_Golden.json" ;;
    Run2023) cert_json="${CERT_BASE}/Cert_Collisions2023_366442_370790_Golden.json" ;;
    Run2024) cert_json="${CERT_BASE}/Cert_Collisions2024_378981_386951_Golden.json" ;;
    Run2025) cert_json="${CERT_BASE}/Cert_Collisions2025_391658_398903_Golden.json" ;;
  esac

  for task_dir in "${CRAB_BASE}/${year}"/crab_*; do
    [[ -d "${task_dir}" ]] || continue

    task_name="$(basename "${task_dir}")"
    dataset_name="${task_name#crab_muRPCTnPFlatTableProducer_cfg_}"
    dataset_dir="${OUT_BASE}/${dataset_name}"
    mkdir -p "${dataset_dir}"

    results_dir="${task_dir}/results"

    crab report -d "${task_dir}" > /dev/null

    src_processed="${results_dir}/processedLumis.json"
    dst_processed="${dataset_dir}/processedLumis.json"
    dst_masked="${dataset_dir}/processedLumis_Golden.json"
    dst_csv="${dataset_dir}/brilcalc_processed_Golden.csv"

    [[ -f "${src_processed}" ]] || continue

    cp "${src_processed}" "${dst_processed}"
    compareJSON.py --and "${dst_processed}" "${cert_json}" "${dst_masked}" > /dev/null
    brilcalc lumi -u /fb -i "${dst_masked}" -o "${dst_csv}"

    echo "[INFO] wrote ${dataset_dir}"
  done
done