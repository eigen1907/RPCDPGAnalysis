from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import glob
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
import uproot

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import RollEfficiencyResult, RollMeanResult  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import (  # type: ignore
    HISTOGRAM_NAMES,
    CLS_RUN_STATION_PROFILE,
    FIDUCIAL_SELECTION,
    MATCHED_SELECTION,
    PAIR_MASS_HISTOGRAM,
    PAIR_MASS_EDGES,
    PAIR_MUON_PT_EDGES,
    PROBE_ETA_EDGES,
    PROBE_ROLL_PROFILES,
    RPC_AXIS_EDGES,
    STATION_NAMES,
    TAG_ETA_EDGES,
    count_roll_name,
    count_run_station_name,
    count_station_name,
    pair_kinematics_name,
    cls_profile_station_name,
    profile_1d_name,
    profile_roll_name,
    roll_names,
    run_categories,
)
from RPCDPGAnalysis.NanoAODTnP.ReadRunMeta import integrated_lumi_edges  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import is_irpc_roll_name  # type: ignore


@dataclass(frozen=True)
class Hist1DResult:
    counts: np.ndarray
    edges: np.ndarray
    n_values: int = 0
    mean: float = np.nan


@dataclass(frozen=True)
class Hist2DResult:
    counts: np.ndarray
    x_edges: np.ndarray
    y_edges: np.ndarray


@dataclass(frozen=True)
class Profile1DResult:
    value_sum: np.ndarray
    value_sumsq: np.ndarray
    counts: np.ndarray
    edges: np.ndarray


@dataclass(frozen=True)
class CategoryProfileResult:
    labels: np.ndarray
    value_sum: np.ndarray
    value_sumsq: np.ndarray
    counts: np.ndarray


@dataclass(frozen=True)
class Efficiency1DResult:
    total: np.ndarray
    passed: np.ndarray
    edges: np.ndarray


@dataclass(frozen=True)
class CategoryEfficiencyResult:
    labels: np.ndarray
    total: np.ndarray
    passed: np.ndarray


@dataclass
class DenseHistogram:
    values: np.ndarray
    variances: np.ndarray


def _require_matching_arrays(results, attribute: str) -> None:
    reference = getattr(results[0], attribute)
    for result in results[1:]:
        value = getattr(result, attribute)
        if reference.shape != value.shape or not np.array_equal(reference, value):
            raise ValueError(f"Cannot merge results with different {attribute}")


def merge_category_profiles(results: Sequence[CategoryProfileResult]) -> CategoryProfileResult:
    if not results:
        raise ValueError("Cannot merge an empty profile result sequence")
    _require_matching_arrays(results, "labels")
    return CategoryProfileResult(
        results[0].labels,
        np.sum([result.value_sum for result in results], axis=0),
        np.sum([result.value_sumsq for result in results], axis=0),
        np.sum([result.counts for result in results], axis=0),
    )


def merge_profile1d_results(results: Sequence[Profile1DResult]) -> Profile1DResult:
    if not results:
        raise ValueError("Cannot merge an empty profile result sequence")
    _require_matching_arrays(results, "edges")
    return Profile1DResult(
        np.sum([result.value_sum for result in results], axis=0),
        np.sum([result.value_sumsq for result in results], axis=0),
        np.sum([result.counts for result in results], axis=0),
        results[0].edges,
    )


def merge_category_efficiencies(results: Sequence[CategoryEfficiencyResult]) -> CategoryEfficiencyResult:
    if not results:
        raise ValueError("Cannot merge an empty efficiency result sequence")
    _require_matching_arrays(results, "labels")
    return CategoryEfficiencyResult(
        results[0].labels,
        np.sum([result.total for result in results], axis=0),
        np.sum([result.passed for result in results], axis=0),
    )


def merge_efficiency1d_results(results: Sequence[Efficiency1DResult]) -> Efficiency1DResult:
    if not results:
        raise ValueError("Cannot merge an empty efficiency result sequence")
    _require_matching_arrays(results, "edges")
    return Efficiency1DResult(
        np.sum([result.total for result in results], axis=0),
        np.sum([result.passed for result in results], axis=0),
        results[0].edges,
    )


ROLL_NAMES = np.asarray(roll_names(), dtype=str)
RUNS = np.asarray(run_categories(), dtype=np.uint32)
ROLL_REGION_MASKS = {
    "barrel": np.char.startswith(ROLL_NAMES, "W"),
    "endcap": np.char.startswith(ROLL_NAMES, "RE"),
}
IRPC_ROLL_MASK = np.asarray([is_irpc_roll_name(name) for name in ROLL_NAMES], dtype=bool)
STATIONS = np.asarray(STATION_NAMES, dtype=str)


def _input_files(paths: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        text = str(path)
        if any(token in text for token in "*?[]"):
            files.extend(Path(each) for each in sorted(glob.glob(text)))
        elif path.is_dir():
            files.extend(sorted(each for each in path.rglob("*.root") if each.is_file()))
        else:
            files.append(path)
    if not files:
        raise FileNotFoundError(f"No ROOT files found in input paths: {paths}")
    return files


@lru_cache(maxsize=16)
def _load_paths(paths: tuple[str, ...]) -> dict[str, DenseHistogram]:
    merged: dict[str, DenseHistogram] = {}
    for input_path in _input_files(tuple(Path(path) for path in paths)):
        with uproot.open(input_path) as root_file:
            for name in HISTOGRAM_NAMES:
                source = root_file[name]
                values = np.asarray(source.values(flow=False), dtype=np.float64)
                source_variances = source.variances(flow=False)
                variances = np.zeros_like(values) if source_variances is None else np.asarray(source_variances, dtype=np.float64)
                if name not in merged:
                    merged[name] = DenseHistogram(values.copy(), variances.copy())
                else:
                    merged[name].values += values
                    merged[name].variances += variances
    return merged


def _contents(histogram: DenseHistogram, variance: bool = False) -> np.ndarray:
    return histogram.variances if variance else histogram.values


def _hist1d_result(counts: np.ndarray, edges: np.ndarray) -> Hist1DResult:
    counts = np.asarray(counts, dtype=np.float64)
    edges = np.asarray(edges, dtype=np.float64)
    centers = 0.5 * (edges[:-1] + edges[1:])
    n_values = int(np.sum(counts))
    mean = float(np.sum(counts * centers) / n_values) if n_values else np.nan
    return Hist1DResult(counts, edges, n_values, mean)


def _rebin_counts(counts: np.ndarray, source_edges: np.ndarray, target_edges: np.ndarray) -> np.ndarray:
    source_edges = np.asarray(source_edges, dtype=np.float64)
    target_edges = np.asarray(target_edges, dtype=np.float64)
    counts = np.asarray(counts, dtype=np.float64)
    if len(source_edges) == len(target_edges) and np.allclose(source_edges, target_edges):
        return counts
    centers = 0.5 * (source_edges[:-1] + source_edges[1:])
    bins = np.searchsorted(target_edges, centers, side="right") - 1
    selected = (bins >= 0) & (bins < len(target_edges) - 1)
    return np.bincount(bins[selected], weights=counts[selected], minlength=len(target_edges) - 1).astype(np.float64, copy=False)


def _rebin_counts2d(counts: np.ndarray, source_x_edges: np.ndarray, source_y_edges: np.ndarray, target_x_edges: np.ndarray, target_y_edges: np.ndarray) -> np.ndarray:
    counts = np.asarray(counts, dtype=np.float64)
    source_x_edges = np.asarray(source_x_edges, dtype=np.float64)
    source_y_edges = np.asarray(source_y_edges, dtype=np.float64)
    target_x_edges = np.asarray(target_x_edges, dtype=np.float64)
    target_y_edges = np.asarray(target_y_edges, dtype=np.float64)
    same_x = len(source_x_edges) == len(target_x_edges) and np.allclose(source_x_edges, target_x_edges)
    same_y = len(source_y_edges) == len(target_y_edges) and np.allclose(source_y_edges, target_y_edges)
    if same_x and same_y:
        return counts
    x_centers = 0.5 * (source_x_edges[:-1] + source_x_edges[1:])
    y_centers = 0.5 * (source_y_edges[:-1] + source_y_edges[1:])
    x_bins = np.searchsorted(target_x_edges, x_centers, side="right") - 1
    y_bins = np.searchsorted(target_y_edges, y_centers, side="right") - 1
    x_selected = (x_bins >= 0) & (x_bins < len(target_x_edges) - 1)
    y_selected = (y_bins >= 0) & (y_bins < len(target_y_edges) - 1)
    shape = (len(target_x_edges) - 1, len(target_y_edges) - 1)
    if not np.any(x_selected) or not np.any(y_selected):
        return np.zeros(shape, dtype=np.float64)
    flat_bins = x_bins[x_selected][:, None] * shape[1] + y_bins[y_selected][None, :]
    weights = counts[np.ix_(x_selected, y_selected)]
    return np.bincount(flat_bins.reshape(-1), weights=weights.reshape(-1), minlength=shape[0] * shape[1]).reshape(shape).astype(np.float64, copy=False)


def _count1d(counts: np.ndarray, source_edges: np.ndarray, target_edges: np.ndarray) -> Hist1DResult:
    return _hist1d_result(_rebin_counts(counts, source_edges, target_edges), target_edges)


def _count2d(counts: np.ndarray, source_x_edges: np.ndarray, source_y_edges: np.ndarray, target_x_edges: np.ndarray, target_y_edges: np.ndarray) -> Hist2DResult:
    rebinned = _rebin_counts2d(counts, source_x_edges, source_y_edges, target_x_edges, target_y_edges)
    return Hist2DResult(rebinned, np.asarray(target_x_edges), np.asarray(target_y_edges))


def _station_indices(key: str) -> np.ndarray:
    if key == "all":
        return np.arange(len(STATIONS))
    if key == "barrel":
        return np.where(np.char.startswith(STATIONS, "RB"))[0]
    if key == "endcap":
        return np.where(np.char.startswith(STATIONS, "RE"))[0]
    found = np.where(STATIONS == key)[0]
    if len(found) != 1:
        raise KeyError(f"Unknown station group: {key}")
    return found


def _count_by_station(histograms: dict[str, DenseHistogram], selection: str, branch: str) -> np.ndarray:
    return _contents(histograms[count_station_name(selection, branch)])


def _count_by_group(histograms: dict[str, DenseHistogram], selection: str, branch: str, group: str) -> np.ndarray:
    return np.sum(_count_by_station(histograms, selection, branch)[:, _station_indices(group)], axis=1)


def _profile_by_group(histograms: dict[str, DenseHistogram], branch: str, group: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = _station_indices(group)
    profile = histograms[cls_profile_station_name(branch)]
    counts = histograms[count_station_name(MATCHED_SELECTION, branch)]
    return (
        np.sum(_contents(profile)[:, indices], axis=1),
        np.sum(_contents(profile, variance=True)[:, indices], axis=1),
        np.sum(_contents(counts)[:, indices], axis=1),
    )


def _profile1d(histograms: dict[str, DenseHistogram], sample: str, branch: str, target_edges: np.ndarray) -> Profile1DResult:
    profile = histograms[profile_1d_name(sample, branch)]
    sums = _contents(profile)
    sumsqs = _contents(profile, variance=True)
    counts = np.sum(_count_by_station(histograms, MATCHED_SELECTION, branch), axis=1)
    source_edges = RPC_AXIS_EDGES[branch]
    return Profile1DResult(
        _rebin_counts(sums, source_edges, target_edges),
        _rebin_counts(sumsqs, source_edges, target_edges),
        _rebin_counts(counts, source_edges, target_edges),
        np.asarray(target_edges, dtype=np.float64),
    )


def _count_by_roll(histograms: dict[str, DenseHistogram], selection: str, dtype=np.int64) -> np.ndarray:
    return _contents(histograms[count_roll_name(selection)]).astype(dtype, copy=False)


def _mean_by_roll(histograms: dict[str, DenseHistogram], sample: str) -> tuple[np.ndarray, np.ndarray]:
    sums = _contents(histograms[profile_roll_name(sample)])
    counts = _count_by_roll(histograms, MATCHED_SELECTION, np.int64)
    means = np.divide(sums, counts, out=np.full(len(counts), np.nan, dtype=np.float64), where=counts > 0)
    return means, counts


def _roll_mean_result(histograms: dict[str, DenseHistogram], samples: Sequence[str]) -> RollMeanResult:
    values_and_counts = {sample: _mean_by_roll(histograms, sample) for sample in samples}
    return RollMeanResult(
        mean_by_roll={sample: pd.Series(values, index=ROLL_NAMES, dtype=np.float64) for sample, (values, _) in values_and_counts.items()},
        mean_count_by_roll={sample: pd.Series(counts, index=ROLL_NAMES, dtype=np.int64) for sample, (_, counts) in values_and_counts.items()},
    )


def _roll_efficiency_result(histograms: dict[str, DenseHistogram]) -> RollEfficiencyResult:
    total = _count_by_roll(histograms, FIDUCIAL_SELECTION, np.int64)
    passed = _count_by_roll(histograms, MATCHED_SELECTION, np.int64)
    efficiency = np.divide(100.0 * passed, total, out=np.full(len(total), np.nan), where=total > 0)
    efficiency_valid = total > 0
    barrel_eff = ROLL_REGION_MASKS["barrel"] & efficiency_valid
    endcap_eff = ROLL_REGION_MASKS["endcap"] & efficiency_valid & ~IRPC_ROLL_MASK
    return RollEfficiencyResult(
        total_by_roll=pd.Series(total, index=ROLL_NAMES, dtype=np.int64),
        passed_by_roll=pd.Series(passed, index=ROLL_NAMES, dtype=np.int64),
        efficiency_by_region={"barrel": efficiency[barrel_eff], "endcap": efficiency[endcap_eff]},
    )


def _category_indices(labels: np.ndarray, all_labels: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(labels, dtype=str)
    unique = np.unique(labels) if all_labels is None else np.asarray(all_labels, dtype=str)
    return unique, np.searchsorted(unique, labels)


def _category_profile(labels: np.ndarray, sums: np.ndarray, sumsqs: np.ndarray, counts: np.ndarray, all_labels: np.ndarray | None = None) -> CategoryProfileResult:
    unique, inverse = _category_indices(labels, all_labels)
    return CategoryProfileResult(unique, np.bincount(inverse, weights=sums, minlength=len(unique)).astype(np.float64), np.bincount(inverse, weights=sumsqs, minlength=len(unique)).astype(np.float64), np.bincount(inverse, weights=counts, minlength=len(unique)).astype(np.int64))


def _category_efficiency(labels: np.ndarray, total: np.ndarray, passed: np.ndarray, all_labels: np.ndarray | None = None) -> CategoryEfficiencyResult:
    unique, inverse = _category_indices(labels, all_labels)
    return CategoryEfficiencyResult(unique, np.bincount(inverse, weights=total, minlength=len(unique)).astype(np.int64), np.bincount(inverse, weights=passed, minlength=len(unique)).astype(np.int64))


def _profile_by_edges(x: np.ndarray, sums: np.ndarray, sumsqs: np.ndarray, counts: np.ndarray, edges: np.ndarray) -> Profile1DResult:
    bins = np.searchsorted(edges, x, side="right") - 1
    selected = np.isfinite(x) & (bins >= 0) & (bins < len(edges) - 1)
    return Profile1DResult(np.bincount(bins[selected], weights=sums[selected], minlength=len(edges) - 1).astype(np.float64), np.bincount(bins[selected], weights=sumsqs[selected], minlength=len(edges) - 1).astype(np.float64), np.bincount(bins[selected], weights=counts[selected], minlength=len(edges) - 1).astype(np.float64), np.asarray(edges, dtype=np.float64))


def _efficiency_by_edges(x: np.ndarray, total: np.ndarray, passed: np.ndarray, edges: np.ndarray) -> Efficiency1DResult:
    bins = np.searchsorted(edges, x, side="right") - 1
    selected = np.isfinite(x) & (bins >= 0) & (bins < len(edges) - 1)
    return Efficiency1DResult(np.bincount(bins[selected], weights=total[selected], minlength=len(edges) - 1).astype(np.float64), np.bincount(bins[selected], weights=passed[selected], minlength=len(edges) - 1).astype(np.float64), np.asarray(edges, dtype=np.float64))


def _time_profile_arrays(histograms: dict[str, DenseHistogram], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    indices = _station_indices(key)
    profile = histograms[CLS_RUN_STATION_PROFILE]
    counts = histograms[count_run_station_name(MATCHED_SELECTION)]
    sums = np.sum(_contents(profile)[:, indices], axis=1)
    sumsqs = np.sum(_contents(profile, variance=True)[:, indices], axis=1)
    count_values = np.sum(_contents(counts)[:, indices], axis=1)
    selected = (count_values != 0) | (sums != 0) | (sumsqs != 0)
    return RUNS[selected], sums[selected], sumsqs[selected], count_values[selected]


def _time_efficiency_arrays(histograms: dict[str, DenseHistogram], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = _station_indices(key)
    total = np.sum(_contents(histograms[count_run_station_name(FIDUCIAL_SELECTION)])[:, indices], axis=1)
    passed = np.sum(_contents(histograms[count_run_station_name(MATCHED_SELECTION)])[:, indices], axis=1)
    selected = (total != 0) | (passed != 0)
    return RUNS[selected], total[selected], passed[selected]


def _time_profiles(histograms: dict[str, DenseHistogram], run_meta, keys: Sequence[str]):
    all_months = np.unique(run_meta.months)
    edges = integrated_lumi_edges(run_meta)
    monthly = {}
    integrated = {}
    for key in keys:
        runs, sums, sumsqs, counts = _time_profile_arrays(histograms, key)
        monthly[key] = _category_profile(run_meta.lookup_months(runs), sums, sumsqs, counts, all_months)
        integrated[key] = _profile_by_edges(run_meta.lookup_integrated_lumis(runs), sums, sumsqs, counts, edges)
    return monthly, integrated


def _time_efficiencies(histograms: dict[str, DenseHistogram], run_meta, keys: Sequence[str]):
    all_months = np.unique(run_meta.months)
    edges = integrated_lumi_edges(run_meta)
    monthly = {}
    integrated = {}
    for key in keys:
        runs, total, passed = _time_efficiency_arrays(histograms, key)
        monthly[key] = _category_efficiency(run_meta.lookup_months(runs), total, passed, all_months)
        integrated[key] = _efficiency_by_edges(run_meta.lookup_integrated_lumis(runs), total, passed, edges)
    return monthly, integrated


def load_pair_results(spec, plots_1d, plots_2d):
    histograms = _load_paths(tuple(str(path) for path in spec.input_paths))
    probe_2d = _contents(histograms[pair_kinematics_name("probe")])
    tag_2d = _contents(histograms[pair_kinematics_name("tag")])
    source_1d = {
        "pair_mass": (_contents(histograms[PAIR_MASS_HISTOGRAM]), PAIR_MASS_EDGES),
        "probe_pt": (np.sum(probe_2d, axis=1), PAIR_MUON_PT_EDGES),
        "probe_eta": (np.sum(probe_2d, axis=0), PROBE_ETA_EDGES),
        "tag_pt": (np.sum(tag_2d, axis=1), PAIR_MUON_PT_EDGES),
        "tag_eta": (np.sum(tag_2d, axis=0), TAG_ETA_EDGES),
    }
    source_2d = {
        ("probe_pt", "probe_eta"): (probe_2d, PAIR_MUON_PT_EDGES, PROBE_ETA_EDGES),
        ("tag_pt", "tag_eta"): (tag_2d, PAIR_MUON_PT_EDGES, TAG_ETA_EDGES),
    }
    results_1d = {plot["name"]: _count1d(*source_1d[plot["branch"]], plot["edges"]) for plot in plots_1d}
    results_2d = {plot["name"]: _count2d(*source_2d[(plot["x_branch"], plot["y_branch"])], plot["x_edges"], plot["y_edges"]) for plot in plots_2d}
    return results_1d, results_2d


def load_probe_result(spec, plots, delta_pt_edges, delta_p_edges):
    histograms = _load_paths(tuple(str(path) for path in spec.input_paths))
    return {
        "hists": {plot["name"]: _count1d(np.sum(_count_by_station(histograms, FIDUCIAL_SELECTION, plot["branch"]), axis=1), RPC_AXIS_EDGES[plot["branch"]], plot["edges"]) for plot in plots},
        "delta_pt_profile": _profile1d(histograms, "delta_pt", "probe_pt", delta_pt_edges),
        "delta_p_profile": _profile1d(histograms, "delta_p", "probe_p", delta_p_edges),
        "roll_result": _roll_mean_result(histograms, PROBE_ROLL_PROFILES),
    }


def load_rpc_results(spec, count_plots, mean_plots, run_meta, monthly_keys: Sequence[str]):
    histograms = _load_paths(tuple(str(path) for path in spec.input_paths))
    selections = {"fiducial": FIDUCIAL_SELECTION, "match": MATCHED_SELECTION}
    count_results = {
        plot["name"]: _count1d(_count_by_group(histograms, selections[plot["selection"]], plot["branch"], plot["region"]), RPC_AXIS_EDGES[plot["branch"]], plot["edges"])
        for plot in count_plots
    }
    mean_results = {}
    for plot in mean_plots:
        sums, sumsqs, counts = _profile_by_group(histograms, plot["x_branch"], plot["region"])
        source_edges = RPC_AXIS_EDGES[plot["x_branch"]]
        mean_results[plot["name"]] = Profile1DResult(_rebin_counts(sums, source_edges, plot["edges"]), _rebin_counts(sumsqs, source_edges, plot["edges"]), _rebin_counts(counts, source_edges, plot["edges"]), np.asarray(plot["edges"], dtype=np.float64))
    fiducial = _count_by_roll(histograms, FIDUCIAL_SELECTION, np.int64)
    selected = _count_by_roll(histograms, MATCHED_SELECTION, np.int64)
    monthly, integrated = _time_profiles(histograms, run_meta, monthly_keys)
    return count_results, mean_results, {"fiducial": int(fiducial.sum()), "selected_fiducial": int(selected.sum())}, _roll_mean_result(histograms, ("cls", "bx")), monthly, integrated


def load_efficiency_results(spec, plots_1d, run_meta, monthly_keys: Sequence[str]):
    histograms = _load_paths(tuple(str(path) for path in spec.input_paths))
    results_1d = {
        plot["name"]: Efficiency1DResult(_rebin_counts(_count_by_group(histograms, FIDUCIAL_SELECTION, plot["branch"], plot["region"]), RPC_AXIS_EDGES[plot["branch"]], plot["edges"]), _rebin_counts(_count_by_group(histograms, MATCHED_SELECTION, plot["branch"], plot["region"]), RPC_AXIS_EDGES[plot["branch"]], plot["edges"]), np.asarray(plot["edges"], dtype=np.float64))
        for plot in plots_1d
    }
    monthly, integrated = _time_efficiencies(histograms, run_meta, monthly_keys)
    return results_1d, _roll_efficiency_result(histograms), monthly, integrated
