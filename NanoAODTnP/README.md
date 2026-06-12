# RPCDPGAnalysis/NanoAODTnP

## Workflow

The current workflow is based on additive histogram outputs:

1. Produce RPC TnP NanoAOD with CRAB or `cmsRun`.
2. Analyze each NanoAOD file with Condor. Each job writes one histogram ROOT shard.
3. Merge additive histogram ROOT shards by dataset.
4. Reproduce the legacy pair, probe, RPC, and efficiency plots from merged histograms.

Histogram shards are built with `hist` and written by `uproot` as additive ROOT `TH1D` and `TH2D` objects, so they remain directly mergeable with `hadd`. Pair counts use one mass histogram and two pt-versus-eta histograms. RPC distributions use dense variable-versus-station histograms with 12 compact station categories: `RB1`-`RB4`, `RE-1`-`RE-4`, and `RE+1`-`RE+4`. Barrel, Endcap, and all-detector plots are derived by summing those station bins. Roll maps keep only the required 1D roll counts and weighted profile sums, while time trends use run-versus-station histograms. Weighted profile bin contents store value sums and variances store value sum-of-squares. Efficiency values are computed only after merging by dividing matched counts by fiducial counts. Flat ROOT shards preserving `pair_tree` and `rpc_tree` can still be written explicitly with `--tree-output`.

The analyzer requires `--roll-blacklist-path` and excludes blacklisted rolls before filling every RPC histogram. The blacklist is not stored in the ROOT output; changing it requires rerunning the affected analysis shards. Excluded rolls remain zero-count bins on the fixed 1D roll axes.

### Setup

```sh
CMSSW_VERSION=CMSSW_16_1_0_pre1
cmsrel ${CMSSW_VERSION}
cd ./${CMSSW_VERSION}/src
cmsenv
git-cms-merge-topic eigen1907:rpc-tnp-nanoaod_from-${CMSSW_VERSION}
git clone https://github.com/eigen1907/RPCDPGAnalysis.git
scram b -j 8
```

## Run A Campaign

```sh
cd ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP
```

Edit the campaign inputs before launching a new production:

- `data/crab/RunYYYY.json`
- `run/rpc-tnp-crab-submit.sh`
- `run/rpc-tnp-lumi-calc.sh`

Produce NanoAOD with CRAB when needed:

```sh
source /cvmfs/cms.cern.ch/common/crab-setup.sh
bash run/rpc-tnp-crab-submit.sh
```

Run the analysis workflow:

```sh
# 1. Submit one year of Condor analysis jobs.
bash run/rpc-tnp-analyze-submit.sh 2022 all

# 2. Resubmit missing outputs for that year.
bash run/rpc-tnp-analyze-submit.sh 2022 resubmit

# 3. Merge that year's histogram shards.
bash run/rpc-tnp-merge-hist.sh 2022
```

The Condor submission wrapper automatically selects the standard shared schedds
for an AFS checkout and the EosSubmit schedds for an EOS checkout.
Both wrappers accept one year from 2022 through 2026 and read the matching
`data/crab/RunYYYY.json`.


## Plot Merged Histograms

The plotting commands read merged histogram ROOT files directly and do not need flat trees. Pass a common output root such as `-o plots`. One-dimensional plots compare years in a Run 3 scope, and time trends combine all supplied years before drawing detector-region or station series. Maps and two-dimensional histograms are written for each year and for the combined Run 3 dataset.

```text
plots/
|-- Run3/
|   |-- pair/1d/                         # one curve per year
|   |-- probe/1d/
|   |-- rpc/1d/
|   |-- rpc/time/{month,integrated-lumi}/
|   |-- efficiency/1d/
|   |-- efficiency/time/{month,integrated-lumi}/
|   |-- pair/2d/
|   |-- probe/map/
|   |-- rpc/map/
|   `-- efficiency/map/
`-- RunYYYY/
    |-- pair/2d/
    |-- probe/map/
    |-- rpc/map/
    `-- efficiency/map/
```

Plot the complete configured Run 3 dataset:

```sh
bash run/rpc-tnp-plot-run3.sh
```

The four category wrappers can also be run independently. They discover merged ROOT files from `data/crab/RunYYYY.json`, calculate yearly luminosities from `data/lumi/run3.csv`, and default to years 2022 through 2026. Wrapper output defaults to `/eos/user/<initial>/<user>/rpc/tnp-plots`, outside the source checkout:

```sh
bash run/rpc-tnp-plot-rpc.sh

# Optional overrides
RUN3_YEARS="2022 2023 2024 2025" \
INPUT_BASE=/eos/user/j/joshin/rpc/tnp-hist-merged \
PLOT_OUTPUT_BASE=/eos/user/j/joshin/rpc/tnp-plots \
bash run/rpc-tnp-plot-efficiency.sh
```

```sh
# Pair plots need only merged histograms.
python3 scripts/rpc-tnp-plot-pair.py \
    -i /eos/user/j/joshin/rpc/tnp-hist-merged/Muon0/Run2026A-PromptReco-v1.root \
    -y 2026 \
    --lumi 1.0 \
    -o plots

# Probe maps need geometry metadata.
python3 scripts/rpc-tnp-plot-probe.py \
    -i /eos/user/j/joshin/rpc/tnp-hist-merged/Muon0/Run2026A-PromptReco-v1.root \
    -y 2026 \
    --lumi 1.0 \
    -g data/geometry/run3.csv \
    -o plots

# Efficiency and RPC summary plots also use run/luminosity metadata.
python3 scripts/rpc-tnp-plot-efficiency.py \
    -i /eos/user/j/joshin/rpc/tnp-hist-merged/Muon0/Run2026A-PromptReco-v1.root \
    -y 2026 \
    --lumi 1.0 \
    -g data/geometry/run3.csv \
    --run-meta-path data/lumi/run3.csv \
    -o plots

python3 scripts/rpc-tnp-plot-rpc.py \
    -i /eos/user/j/joshin/rpc/tnp-hist-merged/Muon0/Run2026A-PromptReco-v1.root \
    -y 2026 \
    --lumi 1.0 \
    -g data/geometry/run3.csv \
    --run-meta-path data/lumi/run3.csv \
    -o plots
```

Multiple merged ROOT files for the same year can be passed after one `-i`. Repeat `-i`, `-y`, and `--lumi` to compare years and build full-period time trends.

By default the analyzer writes `fiducial` and `fiducial_matched` count histograms and the matched profiles used by the standard pair, probe, RPC, and efficiency plots. Plot files omit a redundant matched suffix.

Roll maps mark entries from `data/blacklist/roll/blackListYYYY.txt` with dark hatching and a `Masked` legend. Run 3 maps use the union of the supplied yearly masks.

## Luminosity Metadata

Later plotting uses `data/lumi/run3.csv`. The luminosity tools remain independent of the active analysis modules:

```sh
# Refresh per-dataset CRAB reports, golden lumi JSON files, brilcalc CSV files, and run3.csv.
bash run/rpc-tnp-lumi-calc.sh

# Rebuild run3.csv from existing logs/lumi/*/processedLumisGolden.json files.
bash run/rpc-tnp-lumi-summary.sh
```

## Local Sanity Check

Analyze one NanoAOD file locally:

```sh
cmsRun \
    ${CMSSW_BASE}/src/RPCDPGAnalysis/NanoAODTnP/test/muRPCTnPFlatTableProducer_cfg.py \
    inputFiles=/store/data/Run2024D/Muon1/AOD/2024CDEReprocessing-v1/130000/a610b45b-2b36-4f67-b3f7-30d9a273558f.root \
    outputFile=output.root
```

```sh
python3 scripts/rpc-tnp-analyze.py \
    --input output.root \
    --cert data/cert/Cert_Collisions2024_378981_386951_Golden.json \
    --roll-blacklist-path data/blacklist/roll/blackList2024.txt \
    --output hist-output.root
```

This writes histogram objects only to `hist-output.root`.

Write a flat tree shard explicitly:

```sh
python3 scripts/rpc-tnp-analyze.py \
    --input output.root \
    --cert data/cert/Cert_Collisions2023_366442_370790_Golden.json \
    --roll-blacklist-path data/blacklist/roll/blackList2023.txt \
    --output hist-output.root \
    --tree-output tree-output.root
```


Merge histogram shards with configurable `hadd` multiprocessing:

```sh
bash run/rpc-tnp-merge-hist.sh 2022
```

`-j JOBS` controls `hadd` multiprocessing; the wrapper default is `-j 8`, and `-j 0` uses one process. Dense shards avoid the oversized sparse-object serialization failure.

The fixed compact dense schema writes 39 additive objects with compression setting `101` (ZLIB level 1). It includes matched `delta_pt = probe_pt - probe_at_rpc_pt` by `probe_pt` and `delta_p = probe_p - probe_at_rpc_p` by `probe_p` weighted profiles. Incidence-angle dependencies use fine-binned `abs(probe_at_rpc_dxdz)`, corresponding to `|tan(alpha)| = |dx/dz|`; optional flat trees retain the signed `probe_at_rpc_dxdz` slope and no derived angle branches. Mean cluster-size profiles retain the `probe_at_rpc_pt` dependency by station.

## Layout

`scripts/` contains the reusable analysis and plotting commands. `run/` contains editable campaign wrappers, including histogram merging with `hadd`. The Condor payload is `run/rpc-tnp-analyze-run.sh`; it stages one NanoAOD input and writes one histogram output.

`Analyze.py` orchestrates one input file. `TreeBuild.py` owns flat-tree schema, NanoAOD reading, derived branches, and optional flat ROOT output. `HistBuild.py` uses `hist` and `uproot` to write the compact dense count and weighted-profile schema. Variable distributions and time trends are keyed by station; only map inputs retain a compact numeric roll axis. The RPC variables include both `probe_p` and `probe_at_rpc_p`; optional flat trees store both as derived branches as well. They are computed as `probe_pt * cosh(probe_eta)` and `probe_at_rpc_pt * cosh(probe_at_rpc_eta)`, respectively. `HistIO.py` reads merged ROOT histograms with `uproot`, sums multiple inputs in memory when needed, and derives regions from station sums. `RPCGeomServ.py` keeps the roll naming needed during analysis. Plotting remains in `PlotPair.py`, `PlotProbe.py`, `PlotRPC.py`, and `PlotEfficiency.py`. Luminosity refresh remains available through `run/rpc-tnp-lumi-calc.sh` and `run/rpc-tnp-lumi-summary.sh`.
