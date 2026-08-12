# RPCDPGAnalysis/NanoAODTnP

## Workflow

The current workflow is based on additive histogram outputs:

1. Produce RPC TnP NanoAOD with CRAB or `cmsRun`.
2. Analyze each NanoAOD file with Condor. Each job writes one histogram ROOT shard.
3. Merge additive histogram ROOT shards by dataset.
4. Reproduce the legacy pair, probe, RPC, and efficiency plots from merged histograms.

Histogram shards are built with `hist` and written by `uproot` as additive ROOT `TH1D` and `TH2D` objects, so they remain directly mergeable with `hadd`. Pair counts use one mass histogram and two pt-versus-eta histograms. RPC distributions use dense variable-versus-station histograms with 14 compact station categories: `RB1in`, `RB1out`, `RB2in`, `RB2out`, `RB3`, `RB4`, `RE-1`-`RE-4`, and `RE+1`-`RE+4`. Barrel, Endcap, and all-detector plots are derived by summing those station bins. Roll maps retain only roll counts and the mean-cluster-size weighted profile, while time trends use run-versus-station histograms. Weighted profile bin contents store value sums and variances store value sum-of-squares. Efficiency values are computed only after merging by dividing matched counts by fiducial counts.

The analyzer requires `--roll-blacklist-path` and excludes blacklisted rolls and every iRPC roll before filling any RPC histogram. iRPC rolls are identified by the `RE+3_R1_`, `RE-3_R1_`, `RE+4_R1_`, and `RE-4_R1_` prefixes. Pair histograms are unaffected because they do not represent individual RPC crossings. By default the matched histograms use the NanoAOD `is_matched` flag; add `--tight-match` to use `abs(residual_x) <= 20 cm` or `abs(pull_x) <= 4` instead. The blacklist, iRPC, and matching policies are not stored in the ROOT output; changing any of them requires rerunning and remerging the affected analysis shards. Excluded rolls remain zero-count bins on the fixed 1D roll axes, and roll maps continue to omit iRPC geometry.

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

Add `--tight-match` to the submit and merge commands to write/read
`tnp-hist-tight` shards. Combine it with `--no-blacklist` for
`tnp-hist-tight-wo-blacklist`.

Pair and RPC histograms use probes with `pT > 15 GeV` and `|eta| < 1.9` by
default. Pass `--all-probe-pt` to disable only the pT selection.

The `--bx-zero` selection requires matched RPC hits to have `BX == 0`. It is
applied only to the efficiency numerator; the fiducial denominator is
unchanged. Matched-hit distributions and profiles also use only `BX == 0`
hits.

Pass the same options to submit, merge, and plot commands. Their default paths
carry matching suffixes, for example:

```sh
bash run/rpc-tnp-analyze-submit.sh 2026 all
bash run/rpc-tnp-analyze-submit.sh 2026 all --all-probe-pt
bash run/rpc-tnp-merge-hist.sh 2026
bash run/rpc-tnp-merge-hist.sh 2026 --all-probe-pt
RUN3_YEARS=2026 bash run/rpc-tnp-plot.sh
RUN3_YEARS=2026 bash run/rpc-tnp-plot.sh --all-probe-pt
```

The default sequence uses `tnp-hist`, `tnp-hist-merged`, and `plots/default`.
The full-pT sequence uses `tnp-hist-all-probe-pt`,
`tnp-hist-all-probe-pt-merged`, and `plots/all-probe-pt`. `--bx-zero`,
`--no-blacklist`, `--no-run-blacklist`, and `--tight-match` remain composable
with either selection.

`resubmit` lists each dataset output directory once and submits only missing
histogram shards.

The Condor submission wrapper automatically selects the standard shared schedds
for an AFS checkout and the EosSubmit schedds for an EOS checkout.
Both wrappers accept one year from 2022 through 2026 and read the matching
`data/crab/RunYYYY.json`.


## Plot Merged Histograms

The plotting commands read merged histogram ROOT files directly and do not need flat trees. Pass a common output root such as `-o plots`. The campaign wrapper writes the regular blacklist-applied plots under `plots/default` and the no-blacklist plots under `plots/no-blacklist`; no-blacklist roll maps do not draw blacklist-excluded hatching. One-dimensional plots compare years in a Run 3 scope, and time trends combine all supplied years before drawing detector-region or station series. Time plots group consecutive complete LHC fills into approximately 1 fb^-1 blocks without crossing year boundaries. Each point uses the block's luminosity-weighted mean timestamp. Combined Run 3 efficiency and mean-cluster-size 2D plots are drawn by default. Per-year 2D plots, efficiency roll maps, and RPC mean-cluster-size roll maps are optional.

```text
plots/
|-- default/
|   |-- Run3/
|   |   |-- pair/
|   |   |   |-- 1d/                      # one curve per year
|   |   |   `-- 2d/
|   |   |       |-- probe-pt-eta.png
|   |   |       |-- probe-eta-phi.png
|   |   |       |-- tag-pt-eta.png
|   |   |       `-- tag-eta-phi.png
|   |   |-- probe/1d/
|   |   |-- rpc/
|   |   |   |-- 1d/                      # distributions and time/lumi trends
|   |   |   |   |-- rpc-cls/             # all/barrel/endcap/station variants
|   |   |   |   |-- mean-cls-probe-eta/
|   |   |   |   |-- mean-cls-probe-phi/
|   |   |   |   |-- mean-cls-run/
|   |   |   |   `-- mean-cls-elapsed-time/
|   |   |   `-- 2d/                      # Run 3 mean CLS vs probe eta/pT or eta/phi
|   |   |       |-- mean-cls-probe-pt-eta/
|   |   |       `-- mean-cls-probe-eta-phi/
|   |   |-- efficiency/
|   |   |   |-- 1d/
|   |   |   |   |-- eff-abs-dxdz/
|   |   |   |   |-- eff-probe-eta/
|   |   |   |   |-- eff-probe-phi/
|   |   |   |   |-- eff-run/
|   |   |   |   |-- eff-run-index/
|   |   |   |   `-- eff-elapsed-time/
|   |   |   `-- 2d/
|   |   |       |-- eff-probe-pt-eta/
|   |   |       |-- eff-probe-eta-phi/
|   |   |       |-- denom-probe-pt-eta/
|   |   |       |-- denom-probe-eta-phi/
|   |   |       |-- numer-probe-pt-eta/
|   |   |       `-- numer-probe-eta-phi/
|   `-- RunYYYY/
|       |-- efficiency/map/              # optional roll efficiency
|       |-- efficiency/2d/               # optional per-year efficiency 2D maps
|       |-- rpc/2d/                      # optional per-year mean CLS 2D maps
|       `-- rpc/map/                     # optional roll mean cluster size
`-- no-blacklist/
    |-- Run3/
    |   |-- pair/
    |   |   |-- 1d/
    |   |   `-- 2d/
    |   |-- probe/1d/
    |   |-- rpc/
    |   |   |-- 1d/
    |   |   `-- 2d/
    |   `-- efficiency/
    |       |-- 1d/
    |       `-- 2d/
    `-- RunYYYY/
```

Plot the complete configured Run 3 dataset:

```sh
bash run/rpc-tnp-plot.sh
```

Tight-match plots read `tnp-hist-tight-merged` and write
`plots/tight-match`. Add `--no-blacklist` to select
`tnp-hist-tight-wo-blacklist-merged` and `plots/tight-match-no-blacklist`:

```sh
bash run/rpc-tnp-plot.sh --tight-match
```

Selection-specific plots use the corresponding merged histogram paths:

```sh
bash run/rpc-tnp-plot.sh --all-probe-pt
bash run/rpc-tnp-plot.sh --all-probe-pt --no-blacklist
bash run/rpc-tnp-plot.sh --bx-zero
bash run/rpc-tnp-plot.sh --all-probe-pt --bx-zero
bash run/rpc-tnp-plot.sh --no-run-blacklist
```

The wrapper discovers merged ROOT files from `data/crab/RunYYYY.json`, calculates yearly luminosities from `data/lumi/run3.csv`, and defaults to years 2022 through 2026. Each year's ROOT histograms are loaded once and shared by the RPC, efficiency, pair, and probe plotters. By default it reads blacklist-applied merged histograms from `tnp-hist-merged`; pass `--no-blacklist` to read `tnp-hist-wo-blacklist-merged`. Each invocation writes only the selected campaign under `plots/` in the source checkout:

```sh
# Optional overrides
RUN3_YEARS="2022 2023 2024 2025" \
INPUT_BASE=/eos/user/j/joshin/rpc/tnp-hist-merged \
NO_BLACKLIST_INPUT_BASE=/eos/user/j/joshin/rpc/tnp-hist-wo-blacklist-merged \
PLOT_OUTPUT_BASE=/eos/user/j/joshin/rpc/tnp-plots \
PLOT_YEARLY_2D=1 \
PLOT_EFFICIENCY_MAPS=1 \
PLOT_ROLL_MAPS=1 \
bash run/rpc-tnp-plot.sh
```

```sh
python3 scripts/rpc-tnp-plot.py \
    -i /eos/user/j/joshin/rpc/tnp-hist-merged/Muon0/Run2026A-PromptReco-v1.root \
    -y 2026 \
    --lumi 1.0 \
    --run-meta-path data/lumi/run3.csv \
    -o plots
```

Multiple merged ROOT files for the same year can be passed after one `-i`. Repeat `-i`, `-y`, and `--lumi` to compare years and build full-period time trends. Add `--yearly-2d` for per-year 2D plots, `--efficiency-maps` for per-year efficiency roll maps, or `--roll-maps` for per-year RPC mean-cluster-size roll maps. Roll maps use `data/geometry/run3.csv` by default.

By default the analyzer writes `fiducial` and `fiducial_matched` count histograms and the matched profiles used by the standard pair, probe, RPC, and efficiency plots. Plot files omit a redundant matched suffix.

The RPC plots include matched `cls`, `bx`, and `residual_x` distributions for all RPCs, Barrel, Endcap, and each RB/RE station group. Multi-variant plot families are written as directories, for example `Run3/rpc/1d/rpc-cls/RB1in.png` and `Run3/efficiency/1d/eff-run-index/region.png`. Run 3 2D plots show efficiency and mean cluster size versus `(probe_eta, probe_pt)` and `(probe_eta, probe_phi)` for all RPCs, Barrel, Endcap, and each RB/RE station group. Probe eta and phi 1D efficiency and mean-cluster-size plots are projected from station-binned 2D histograms; the remaining RPC count/profile axes are plotted directly as 1D families. Pair 2D plots are drawn for probe/tag `(eta, pT)` and `(eta, phi)`.

Roll maps mark entries from `data/blacklist/roll/blackListYYYY.txt` with dark hatching and a `Masked` legend. Efficiency maps are produced with `--efficiency-maps`; RPC mean-cluster-size maps are produced with `--roll-maps`. Combined Run 3 maps are omitted.

## Luminosity Metadata

Later plotting uses `data/lumi/run3.csv`. The luminosity tools remain independent of the active analysis modules:

```sh
# Refresh per-dataset CRAB reports, golden lumi JSON files, and brilcalc CSV files.
bash run/rpc-tnp-lumi-calc.sh

# Build run3.csv from existing logs/lumi/*/processedLumisGolden.json files.
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

This writes histogram objects only to `hist-output.root` and applies the default
`pT > 15 GeV` probe selection. Add `--all-probe-pt` to disable it, or add
`--tight-match` or `--bx-zero` to use the corresponding selections.

Merge histogram shards with configurable `hadd` multiprocessing:

```sh
bash run/rpc-tnp-merge-hist.sh 2022
```

Condor analysis submission groups NanoAOD inputs into chunks of 10 files per job by default. Override this with `--files-per-job N` when running `run/rpc-tnp-analyze-submit.sh`. Each job analyzes its input files independently, merges the per-file histogram shards inside the job, and writes one chunk output such as `output_0_9.root` or `output_10_19.root`. `-j JOBS` controls `hadd` multiprocessing in the final dataset merge; the wrapper default is `-j 8`, and `-j 0` uses one process. Dense shards avoid the oversized sparse-object serialization failure.

The fixed compact dense schema writes additive objects with compression setting `101` (ZLIB level 1). Momentum axes are stored over 0--300 GeV with 1 GeV bins, eta axes use 0.05 bins, and phi axes use 128 bins across `[-pi, pi]`; plotting code rebins these dense inputs into the requested analysis binning. Wider residual and cluster-size axes minimize flow bins, while sentinel-prone unmatched `residual_x`, `bx`, and `cls` distributions are not stored. The schema includes `(eta, pT, station)` and `(eta, phi, station)` counts and CLS profiles for optional 2D maps.

## Layout

`scripts/` contains the reusable analysis and plotting commands. `run/` contains editable campaign wrappers, including histogram merging with `hadd`; shared shell helpers live in `run/rpc-tnp-common.sh`. The Condor payload is `run/rpc-tnp-analyze-run.sh`; it stages one or more NanoAOD inputs, merges their histogram shards inside the job, and writes one chunk histogram output.

`Analyze.py` orchestrates one input file. `TreeBuild.py` applies the golden JSON lumi block mask, reads the RPC TnP NanoAOD table, and builds the pair/RPC arrays needed by `HistBuild.py`. `HistBuild.py` uses `hist` and `uproot` to write the compact dense count and weighted-profile schema. Variable distributions and time trends are keyed by station; only map inputs retain a compact numeric roll axis. The derived `probe_p` value is computed as `probe_pt * cosh(probe_eta)`. `HistIO.py` reads merged ROOT histograms with `uproot`, sums multiple inputs in memory when needed, and derives regions from station sums. `RPCGeomServ.py` keeps the roll naming needed during analysis. Plotting remains in `PlotPair.py`, `PlotProbe.py`, `PlotRPC.py`, and `PlotEfficiency.py`. Luminosity refresh remains available through `run/rpc-tnp-lumi-calc.sh` and `run/rpc-tnp-lumi-summary.sh`.
