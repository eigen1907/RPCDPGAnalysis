from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
import uproot

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import RollEfficiencyResult, RollMeanResult  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import (  # type: ignore
    HISTOGRAM_NAMES,
    KINEMATIC_2D_HISTOGRAM_NAMES,
    CLS_ROLL_PROFILE,
    CLS_RUN_STATION_PROFILE,
    FIDUCIAL_SELECTION,
    MATCHED_SELECTION,
    PAIR_MASS_HISTOGRAM,
    STATION_NAMES,
    count_roll_name,
    count_2d_station_name,
    count_run_station_name,
    count_station_name,
    pair_kinematics_name,
    cls_profile_station_name,
    cls_profile_2d_station_name,
    profile_1d_station_name,
    roll_names,
    run_categories,
)
from RPCDPGAnalysis.NanoAODTnP.ReadRunMeta import integrated_lumi_edges  # type: ignore


@dataclass(frozen=True)
class Hist1DResult:
    counts: np.ndarray
    edges: np.ndarray
    n_values: int = 0
    mean: float = np.nan


@dataclass(frozen=True)
class Profile1DResult:
    value_sum: np.ndarray
    value_sumsq: np.ndarray
    counts: np.ndarray
    edges: np.ndarray


@dataclass(frozen=True)
class Profile2DResult:
    value_sum: np.ndarray
    value_sumsq: np.ndarray
    counts: np.ndarray
    x_edges: np.ndarray
    y_edges: np.ndarray


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
class Efficiency2DResult:
    total: np.ndarray
    passed: np.ndarray
    x_edges: np.ndarray
    y_edges: np.ndarray


@dataclass(frozen=True)
class CategoryEfficiencyResult:
    labels: np.ndarray
    total: np.ndarray
    passed: np.ndarray


@dataclass
class DenseHistogram:
    values: np.ndarray
    variances: np.ndarray
    edges: tuple[np.ndarray, ...]


def merge_category_profiles(results: Sequence[CategoryProfileResult]) -> CategoryProfileResult:
    return CategoryProfileResult(
        results[0].labels,
        np.sum([result.value_sum for result in results], axis=0),
        np.sum([result.value_sumsq for result in results], axis=0),
        np.sum([result.counts for result in results], axis=0),
    )


def merge_profile1d_results(results: Sequence[Profile1DResult]) -> Profile1DResult:
    return Profile1DResult(
        np.sum([result.value_sum for result in results], axis=0),
        np.sum([result.value_sumsq for result in results], axis=0),
        np.sum([result.counts for result in results], axis=0),
        results[0].edges,
    )


def merge_category_efficiencies(results: Sequence[CategoryEfficiencyResult]) -> CategoryEfficiencyResult:
    return CategoryEfficiencyResult(
        results[0].labels,
        np.sum([result.total for result in results], axis=0),
        np.sum([result.passed for result in results], axis=0),
    )


def merge_efficiency1d_results(results: Sequence[Efficiency1DResult]) -> Efficiency1DResult:
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
STATIONS = np.asarray(STATION_NAMES, dtype=str)
STATION_INDICES = {
    "all": np.arange(len(STATIONS)),
    "barrel": np.where(np.char.startswith(STATIONS, "RB"))[0],
    "endcap": np.where(np.char.startswith(STATIONS, "RE"))[0],
    "endcap-minus": np.where(np.char.startswith(STATIONS, "RE-"))[0],
    "endcap-plus": np.where(np.char.startswith(STATIONS, "RE+"))[0],
    **{name: np.asarray([idx]) for idx, name in enumerate(STATIONS)},
}


@lru_cache(maxsize=16)
def _load_paths(paths: tuple[str, ...]) -> dict[str, DenseHistogram]:
    merged: dict[str, DenseHistogram] = {}
    optional_names = set(KINEMATIC_2D_HISTOGRAM_NAMES)
    expected_optional_names: set[str] | None = None
    for input_path in map(Path, paths):
        with uproot.open(input_path) as root_file:
            available_optional_names = {name for name in optional_names if name in root_file}
            if expected_optional_names is None:
                expected_optional_names = available_optional_names
            elif available_optional_names != expected_optional_names:
                raise RuntimeError("Cannot merge legacy and current histogram schemas")
            for name in HISTOGRAM_NAMES:
                if name not in root_file:
                    if name in optional_names:
                        continue
                    raise RuntimeError(f"Missing histogram {name} in {input_path}")
                source = root_file[name]
                values = np.asarray(source.values(flow=False), dtype=np.float64)
                source_variances = source.variances(flow=False)
                variances = np.zeros_like(values) if source_variances is None else np.asarray(source_variances, dtype=np.float64)
                edges = tuple(np.asarray(axis.edges(flow=False), dtype=np.float64) for axis in source.axes)
                if name not in merged:
                    merged[name] = DenseHistogram(values.copy(), variances.copy(), edges)
                else:
                    if len(edges) != len(merged[name].edges) or any(
                        len(each) != len(reference) or not np.allclose(each, reference)
                        for each, reference in zip(edges, merged[name].edges)
                    ):
                        raise RuntimeError(f"Cannot merge histogram {name} with different axis binning")
                    merged[name].values += values
                    merged[name].variances += variances
    return merged


def load_histograms(spec) -> dict[str, DenseHistogram]:
    print(f"[info] loading histograms: Run{spec.year} files={len(spec.input_paths)}", flush=True)
    return _load_paths(tuple(str(path) for path in spec.input_paths))


def _contents(histogram: DenseHistogram, variance: bool = False) -> np.ndarray:
    return histogram.variances if variance else histogram.values


def _edges(histogram: DenseHistogram, axis: int = 0) -> np.ndarray:
    return histogram.edges[axis]


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


def _count1d(counts: np.ndarray, source_edges: np.ndarray, target_edges: np.ndarray) -> Hist1DResult:
    return _hist1d_result(_rebin_counts(counts, source_edges, target_edges), target_edges)


def _count_by_station(histograms: dict[str, DenseHistogram], selection: str, branch: str) -> np.ndarray:
    return _contents(histograms[count_station_name(selection, branch)])


def _count_by_group(histograms: dict[str, DenseHistogram], selection: str, branch: str, group: str) -> np.ndarray:
    return np.sum(_count_by_station(histograms, selection, branch)[:, STATION_INDICES[group]], axis=1)


def _profile_by_group(histograms: dict[str, DenseHistogram], branch: str, group: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = STATION_INDICES[group]
    profile = histograms[cls_profile_station_name(branch)]
    counts = histograms[count_station_name(MATCHED_SELECTION, branch)]
    return (
        np.sum(_contents(profile)[:, indices], axis=1),
        np.sum(_contents(profile, variance=True)[:, indices], axis=1),
        np.sum(_contents(counts)[:, indices], axis=1),
    )


def _profile1d_by_group(histograms: dict[str, DenseHistogram], sample: str, branch: str, target_edges: np.ndarray, group: str) -> Profile1DResult:
    indices = STATION_INDICES[group]
    profile = histograms[profile_1d_station_name(sample, branch)]
    counts = histograms[count_station_name(MATCHED_SELECTION, branch)]
    source_edges = _edges(profile)
    return Profile1DResult(
        _rebin_counts(np.sum(_contents(profile)[:, indices], axis=1), source_edges, target_edges),
        _rebin_counts(np.sum(_contents(profile, variance=True)[:, indices], axis=1), source_edges, target_edges),
        _rebin_counts(np.sum(_contents(counts)[:, indices], axis=1), source_edges, target_edges),
        np.asarray(target_edges, dtype=np.float64),
    )


def _histogram_2d_by_group(histogram: DenseHistogram, group: str) -> np.ndarray:
    return np.sum(_contents(histogram)[:, :, STATION_INDICES[group]], axis=2)


def has_kinematic_2d_histograms(histograms: dict[str, DenseHistogram]) -> bool:
    return all(name in histograms for name in KINEMATIC_2D_HISTOGRAM_NAMES)


def load_efficiency_2d_results(histograms: dict[str, DenseHistogram], names: Sequence[str], group: str = "all") -> dict[str, Efficiency2DResult]:
    results = {}
    for name in names:
        total_histogram = histograms[count_2d_station_name(FIDUCIAL_SELECTION, name)]
        passed_histogram = histograms[count_2d_station_name(MATCHED_SELECTION, name)]
        results[name] = Efficiency2DResult(
            _histogram_2d_by_group(total_histogram, group),
            _histogram_2d_by_group(passed_histogram, group),
            _edges(total_histogram, 0),
            _edges(total_histogram, 1),
        )
    return results


def load_cls_2d_results(histograms: dict[str, DenseHistogram], names: Sequence[str], group: str = "all") -> dict[str, Profile2DResult]:
    results = {}
    for name in names:
        profile = histograms[cls_profile_2d_station_name(name)]
        counts = histograms[count_2d_station_name(MATCHED_SELECTION, name)]
        indices = STATION_INDICES[group]
        results[name] = Profile2DResult(
            np.sum(_contents(profile)[:, :, indices], axis=2),
            np.sum(_contents(profile, variance=True)[:, :, indices], axis=2),
            np.sum(_contents(counts)[:, :, indices], axis=2),
            _edges(profile, 0),
            _edges(profile, 1),
        )
    return results


def _count_by_roll(histograms: dict[str, DenseHistogram], selection: str, dtype=np.int64) -> np.ndarray:
    return _contents(histograms[count_roll_name(selection)]).astype(dtype, copy=False)


def _roll_mean_result(histograms: dict[str, DenseHistogram]) -> RollMeanResult:
    sums = _contents(histograms[CLS_ROLL_PROFILE])
    counts = _count_by_roll(histograms, MATCHED_SELECTION, np.int64)
    means = np.divide(sums, counts, out=np.full(len(counts), np.nan, dtype=np.float64), where=counts > 0)
    return RollMeanResult(
        dict(zip(ROLL_NAMES.tolist(), means.tolist())),
        dict(zip(ROLL_NAMES.tolist(), counts.astype(int).tolist())),
    )


def _roll_efficiency_result(histograms: dict[str, DenseHistogram]) -> RollEfficiencyResult:
    total = _count_by_roll(histograms, FIDUCIAL_SELECTION, np.int64)
    passed = _count_by_roll(histograms, MATCHED_SELECTION, np.int64)
    efficiency = np.divide(100.0 * passed, total, out=np.full(len(total), np.nan), where=total > 0)
    efficiency_valid = total > 0
    barrel_eff = ROLL_REGION_MASKS["barrel"] & efficiency_valid
    endcap_eff = ROLL_REGION_MASKS["endcap"] & efficiency_valid
    return RollEfficiencyResult(
        total_by_roll=dict(zip(ROLL_NAMES.tolist(), total.astype(int).tolist())),
        passed_by_roll=dict(zip(ROLL_NAMES.tolist(), passed.astype(int).tolist())),
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
    indices = STATION_INDICES[key]
    profile = histograms[CLS_RUN_STATION_PROFILE]
    counts = histograms[count_run_station_name(MATCHED_SELECTION)]
    sums = np.sum(_contents(profile)[:, indices], axis=1)
    sumsqs = np.sum(_contents(profile, variance=True)[:, indices], axis=1)
    count_values = np.sum(_contents(counts)[:, indices], axis=1)
    selected = (count_values != 0) | (sums != 0) | (sumsqs != 0)
    return RUNS[selected], sums[selected], sumsqs[selected], count_values[selected]


def _time_efficiency_arrays(histograms: dict[str, DenseHistogram], key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = STATION_INDICES[key]
    total = np.sum(_contents(histograms[count_run_station_name(FIDUCIAL_SELECTION)])[:, indices], axis=1)
    passed = np.sum(_contents(histograms[count_run_station_name(MATCHED_SELECTION)])[:, indices], axis=1)
    selected = (total != 0) | (passed != 0)
    return RUNS[selected], total[selected], passed[selected]


def _time_profiles(histograms: dict[str, DenseHistogram], run_meta, keys: Sequence[str]):
    all_time_bin_timestamps = np.unique(np.asarray(run_meta.time_bin_timestamps, dtype="datetime64[s]"))
    edges = integrated_lumi_edges(run_meta)
    by_time = {}
    integrated = {}
    for key in keys:
        runs, sums, sumsqs, counts = _time_profile_arrays(histograms, key)
        by_time[key] = _category_profile(run_meta.lookup_time_bin_timestamps(runs), sums, sumsqs, counts, all_time_bin_timestamps)
        integrated[key] = _profile_by_edges(run_meta.lookup_integrated_lumis(runs), sums, sumsqs, counts, edges)
    return by_time, integrated


def _time_efficiencies(histograms: dict[str, DenseHistogram], run_meta, keys: Sequence[str]):
    all_time_bin_timestamps = np.unique(np.asarray(run_meta.time_bin_timestamps, dtype="datetime64[s]"))
    edges = integrated_lumi_edges(run_meta)
    by_time = {}
    integrated = {}
    for key in keys:
        runs, total, passed = _time_efficiency_arrays(histograms, key)
        by_time[key] = _category_efficiency(run_meta.lookup_time_bin_timestamps(runs), total, passed, all_time_bin_timestamps)
        integrated[key] = _efficiency_by_edges(run_meta.lookup_integrated_lumis(runs), total, passed, edges)
    return by_time, integrated


def load_pair_results(histograms: dict[str, DenseHistogram], plots):
    pair_mass = histograms[PAIR_MASS_HISTOGRAM]
    probe_histogram = histograms[pair_kinematics_name("probe")]
    tag_histogram = histograms[pair_kinematics_name("tag")]
    probe_2d = _contents(probe_histogram)
    tag_2d = _contents(tag_histogram)
    source_1d = {
        "pair_mass": (_contents(pair_mass), _edges(pair_mass)),
        "probe_pt": (np.sum(probe_2d, axis=1), _edges(probe_histogram, 0)),
        "probe_eta": (np.sum(probe_2d, axis=0), _edges(probe_histogram, 1)),
        "tag_pt": (np.sum(tag_2d, axis=1), _edges(tag_histogram, 0)),
        "tag_eta": (np.sum(tag_2d, axis=0), _edges(tag_histogram, 1)),
    }
    return {plot["name"]: _count1d(*source_1d[plot["branch"]], plot["edges"]) for plot in plots}


def load_probe_result(histograms: dict[str, DenseHistogram], plots, delta_pt_edges, delta_p_edges, profile_groups: Sequence[str]):
    return {
        "hists": {
            plot["name"]: _count1d(
                _count_by_group(histograms, FIDUCIAL_SELECTION, plot["branch"], plot["region"]),
                _edges(histograms[count_station_name(FIDUCIAL_SELECTION, plot["branch"])]),
                plot["edges"],
            )
            for plot in plots
        },
        "delta_pt_profiles": {group: _profile1d_by_group(histograms, "delta_pt", "probe_pt", delta_pt_edges, group) for group in profile_groups},
        "delta_p_profiles": {group: _profile1d_by_group(histograms, "delta_p", "probe_p", delta_p_edges, group) for group in profile_groups},
    }


def load_rpc_results(histograms: dict[str, DenseHistogram], count_plots, mean_plots, run_meta, time_keys: Sequence[str]):
    selections = {"fiducial": FIDUCIAL_SELECTION, "match": MATCHED_SELECTION}
    count_results = {
        plot["name"]: _count1d(
            _count_by_group(histograms, selections[plot["selection"]], plot["branch"], plot["region"]),
            _edges(histograms[count_station_name(selections[plot["selection"]], plot["branch"])]),
            plot["edges"],
        )
        for plot in count_plots
    }
    mean_results = {}
    for plot in mean_plots:
        sums, sumsqs, counts = _profile_by_group(histograms, plot["x_branch"], plot["region"])
        source_edges = _edges(histograms[cls_profile_station_name(plot["x_branch"])])
        mean_results[plot["name"]] = Profile1DResult(_rebin_counts(sums, source_edges, plot["edges"]), _rebin_counts(sumsqs, source_edges, plot["edges"]), _rebin_counts(counts, source_edges, plot["edges"]), np.asarray(plot["edges"], dtype=np.float64))
    by_time, integrated = _time_profiles(histograms, run_meta, time_keys)
    return count_results, mean_results, _roll_mean_result(histograms), by_time, integrated


def load_efficiency_results(histograms: dict[str, DenseHistogram], plots_1d, run_meta, time_keys: Sequence[str]):
    results_1d = {
        plot["name"]: Efficiency1DResult(
            _rebin_counts(
                _count_by_group(histograms, FIDUCIAL_SELECTION, plot["branch"], plot["region"]),
                _edges(histograms[count_station_name(FIDUCIAL_SELECTION, plot["branch"])]),
                plot["edges"],
            ),
            _rebin_counts(
                _count_by_group(histograms, MATCHED_SELECTION, plot["branch"], plot["region"]),
                _edges(histograms[count_station_name(MATCHED_SELECTION, plot["branch"])]),
                plot["edges"],
            ),
            np.asarray(plot["edges"], dtype=np.float64),
        )
        for plot in plots_1d
    }
    by_time, integrated = _time_efficiencies(histograms, run_meta, time_keys)
    return results_1d, _roll_efficiency_result(histograms), by_time, integrated
