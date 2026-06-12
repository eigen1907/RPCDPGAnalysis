#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

WORK_DIR="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP"
CERT_BASE="${WORK_DIR}/data/cert"
CRAB_BASE="${WORK_DIR}/logs/crab"
OUT_BASE="${WORK_DIR}/logs/lumi"
NORMTAG="/cvmfs/cms-bril.cern.ch/cms-lumi-pog/Normtags/normtag_BRIL.json"

for command in crab compareJSON.py brilcalc; do
    command -v "${command}" >/dev/null 2>&1 || { echo "[error] missing command: ${command}" >&2; exit 1; }
done
mkdir -p "${OUT_BASE}"

for year in Run2022 Run2023 Run2024 Run2025 Run2026; do
    case "${year}" in
        Run2022) cert_json="${CERT_BASE}/Cert_Collisions2022_355100_362760_Golden.json" ;;
        Run2023) cert_json="${CERT_BASE}/Cert_Collisions2023_366442_370790_Golden.json" ;;
        Run2024) cert_json="${CERT_BASE}/Cert_Collisions2024_378981_386951_Golden.json" ;;
        Run2025) cert_json="${CERT_BASE}/Cert_Collisions2025_391658_398903_Golden.json" ;;
        Run2026) cert_json="${CERT_BASE}/Cert_Collisions2026_401624_403493_Golden.json" ;;
    esac
    [[ -f "${cert_json}" ]] || { echo "[error] missing certification JSON: ${cert_json}" >&2; exit 1; }

    for task_dir in "${CRAB_BASE}"/crab_*"${year}"*; do
        task_name="$(basename "${task_dir}")"
        dataset_dir="${OUT_BASE}/${task_name#crab_muRPCTnPFlatTableProducer_cfg_}"
        results_dir="${task_dir}/results"
        mkdir -p "${dataset_dir}"

        crab report -d "${task_dir}" >/dev/null
        [[ -f "${results_dir}/processedLumis.json" ]] || continue
        cp "${results_dir}/processedLumis.json" "${dataset_dir}/processedLumis.json"
        compareJSON.py --and "${dataset_dir}/processedLumis.json" "${cert_json}" "${dataset_dir}/processedLumisGolden.json" >/dev/null
        brilcalc lumi -b "STABLE BEAMS" --normtag "${NORMTAG}" --output-style csv -u /fb \
            -i "${dataset_dir}/processedLumis.json" -o "${dataset_dir}/brilcalc_processed.csv"
        brilcalc lumi -b "STABLE BEAMS" --normtag "${NORMTAG}" --output-style csv -u /fb \
            -i "${dataset_dir}/processedLumisGolden.json" -o "${dataset_dir}/brilcalc_processed_golden.csv"
    done
done

"${WORK_DIR}/run/rpc-tnp-lumi-summary.sh"
