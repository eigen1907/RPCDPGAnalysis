from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import mean_and_error  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistIO import has_kinematic_2d_histograms, load_cls_2d_results, load_rpc_results, merge_category_profiles, merge_profile1d_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_cms_label, add_legend, annotate_count_scale, bin_centers, bin_half_widths, build_year_label, cms_year_label, combine_dataset_specs, count_scale, draw_binned_errorbar, draw_errorbar_series, new_figure, plot_group_label, plot_output_dir, poisson_yerr, save_binned_value_map, save_figure, save_roll_value_map, style_log_y_axis, variant_output_label, variant_output_target  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_names  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, RPC_BX_EDGES, RPC_CLS_EDGES, RPC_PV_EDGES, RPC_Q_OVER_P_EDGES, RPC_RHO_EDGES, STATION_NAMES, VALUE_MOMENTUM_EDGES, regular_edges  # type: ignore


PLOT_GROUPS = ("all", "barrel", "endcap", *STATION_NAMES)
CLS_EDGES = RPC_CLS_EDGES
BX_EDGES = RPC_BX_EDGES
PT_EDGES = VALUE_MOMENTUM_EDGES
P_EDGES = VALUE_MOMENTUM_EDGES
RESIDUAL_X_EDGES = regular_edges(-100.0, 100.0, 200)
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
EVENT_PLOTS = (
    ("rho", "rho", "rho", RPC_RHO_EDGES, r"$\rho$"),
    ("n_pv", "n-pv", "n_pv", RPC_PV_EDGES, "Number of Primary Vertices"),
    ("n_good_pv", "n-good-pv", "n_good_pv", RPC_PV_EDGES, "Number of Good Primary Vertices"),
    ("probe_q_over_p", "probe-q-over-p", "probe_q_over_p", RPC_Q_OVER_P_EDGES, r"Probe Muon $q/p$ [$\mathrm{GeV}^{-1}$]"),
)
KINEMATIC_2D_PLOTS = (
    ("probe_pt_eta", "mean-cls-probe-pt-eta", r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", r"Probe Muon $\eta$"),
    ("probe_at_rpc_pt_eta", "mean-cls-probe-at-rpc-pt-eta", r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]", r"Probe at RPC $\eta$"),
)


def abs_dxdz_edges(group: str) -> np.ndarray:
    return ABS_DXDZ_EDGES_BY_REGION["endcap"] if group == "endcap" or group.startswith("RE") else ABS_DXDZ_EDGES_BY_REGION["barrel"]


COUNT_PLOTS: list[dict] = []
MEAN_PLOTS: list[dict] = []
for group in PLOT_GROUPS:
    panel_label = plot_group_label(group)
    COUNT_PLOTS.append({"name": f"residual_x_{group}", "output": "rpc-residual-x", "variant": group, "branch": "residual_x", "edges": RESIDUAL_X_EDGES, "xlabel": r"Residual $x$ [cm]", "ylabel": "Probe Crossings", "region": group, "selection": "match", "log_scale": False, "panel_label": panel_label})
    COUNT_PLOTS.append({"name": f"cls_{group}", "output": "rpc-cls", "variant": group, "branch": "cls", "edges": CLS_EDGES, "xlabel": "Cluster Size", "ylabel": "Probe Crossings", "region": group, "selection": "match", "log_scale": False, "x_ticks": np.arange(1, 31, 2), "panel_label": panel_label})
    COUNT_PLOTS.append({"name": f"bx_{group}", "output": "rpc-bx", "variant": group, "branch": "bx", "edges": BX_EDGES, "xlabel": "Bunch Crossing", "ylabel": "Probe Crossings", "region": group, "selection": "match", "log_scale": True, "x_ticks": np.arange(-4, 5), "panel_label": panel_label})
    MEAN_PLOTS.append({
        "name": f"mean_cls_abs_dxdz_{group}",
        "output": "mean-cls-abs-dxdz",
        "variant": group,
        "x_branch": ABS_DXDZ_AXIS,
        "edges": abs_dxdz_edges(group),
        "xlabel": r"Projected local slope $|dx/dz|$",
        "ylabel": "Mean Cluster Size",
        "region": group,
        "panel_label": panel_label,
    })
    for name, output, branch, edges, xlabel in (*KINEMATIC_PLOTS, *EVENT_PLOTS):
        MEAN_PLOTS.append({"name": f"mean_cls_{name}_{group}", "output": f"mean-cls-{output}", "variant": group, "x_branch": branch, "edges": edges, "xlabel": xlabel, "ylabel": "Mean Cluster Size", "region": group, "panel_label": panel_label})
BARREL_STATION_SERIES = (
    ("RB1in", "RB1in"),
    ("RB1out", "RB1out"),
    ("RB2in", "RB2in"),
    ("RB2out", "RB2out"),
    ("RB3", "RB3"),
    ("RB4", "RB4"),
)

TIME_CLS_PLOTS = [
    {
        "output": "mean-cls-time",
        "variant": "rb",
        "series": BARREL_STATION_SERIES,
    },
    {
        "output": "mean-cls-time",
        "variant": "re-plus",
        "series": tuple((f"RE+{station}", f"RE+{station}") for station in range(1, 5)),
    },
    {
        "output": "mean-cls-time",
        "variant": "re-minus",
        "series": tuple((f"RE-{station}", f"RE-{station}") for station in range(1, 5)),
    },
    {
        "output": "mean-cls-time",
        "variant": "region",
        "series": (("barrel", "Barrel"), ("endcap", "Endcap")),
    },
]
TIME_CLS_KEYS = tuple(dict.fromkeys(
    key
    for plot in TIME_CLS_PLOTS
    for key, _ in plot["series"]
))
INTEGRATED_LUMI_CLS_PLOTS = [
    {**plot, "output": plot["output"].replace("mean-cls-time", "mean-cls-integ-lumi")}
    for plot in TIME_CLS_PLOTS
]

RPC_ROLL_MAP = {"name": "cls", "label": "Mean Cluster Size", "cmap": "viridis", "vmin": 0.5, "vmax": 4.5}


def draw_count_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
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
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_mean_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    ax.set_ylim(1.0, 3.0)
    for idx, (spec, profile) in enumerate(results):
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], build_year_label(spec.year, spec.lumi), xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def save_cls_2d(
    value_sum: np.ndarray,
    counts: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    output_name: str,
    group: str,
    xlabel: str,
    ylabel: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> Path:
    mean = np.divide(value_sum, counts, out=np.full_like(value_sum, np.nan, dtype=np.float64), where=counts > 0)
    return save_binned_value_map(mean, x_edges, y_edges, xlabel, ylabel, "Mean Cluster Size", output / output_name, group, label, com, spec.lumi, spec.year, ext, "viridis", 1.0, 3.0)


def draw_cls_2d_for_spec(histograms, spec, output: Path, label: str, com: float, ext: str) -> list[Path]:
    if not has_kinematic_2d_histograms(histograms):
        print(f"[warning] skipping mean CLS 2D plots for Run{spec.year}: reanalysis with the current histogram schema is required", flush=True)
        return []
    paths: list[Path] = []
    output_2d = plot_output_dir(output, "rpc-2d", spec.year)
    names = [plot[0] for plot in KINEMATIC_2D_PLOTS]
    for group in PLOT_GROUPS:
        results_2d = load_cls_2d_results(histograms, names, group)
        for name, output_name, xlabel, ylabel in KINEMATIC_2D_PLOTS:
            result = results_2d[name]
            paths.append(save_cls_2d(result.value_sum, result.counts, result.x_edges, result.y_edges, output_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
    return paths


def draw_run3_cls_2d(specs, histograms_by_spec, output: Path, label: str, com: float, ext: str) -> list[Path]:
    missing = [spec for spec in specs if not has_kinematic_2d_histograms(histograms_by_spec[spec])]
    if missing:
        years = ", ".join(f"Run{spec.year}" for spec in missing)
        print(f"[warning] skipping Run 3 mean CLS 2D plots: {years} need reanalysis with the current histogram schema", flush=True)
        return []

    spec = combine_dataset_specs(specs)
    if str(spec.year) != "3":
        return []

    paths: list[Path] = []
    output_2d = plot_output_dir(output, "rpc-2d", spec.year)
    names = [plot[0] for plot in KINEMATIC_2D_PLOTS]
    for group in PLOT_GROUPS:
        results_by_spec = [
            load_cls_2d_results(histograms_by_spec[each_spec], names, group)
            for each_spec in specs
        ]
        for name, output_name, xlabel, ylabel in KINEMATIC_2D_PLOTS:
            first = results_by_spec[0][name]
            value_sum = np.sum([results[name].value_sum for results in results_by_spec], axis=0)
            counts = np.sum([results[name].counts for results in results_by_spec], axis=0)
            paths.append(save_cls_2d(value_sum, counts, first.x_edges, first.y_edges, output_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
    return paths


def draw_time_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel("Time", fontsize=22, loc="center")
    ax.set_ylabel("Mean Cluster Size", fontsize=22)
    ax.set_ylim(1.0, 3.0)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if not np.any(mask):
            continue
        timestamps = np.asarray(profile.labels[mask], dtype="datetime64[s]")
        draw_errorbar_series(ax, timestamps, mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, yerr=yerr, marker_size=4)
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    add_legend(ax, loc="best")
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_integrated_lumi_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel(r"Integrated Luminosity [fb$^{-1}$]", fontsize=22)
    ax.set_ylabel("Mean Cluster Size", fontsize=22)
    ax.set_ylim(1.0, 3.0)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if not np.any(mask):
            continue
        draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, xerr=bin_half_widths(profile.edges)[mask], yerr=yerr, marker_size=5)
    add_legend(ax, loc="best")
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def plot_rpc(
    specs,
    histograms_by_spec,
    output: Path,
    geom,
    run_meta,
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
    draw_yearly_2d: bool = False,
    draw_roll_maps: bool = False,
) -> list[Path]:
    count_results = {}
    mean_results = {}
    roll_results = {}
    time_results = {}
    integrated_lumi_results = {}
    for spec in specs:
        count_results[spec], mean_results[spec], roll_results[spec], time_results[spec], integrated_lumi_results[spec] = load_rpc_results(histograms_by_spec[spec], COUNT_PLOTS, MEAN_PLOTS, run_meta, TIME_CLS_KEYS)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "rpc", specs)
    for plot in COUNT_PLOTS:
        paths.append(draw_count_plot([(spec, count_results[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for plot in MEAN_PLOTS:
        paths.append(draw_mean_plot([(spec, mean_results[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))

    paths.extend(draw_run3_cls_2d(specs, histograms_by_spec, output, label, com, ext))
    if draw_yearly_2d:
        for spec in specs:
            paths.extend(draw_cls_2d_for_spec(histograms_by_spec[spec], spec, output, label, com, ext))

    time_spec = combine_dataset_specs(specs)
    run3_time = {
        key: merge_category_profiles([time_results[spec][key] for spec in specs])
        for key in TIME_CLS_KEYS
    }
    run3_integrated_lumi = {
        key: merge_profile1d_results([integrated_lumi_results[spec][key] for spec in specs])
        for key in TIME_CLS_KEYS
    }
    time_output = plot_output_dir(output, "rpc", time_spec.year)
    integrated_lumi_output = plot_output_dir(output, "rpc", time_spec.year)
    for plot in TIME_CLS_PLOTS:
        paths.append(draw_time_cls(run3_time, plot, time_spec, time_output, label, com, ext))
    for plot in INTEGRATED_LUMI_CLS_PLOTS:
        paths.append(draw_integrated_lumi_cls(run3_integrated_lumi, plot, time_spec, integrated_lumi_output, label, com, ext))

    if draw_roll_maps:
        if geom is None:
            raise RuntimeError("RPC roll maps require RPC geometry")
        for spec in specs:
            roll_result = roll_results[spec]
            masked = roll_mask_names(spec.year)
            roll_map_spec = RollMapSpec(
                RPC_ROLL_MAP["name"],
                roll_result.mean_by_roll,
                RPC_ROLL_MAP["label"],
                RPC_ROLL_MAP["cmap"],
                RPC_ROLL_MAP["vmin"],
                RPC_ROLL_MAP["vmax"],
                excluded_rolls=masked,
            )
            for roll_map in build_roll_maps(geom, [roll_map_spec]):
                paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "rpc-map", spec.year), spec.year, label, com, spec.lumi, ext))
    return paths
