# RPCDumper

Simple tools to validate RPC Digi, RecHit, and Geometry outputs in CMSSW.

## Setup

```bash
export SCRAM_ARCH=el9_amd64_gcc14
cmsrel CMSSW_16_1_0_pre4
cd CMSSW_16_1_0_pre4/src
cmsenv

git cms-init
git cms-merge-topic eigen1907:rpc-rechit_from-${CMSSW_VERSION}
git clone https://github.com/eigen1907/RPCDPGAnalysis.git

scram b -j8
mkdir ../relval
cd ../relval
```

## Workflow Check

```bash
runTheMatrix.py --what upgrade -n | grep rpcDevel
runTheMatrix.py --what upgrade -l 36034.62
```

## Simple Muon Gun Test

```bash
cmsDriver.py SingleMuFlatPt2To100_cfi -s GEN,SIM -n 100 --conditions auto:phase2_realistic_T35 --beamspot DBrealisticHLLHC --datatier GEN-SIM --eventcontent FEVTDEBUG --geometry ExtendedRun4D125 --era Phase2C22I13M9 --fileout file:step1.root --nThreads 4 > step1.log 2>&1

cmsDriver.py step2 -s DIGI:pdigi_valid,L1TrackTrigger,L1,L1P2GT,DIGI2RAW,HLT:@relvalRun4 --conditions auto:phase2_realistic_T35 --datatier GEN-SIM-DIGI-RAW -n -1 --eventcontent FEVTDEBUGHLT --geometry ExtendedRun4D125 --era Phase2C22I13M9,phase2_rpc_devel --filein file:step1.root --fileout file:step2.root --nThreads 4 > step2.log 2>&1

cmsDriver.py step3 -s RAW2DIGI,RECO,RECOSIM,PAT --conditions auto:phase2_realistic_T35 --datatier GEN-SIM-RECO -n -1 --eventcontent FEVTDEBUGHLT --geometry ExtendedRun4D125 --era Phase2C22I13M9,phase2_rpc_devel --filein file:step2.root --fileout file:step3.root --nThreads 4 > step3.log 2>&1
```

## Dumpers

```bash
cmsRun ${CMSSW_BASE}/src/RPCDPGAnalysis/RPCDumper/test/RPCDigiDumper_cfg.py inputFiles=file:step2.root outputFile=digis.root > RPCDigiDumper.log 2>&1
cmsRun ${CMSSW_BASE}/src/RPCDPGAnalysis/RPCDumper/test/RPCRecHitDumper_cfg.py inputFiles=file:step3.root outputFile=rechits.root > RPCRecHitDumper.log 2>&1
cmsRun ${CMSSW_BASE}/src/RPCDPGAnalysis/RPCDumper/test/RPCGeometryDumper_cfg.py > RPCGeometryDumper.log 2>&1
```

## Print and Plot

```bash
rpc-print-digi.py -i digis.root > digis.txt
rpc-print-rechit.py -i rechits.root > rechits.txt

rpc-plot-geo.py -g geometry.csv -o ./plots/geometry
rpc-plot-digi.py -i digis.root -g geometry.csv -o ./plots/digis
rpc-plot-rechit.py -i rechits.root -g geometry.csv -o ./plots/rechits
```

## Outputs

- digis.root: dumped Digi objects
- rechits.root: dumped RecHit objects
- geometry.csv: dumped RPC geometry
- digis.txt, rechits.txt: simple text summaries
- plots/: quick debug plots