# RPCDPGAnalysis/NanoAODTnP

## Recipes
### Setup
```sh
CMSSW_VERSION=CMSSW_16_1_0_pre1
cmsrel ${CMSSW_VERSION}
cd ./${CMSSW_VERSION}/src
cmsenv
git-cms-merge-topic eigen1907:rpc-tnp-nanoaod_from-${CMSSW_VERSION}
git clone https://github.com/eigen1907/RPCDPGAnalysis.git
scram b
```

### Test
```sh
cmsRun \
    ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/test/muRPCTnPFlatTableProducer_cfg.py \
    inputFiles=/store/data/Run2023D/Muon0/AOD/PromptReco-v1/000/370/357/00000/9a0455fb-1dae-4dc3-935d-d274bf697167.root \
    outputFile=output.root
```

### CRAB job
```sh
rpc-tnp-crab-submit.py \
    -p ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/test/muRPCTnPFlatTableProducer_cfg.py \
    -i ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/crab/Run2022.json \
    -s T3_CH_CERNBOX \
    -u joshin \
    -n rpc/tnp \
    --units-per-job 10
```

### Flatten Nanoaod
```sh
rpc-tnp-flatten.py \
    -i /eos/user/j/joshin/rpc/tnp/SingleMuon/Run2022C-27Jun2023-v1/260311_170958/0000/output_1.root \
    -c ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/cert/Cert_Collisions2022_355100_362760_Golden.json \
    -o output.root
```

### Condor job for flatten nanoaod
```sh
rpc-tnp-flatten-submit.py \
    -i /eos/user/j/joshin/rpc/tnp/SingleMuon/Run2022C-27Jun2023-v1 \
    -o /eos/user/j/joshin/rpc/tnp-flat/SingleMuon/Run2022C-27Jun2023-v1 \
    -s ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/scripts/rpc-tnp-flatten.py \
    -c ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/cert \
    --batch-name rpc-tnp-flatten
```


### Plot Efficiency vs Roll
```sh
rpc-tnp-plot-eff-detector.py \
    -i /eos/user/j/joshin/rpc/tnp-flat-merged/SingleMuon/Run2022C-27Jun2023-v1.root \
    -g ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/geometry/run3.csv \
    -s 13.6 \
    -y Run2022C \
    -o eff-detector
```

### Plot Muon Pair's Kinematics
```sh
rpc-tnp-plot-pair-kinematics.py \
    -i /eos/user/j/joshin/rpc/tnp-flat-merged/SingleMuon/Run2022C-27Jun2023-v1.root \
    -s 13.6 \
    -y Run2022C \
    -o pair-kinematics
```

### Plot Trials Basics
```sh
rpc-tnp-plot-trial-basics.py \
    -i /eos/user/j/joshin/rpc/tnp-flat-merged/SingleMuon/Run2022C-27Jun2023-v1.root \
    -s 13.6 \
    -y Run2022C \
    -o trial_plots
```
