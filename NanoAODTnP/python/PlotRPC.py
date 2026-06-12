from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import mean_and_error  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistIO import load_rpc_results, merge_category_profiles, merge_profile1d_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_cms_label, add_legend, annotate_count_scale, bin_centers, bin_half_widths, build_dataset_specs, build_year_label, cms_year_label, combine_dataset_specs, count_scale, dataset_specs_with_combined, draw_binned_errorbar, draw_errorbar_series, new_figure, plot_output_dir, poisson_yerr, save_figure, save_roll_value_map, style_log_y_axis  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_series  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, RPC_BX_EDGES, RPC_CLS_EDGES, regular_edges  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadRunMeta import read_run_meta  # type: ignore


REGION_TITLES = {"barrel": "RPC Barrel", "endcap": "RPC Endcap"}
CLS_EDGES = RPC_CLS_EDGES
BX_EDGES = RPC_BX_EDGES
PT_EDGES = regular_edges(0.0, 100.0, 50)
P_EDGES = regular_edges(0.0, 200.0, 100)
RESIDUAL_X_EDGES = regular_edges(-20.0, 20.0, 100)
ABS_DXDZ_EDGES_BY_REGION = {
    "barrel": regular_edges(0.0, 0.50, 25),
    "endcap": regular_edges(0.0, 0.10, 10),
}
KINEMATIC_PLOTS = (
    ("pt", "probe-pt", "probe_pt", PT_EDGES, r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]"),
    ("p", "probe-p", "probe_p", P_EDGES, r"Probe Muon $p$ [$\mathrm{GeV}$]"),
    ("at_rpc_pt", "probe-at-rpc-pt", "probe_at_rpc_pt", PT_EDGES, r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]"),
    ("at_rpc_p", "probe-at-rpc-p", "probe_at_rpc_p", P_EDGES, r"Probe at RPC $p$ [$\mathrm{GeV}$]"),
)

COUNT_PLOTS = [
    {"name": "residual_x", "output": "rpc-residual-x", "branch": "residual_x", "edges": RESIDUAL_X_EDGES, "xlabel": r"Residual $x$ [cm]", "ylabel": "Probe Crossings", "region": "all", "selection": "fiducial", "log_scale": False},
]
MEAN_PLOTS: list[dict] = []
for region in ("barrel", "endcap"):
    COUNT_PLOTS.append({"name": f"cls_{region}", "output": f"rpc-cls-{region}", "branch": "cls", "edges": CLS_EDGES, "xlabel": "Cluster Size", "ylabel": "Probe Crossings", "region": region, "selection": "match", "log_scale": False, "x_ticks": np.arange(1, 11), "panel_label": REGION_TITLES[region]})
    COUNT_PLOTS.append({"name": f"bx_{region}", "output": f"rpc-bx-{region}", "branch": "bx", "edges": BX_EDGES, "xlabel": "Bunch Crossing", "ylabel": "Probe Crossings", "region": region, "selection": "match", "log_scale": True, "x_ticks": np.arange(-4, 5), "panel_label": REGION_TITLES[region]})
    MEAN_PLOTS.append({
        "name": f"mean_cls_abs_dxdz_{region}",
        "output": f"mean-cls-abs-dxdz-{region}",
        "x_branch": ABS_DXDZ_AXIS,
        "edges": ABS_DXDZ_EDGES_BY_REGION[region],
        "xlabel": r"Projected local slope $|dx/dz|$",
        "ylabel": "Mean Cluster Size",
        "region": region,
        "panel_label": REGION_TITLES[region],
    })
    for name, output, branch, edges, xlabel in KINEMATIC_PLOTS:
        MEAN_PLOTS.append({"name": f"mean_cls_{name}_{region}", "output": f"mean-cls-{output}-{region}", "x_branch": branch, "edges": edges, "xlabel": xlabel, "ylabel": "Mean Cluster Size", "region": region, "panel_label": REGION_TITLES[region]})
BARREL_STATION_SERIES = (
    ("RB1in", "RB1in"),
    ("RB1out", "RB1out"),
    ("RB2in", "RB2in"),
    ("RB2out", "RB2out"),
    ("RB3", "RB3"),
    ("RB4", "RB4"),
)

MONTHLY_CLS_PLOTS = [
    {
        "output": "mean-cls-month-rb",
        "series": BARREL_STATION_SERIES,
    },
    {
        "output": "mean-cls-month-re-plus",
        "series": tuple((f"RE+{station}", f"RE+{station}") for station in range(1, 5)),
    },
    {
        "output": "mean-cls-month-re-minus",
        "series": tuple((f"RE-{station}", f"RE-{station}") for station in range(1, 5)),
    },
    {
        "output": "mean-cls-month-region",
        "series": (("barrel", "Barrel"), ("endcap", "Endcap")),
    },
]
MONTHLY_CLS_KEYS = tuple(dict.fromkeys(
    key
    for plot in MONTHLY_CLS_PLOTS
    for key, _ in plot["series"]
))
INTEGRATED_LUMI_CLS_PLOTS = [
    {**plot, "output": plot["output"].replace("mean-cls-month-", "mean-cls-integ-lumi-")}
    for plot in MONTHLY_CLS_PLOTS
]

MIN_PROFILE_ENTRIES = 100.0
MIN_ROLL_ENTRIES = 100.0
RPC_ROLL_MAPS = [
    {"name": "cls", "mean": "cls", "label": "Mean Cluster Size", "cmap": "viridis", "vmin": 0.5, "vmax": 4.5},
]


def draw_count_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}", flush=True)
    fig, ax = new_figure(label, com)
    if "panel_label" in plot:
        ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    if "x_ticks" in plot:
        ax.set_xticks(plot["x_ticks"])
    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    if plot["log_scale"]:
        positive_counts: list[np.ndarray] = []
        for idx, (spec, result) in enumerate(results):
            draw_binned_errorbar(ax, result.counts, result.edges, color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], label=build_year_label(spec.year, spec.lumi), yerr=poisson_yerr(result.counts, log_scale=True), log_scale=True)
            positive = result.counts[result.counts > 0]
            if len(positive):
                positive_counts.append(positive)
        style_log_y_axis(ax, np.concatenate(positive_counts) if positive_counts else np.empty(0, dtype=np.float64))
    else:
        scale_exp, scale = count_scale(max_count)
        for idx, (spec, result) in enumerate(results):
            draw_binned_errorbar(ax, result.counts, result.edges, color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], label=build_year_label(spec.year, spec.lumi), scale=scale)
        if max_count > 0.0:
            ax.set_ylim(0.0, 1.35 * max_count / scale)
        annotate_count_scale(ax, scale_exp)
    add_legend(ax)
    return save_figure(fig, output, output_name, ext)


def draw_mean_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    for idx, (spec, profile) in enumerate(results):
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts, min_count=MIN_PROFILE_ENTRIES)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], build_year_label(spec.year, spec.lumi), xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    return save_figure(fig, output, output_name, ext)


def draw_monthly_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel("Month", fontsize=22)
    ax.set_ylabel("Mean Cluster Size", fontsize=22)
    month_labels = sorted({
        month
        for key, _ in plot["series"]
        for month in result_by_key[key].labels
    })
    month_positions = {month: idx for idx, month in enumerate(month_labels)}
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts, min_count=MIN_PROFILE_ENTRIES)
        if not np.any(mask):
            continue
        x = np.asarray([month_positions[month] for month in profile.labels[mask]], dtype=np.float64)
        draw_errorbar_series(ax, x, mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, yerr=yerr, marker_size=5)
    ax.set_xticks(np.arange(len(month_labels), dtype=np.float64))
    ax.set_xticklabels(month_labels, rotation=45, ha="right")
    add_legend(ax, loc="best")
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def draw_integrated_lumi_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel(r"Integrated Luminosity [fb$^{-1}$]", fontsize=22)
    ax.set_ylabel("Mean Cluster Size", fontsize=22)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts, min_count=MIN_PROFILE_ENTRIES)
        if not np.any(mask):
            continue
        draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, xerr=bin_half_widths(profile.edges)[mask], yerr=yerr, marker_size=5)
    add_legend(ax, loc="best")
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def plot_rpc(
    input_groups: Sequence[Sequence[Path]],
    years: Sequence[int],
    output: Path,
    lumis: Sequence[float],
    geom_path: Path,
    run_meta_paths: Sequence[Path | Sequence[Path]],
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
) -> list[Path]:
    specs = build_dataset_specs(input_groups, years, lumis)
    map_specs = dataset_specs_with_combined(specs)
    run_meta = read_run_meta(run_meta_paths)
    count_results = {}
    mean_results = {}
    cutflows = {}
    roll_results = {}
    monthly_results = {}
    integrated_lumi_results = {}
    for spec in map_specs:
        count_results[spec], mean_results[spec], cutflows[spec], roll_results[spec], monthly_results[spec], integrated_lumi_results[spec] = load_rpc_results(spec, COUNT_PLOTS, MEAN_PLOTS, run_meta, MONTHLY_CLS_KEYS)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "rpc", specs)
    for plot in COUNT_PLOTS:
        paths.append(draw_count_plot([(spec, count_results[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for plot in MEAN_PLOTS:
        paths.append(draw_mean_plot([(spec, mean_results[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))

    time_spec = combine_dataset_specs(specs)
    run3_monthly = {
        key: merge_category_profiles([monthly_results[spec][key] for spec in specs])
        for key in MONTHLY_CLS_KEYS
    }
    run3_integrated_lumi = {
        key: merge_profile1d_results([integrated_lumi_results[spec][key] for spec in specs])
        for key in MONTHLY_CLS_KEYS
    }
    monthly_output = plot_output_dir(output, "rpc", time_spec.year, "time/month")
    integrated_lumi_output = plot_output_dir(output, "rpc", time_spec.year, "time/integrated-lumi")
    for plot in MONTHLY_CLS_PLOTS:
        paths.append(draw_monthly_cls(run3_monthly, plot, time_spec, monthly_output, label, com, ext))
    for plot in INTEGRATED_LUMI_CLS_PLOTS:
        paths.append(draw_integrated_lumi_cls(run3_integrated_lumi, plot, time_spec, integrated_lumi_output, label, com, ext))

    geom = pd.read_csv(geom_path)
    for spec in map_specs:
        roll_result = roll_results[spec]
        masked = roll_mask_series(years if str(spec.year) == "3" else spec.year)
        roll_map_specs = [
            RollMapSpec(
                plot["name"],
                roll_result.mean_by_roll[plot["mean"]].where(roll_result.mean_count_by_roll[plot["mean"]] >= MIN_ROLL_ENTRIES),
                plot["label"],
                plot["cmap"],
                plot["vmin"],
                plot["vmax"],
                excluded_by_roll=masked,
            )
            for plot in RPC_ROLL_MAPS
        ]
        for roll_map in build_roll_maps(geom, roll_map_specs):
            paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "rpc", spec.year, "map"), spec.year, label, com, spec.lumi, ext))
    return paths
