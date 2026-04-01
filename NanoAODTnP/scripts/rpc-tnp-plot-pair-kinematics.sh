WORK_DIR=${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP

INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2022.root
INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2023.root
INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2024.root
INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Run2025.root

#INPUT_2022=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v2.root
#INPUT_2023=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon0/Run2023C-PromptReco-v3.root
#INPUT_2024=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v2.root
#INPUT_2025=/eos/user/j/joshin/rpc/tnp-flatten-merged/v1/Muon1/Run2023C-PromptReco-v3.root

python3 ${WORK_DIR}/scripts/rpc-tnp-plot-pair-kinematics.py \
  -i ${INPUT_2022} \
  -i ${INPUT_2023} \
  -i ${INPUT_2024} \
  -i ${INPUT_2025} \
  -y 2022 \
  -y 2023 \
  -y 2024 \
  -y 2025 \
  --lumi 34.19 \
  --lumi 27.50 \
  --lumi 109.77 \
  --lumi 110.73 \
  -s 13.6 \
  -o ${WORK_DIR}/plots/Run3/pair \
  -l "Private Work" \
  --tree-name pair_tree \
  --branch dimuon_mass \
  --xmin 70 \
  --xmax 110 \
  --nbins 80 \
  --name rpc-tnp-pair-dimuon-mass \
  --ext png \
  --plot-probe-pt \
  --plot-probe-eta \
  --probe-tree-name pair_tree \
  --probe-pt-branch probe_pt \
  --probe-pt-xmin 0 \
  --probe-pt-xmax 100 \
  --probe-pt-nbins 50 \
  --probe-pt-name rpc-tnp-probe-pt \
  --probe-eta-branch probe_eta \
  --probe-eta-xmin -2.1 \
  --probe-eta-xmax 2.1 \
  --probe-eta-nbins 42 \
  --probe-eta-name rpc-tnp-probe-eta