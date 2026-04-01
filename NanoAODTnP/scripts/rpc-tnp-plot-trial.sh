WORK_DIR="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP"

#INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v2.root
#INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v3.root
#INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v2.root
#INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v3.root

INPUT_2022="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2022.root"
INPUT_2023="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2023.root"
INPUT_2024="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2024.root"
INPUT_2025="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2025.root"

EXCLUDE_2022="${WORK_DIR}/logs/excluded_rolls/Run2022.json"
EXCLUDE_2023="${WORK_DIR}/logs/excluded_rolls/Run2023.json"
EXCLUDE_2024="${WORK_DIR}/logs/excluded_rolls/Run2024.json"
EXCLUDE_2025="${WORK_DIR}/logs/excluded_rolls/Run2025.json"

python3 "${WORK_DIR}/scripts/rpc-tnp-plot-trial.py" \
  -i "${INPUT_2022}" \
  -i "${INPUT_2023}" \
  -i "${INPUT_2024}" \
  -i "${INPUT_2025}" \
  -y 2022 \
  -y 2023 \
  -y 2024 \
  -y 2025 \
  --lumi 34.7 \
  --lumi 27.9 \
  --lumi 109.8 \
  --lumi 110.7 \
  --exclude-json "${EXCLUDE_2022}" \
  --exclude-json "${EXCLUDE_2023}" \
  --exclude-json "${EXCLUDE_2024}" \
  --exclude-json "${EXCLUDE_2025}" \
  -s 13.6 \
  -o "${WORK_DIR}/plots/Run3/trial" \
  -l "Private Work" \
  --tree-name trial_tree \
  --eff-xmin 70 \
  --eff-xmax 100 \
  --eff-nbins 60 \
  --name-prefix rpc-tnp \
  --ext png