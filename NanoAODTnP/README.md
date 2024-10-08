# RPCDPGAnalysis/NanoAODTnP

## Recipes
### Setup
```sh
CMSSW_VERSION=CMSSW_14_1_0
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
    inputFiles=/store/data/Run2024C/Muon1/AOD/PromptReco-v1/000/379/866/00000/319e19de-d5f8-41e5-b3da-241451966576.root \
    outputFile=output.root
```

### CRAB job
```sh
rpc-crab-submit.py \
    -p ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/test/muRPCTnPFlatTableProducer_cfg.py \
    -i ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/data/crab/Run3.json \
    -s T3_CH_CERNBOX \
    -u joshin \
    -n RPC-TnP-NanoAOD
```
