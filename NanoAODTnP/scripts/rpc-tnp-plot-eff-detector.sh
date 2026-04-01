WORK_DIR=${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP

INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2022.root
INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2023.root
INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2024.root
INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2025.root

#INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v2.root
#INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v3.root
#INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v2.root
#INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v3.root


python3 ${WORK_DIR}/scripts/rpc-tnp-plot-eff-detector.py \
  -i ${INPUT_2022} \
  -g ${WORK_DIR}/data/geometry/run3.csv \
  -s 13.6 \
  -y Run2022 \
  -o ${WORK_DIR}/plots/Run2022 \
  -l "Private Work" \
  --lumi 34.19 \
  --hide-irpc \
  --exclude-eff-below 70

python3 ${WORK_DIR}/scripts/rpc-tnp-plot-eff-detector.py \
  -i ${INPUT_2023} \
  -g ${WORK_DIR}/data/geometry/run3.csv \
  -s 13.6 \
  -y Run2023 \
  -o ${WORK_DIR}/plots/Run2023 \
  -l "Private Work" \
  --lumi 27.50 \
  --hide-irpc \
  --exclude-eff-below 70

python3 ${WORK_DIR}/scripts/rpc-tnp-plot-eff-detector.py \
  -i ${INPUT_2024} \
  -g ${WORK_DIR}/data/geometry/run3.csv \
  -s 13.6 \
  -y Run2024 \
  -o ${WORK_DIR}/plots/Run2024 \
  -l "Private Work" \
  --lumi 109.77 \
  --hide-irpc \
  --exclude-eff-below 70

python3 ${WORK_DIR}/scripts/rpc-tnp-plot-eff-detector.py \
  -i ${INPUT_2025} \
  -g ${WORK_DIR}/data/geometry/run3.csv \
  -s 13.6 \
  -y Run2025 \
  -o ${WORK_DIR}/plots/Run2025 \
  -l "Private Work" \
  --lumi 110.73 \
  --hide-irpc \
  --exclude-eff-below 70
