WORK_DIR="${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP"
OUT_DIR="${WORK_DIR}/logs/excluded_rolls"

mkdir -p "${OUT_DIR}"

#INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v2.root
#INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v3.root
#INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v2.root
#INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v3.root

INPUT_2022="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2022.root"
INPUT_2023="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2023.root"
INPUT_2024="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2024.root"
INPUT_2025="/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2025.root"

python3 "${WORK_DIR}/scripts/rpc-tnp-excluded-rolls.py" \
  -i "${INPUT_2022}" \
  -o "${OUT_DIR}/Run2022.json" \
  --tree-name trial_tree \
  --threshold 70.0

python3 "${WORK_DIR}/scripts/rpc-tnp-excluded-rolls.py" \
  -i "${INPUT_2023}" \
  -o "${OUT_DIR}/Run2023.json" \
  --tree-name trial_tree \
  --threshold 70.0

python3 "${WORK_DIR}/scripts/rpc-tnp-excluded-rolls.py" \
  -i "${INPUT_2024}" \
  -o "${OUT_DIR}/Run2024.json" \
  --tree-name trial_tree \
  --threshold 70.0

python3 "${WORK_DIR}/scripts/rpc-tnp-excluded-rolls.py" \
  -i "${INPUT_2025}" \
  -o "${OUT_DIR}/Run2025.json" \
  --tree-name trial_tree \
  --threshold 70.0