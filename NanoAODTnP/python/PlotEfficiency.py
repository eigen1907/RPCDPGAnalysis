from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D

from RPCDPGAnalysis.NanoAODTnP.HistIO import has_kinematic_2d_histograms, load_efficiency_2d_results, load_efficiency_results, merge_category_efficiencies, merge_efficiency1d_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.BuildUtils import clopper_pearson_efficiency_yerr, efficiency_series, efficiency_stats  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_cms_label, add_legend, bin_centers, bin_half_widths, build_year_label, cms_year_label, combine_dataset_specs, draw_errorbar_series, new_figure, plot_group_label, plot_output_dir, save_binned_value_map, save_figure, save_roll_value_map, variant_output_label, variant_output_target  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_names  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, RPC_PV_EDGES, RPC_Q_OVER_P_EDGES, RPC_RHO_EDGES, STATION_NAMES, VALUE_MOMENTUM_EDGES, regular_edges  # type: ignore


DEFAULT_EFF_THRESHOLD = 70.0
PLOT_GROUPS = ("all", "barrel", "endcap", *STATION_NAMES)
PT_EDGES = VALUE_MOMENTUM_EDGES
P_EDGES = VALUE_MOMENTUM_EDGES
ABS_DXDZ_EDGES_BY_REGION = {
    "barrel": regular_edges(0.0, 0.50, 25),
    "endcap": regular_edges(0.0, 0.12, 12),
}
EFFICIENCY_ROLL_EDGES = regular_edges(DEFAULT_EFF_THRESHOLD, 100.0, 60)
KINEMATIC_PLOTS = (
    ("probe_pt", "probe-pt", PT_EDGES, r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]"),
    ("probe_p", "probe-p", P_EDGES, r"Probe Muon $p$ [$\mathrm{GeV}$]"),
    ("probe_at_rpc_pt", "probe-at-rpc-pt", PT_EDGES, r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]"),
    ("probe_at_rpc_p", "probe-at-rpc-p", P_EDGES, r"Probe at RPC $p$ [$\mathrm{GeV}$]"),
)
EVENT_PLOTS = (
    ("rho", "rho", RPC_RHO_EDGES, r"$\rho$"),
    ("n_pv", "n-pv", RPC_PV_EDGES, "Number of Primary Vertices"),
    ("n_good_pv", "n-good-pv", RPC_PV_EDGES, "Number of Good Primary Vertices"),
    ("probe_q_over_p", "probe-q-over-p", RPC_Q_OVER_P_EDGES, r"Probe Muon $q/p$ [$\mathrm{GeV}^{-1}$]"),
)
KINEMATIC_2D_PLOTS = (
    ("probe_pt_eta", "eff-probe-pt-eta", r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", r"Probe Muon $\eta$"),
    ("probe_at_rpc_pt_eta", "eff-probe-at-rpc-pt-eta", r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]", r"Probe at RPC $\eta$"),
)


def abs_dxdz_edges(group: str) -> np.ndarray:
    return ABS_DXDZ_EDGES_BY_REGION["endcap"] if group == "endcap" or group.startswith("RE") else ABS_DXDZ_EDGES_BY_REGION["barrel"]


EFF_1D_PLOTS: list[dict] = []
for group in PLOT_GROUPS:
    EFF_1D_PLOTS.append({
        "name": f"eff_abs_dxdz_{group}",
        "output": "eff-abs-dxdz",
        "variant": group,
        "branch": ABS_DXDZ_AXIS,
        "edges": abs_dxdz_edges(group),
        "xlabel": r"Projected local slope $|dx/dz|$",
        "region": group,
        "panel_label": plot_group_label(group),
    })
    for branch, output, edges, xlabel in (*KINEMATIC_PLOTS, *EVENT_PLOTS):
        EFF_1D_PLOTS.append({
            "name": f"eff_{branch}_{group}",
            "output": f"eff-{output}",
            "variant": group,
            "branch": branch,
            "edges": edges,
            "xlabel": xlabel,
            "region": group,
            "panel_label": plot_group_label(group),
        })
EFFICIENCY_ROLL_MAP = {
    "name": "efficiency",
    "label": "Efficiency [%]",
    "cmap": "RdYlGn",
    "vmin": 0.0,
    "vmax": 100.0,
}

BARREL_STATION_SERIES = (
    ("RB1in", "RB1in"),
    ("RB1out", "RB1out"),
    ("RB2in", "RB2in"),
    ("RB2out", "RB2out"),
    ("RB3", "RB3"),
    ("RB4", "RB4"),
)

TIME_EFFICIENCY_PLOTS = [
    {
        "output": "eff-time",
        "variant": "rb",
        "series": BARREL_STATION_SERIES,
    },
    {
        "output": "eff-time",
        "variant": "re-plus",
        "series": tuple((f"RE+{station}", f"RE+{station}") for station in range(1, 5)),
    },
    {
        "output": "eff-time",
        "variant": "re-minus",
        "series": tuple((f"RE-{station}", f"RE-{station}") for station in range(1, 5)),
    },
    {
        "output": "eff-time",
        "variant": "region",
        "series": (("barrel", "Barrel"), ("endcap", "Endcap")),
    },
]

TIME_EFFICIENCY_KEYS = tuple(dict.fromkeys(
    key
    for plot in TIME_EFFICIENCY_PLOTS
    for key, _ in plot["series"]
))
INTEGRATED_LUMI_EFFICIENCY_PLOTS = [
    {**plot, "output": plot["output"].replace("eff-time", "eff-integ-lumi")}
    for plot in TIME_EFFICIENCY_PLOTS
]


def draw_efficiency_1d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    ax.set_ylim(0.0, 105.0)
    for idx, (spec, profile) in enumerate(results):
        mask, eff, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], eff, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], build_year_label(spec.year, spec.lumi), xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_time_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel("Time", fontsize=22, loc="center")
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_ylim(70.0, 100.0)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, efficiency, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if not np.any(mask):
            continue
        timestamps = np.asarray(profile.labels[mask], dtype="datetime64[s]")
        draw_errorbar_series(ax, timestamps, efficiency, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, yerr=yerr, marker_size=4)
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    add_legend(ax, loc="best")
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_integrated_lumi_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel(r"Integrated Luminosity [fb$^{-1}$]", fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_ylim(70.0, 100.0)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, efficiency, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if not np.any(mask):
            continue
        draw_errorbar_series(ax, bin_centers(profile.edges)[mask], efficiency, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, xerr=bin_half_widths(profile.edges)[mask], yerr=yerr, marker_size=5)
    add_legend(ax, loc="best")
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_nrolls_efficiency(results, region: str, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = "nrolls-eff"
    print(f"[info] plotting {variant_output_label(output_name, region)}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, plot_group_label(region), transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.text(0.96, 0.94, "Tag-and-Probe method", transform=ax.transAxes, ha="right", va="top", fontsize=22)
    ax.set_xlabel("Efficiency [%]", fontsize=22)
    ax.set_ylabel("Number of Rolls", fontsize=22)
    ax.set_xlim(DEFAULT_EFF_THRESHOLD, 100.0)
    legend_handles: list[Line2D] = [Line2D([], [], linestyle="none", color="none")]
    legend_labels: list[str] = [f"{'':<18}{('Mean (>%.0f%%)' % DEFAULT_EFF_THRESHOLD):>10}{('%% (<=%.0f%%)' % DEFAULT_EFF_THRESHOLD):>10}"]
    max_count = 0.0
    edges = EFFICIENCY_ROLL_EDGES
    for idx, (spec, roll_result) in enumerate(results):
        values = roll_result.efficiency_by_region[region]
        counts, _ = np.histogram(values[np.isfinite(values)], bins=edges)
        counts = counts.astype(np.float64, copy=False)
        max_count = max(max_count, float(np.max(counts)) if len(counts) else 0.0)
        color = DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]
        handle = ax.stairs(counts, edges, color=color, label=build_year_label(spec.year, spec.lumi))
        legend_handles.append(handle)
        mean_good, frac_bad = efficiency_stats(values, DEFAULT_EFF_THRESHOLD)
        legend_labels.append(f"{build_year_label(spec.year, spec.lumi):<18}{mean_good:>10.1f}{frac_bad:>10.1f}")
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.35 * max_count)
    ax.legend(legend_handles, legend_labels, loc="upper left", bbox_to_anchor=(0.02, 0.88), frameon=False, handlelength=1.8, handleheight=1.2, labelspacing=0.35, borderpad=0.2, prop=FontProperties(family=["DejaVu Sans Mono"], size=16))
    output_dir, file_name = variant_output_target(output, output_name, region)
    return save_figure(fig, output_dir, file_name, ext)


def save_efficiency_2d(
    total: np.ndarray,
    passed: np.ndarray,
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
    efficiency = np.divide(100.0 * passed, total, out=np.full_like(total, np.nan, dtype=np.float64), where=total > 0)
    return save_binned_value_map(efficiency, x_edges, y_edges, xlabel, ylabel, "RPC Efficiency [%]", output / output_name, group, label, com, spec.lumi, spec.year, ext, "RdYlGn", 70.0, 100.0)


def save_efficiency_2d_count(
    values: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    output_name: str,
    group: str,
    xlabel: str,
    ylabel: str,
    value_label: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> Path:
    finite = values[np.isfinite(values)]
    vmax = max(float(np.max(finite)) if len(finite) else 0.0, 1.0)
    return save_binned_value_map(values, x_edges, y_edges, xlabel, ylabel, value_label, output / output_name, group, label, com, spec.lumi, spec.year, ext, "viridis", 0.0, vmax)


def save_efficiency_2d_components(
    total: np.ndarray,
    passed: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    denominator_output: Path,
    numerator_output: Path,
    output_name: str,
    group: str,
    xlabel: str,
    ylabel: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> list[Path]:
    return [
        save_efficiency_2d_count(total, x_edges, y_edges, denominator_output, output_name, group, xlabel, ylabel, "Denominator", spec, label, com, ext),
        save_efficiency_2d_count(passed, x_edges, y_edges, numerator_output, output_name, group, xlabel, ylabel, "Numerator", spec, label, com, ext),
    ]


def draw_efficiency_2d_for_spec(histograms, spec, output: Path, label: str, com: float, ext: str) -> list[Path]:
    if not has_kinematic_2d_histograms(histograms):
        print(f"[warning] skipping efficiency 2D plots for Run{spec.year}: reanalysis with the current histogram schema is required", flush=True)
        return []
    paths: list[Path] = []
    output_2d = plot_output_dir(output, "efficiency-2d", spec.year)
    denominator_2d = plot_output_dir(output, "denominator-2d", spec.year)
    numerator_2d = plot_output_dir(output, "numerator-2d", spec.year)
    names = [plot[0] for plot in KINEMATIC_2D_PLOTS]
    for group in PLOT_GROUPS:
        results_2d = load_efficiency_2d_results(histograms, names, group)
        for name, output_name, xlabel, ylabel in KINEMATIC_2D_PLOTS:
            result = results_2d[name]
            paths.append(save_efficiency_2d(result.total, result.passed, result.x_edges, result.y_edges, output_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
            paths.extend(save_efficiency_2d_components(result.total, result.passed, result.x_edges, result.y_edges, denominator_2d, numerator_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
    return paths


def draw_run3_efficiency_2d(specs, histograms_by_spec, output: Path, label: str, com: float, ext: str) -> list[Path]:
    missing = [spec for spec in specs if not has_kinematic_2d_histograms(histograms_by_spec[spec])]
    if missing:
        years = ", ".join(f"Run{spec.year}" for spec in missing)
        print(f"[warning] skipping Run 3 efficiency 2D plots: {years} need reanalysis with the current histogram schema", flush=True)
        return []

    spec = combine_dataset_specs(specs)
    if str(spec.year) != "3":
        return []

    paths: list[Path] = []
    output_2d = plot_output_dir(output, "efficiency-2d", spec.year)
    denominator_2d = plot_output_dir(output, "denominator-2d", spec.year)
    numerator_2d = plot_output_dir(output, "numerator-2d", spec.year)
    names = [plot[0] for plot in KINEMATIC_2D_PLOTS]
    for group in PLOT_GROUPS:
        results_by_spec = [
            load_efficiency_2d_results(histograms_by_spec[each_spec], names, group)
            for each_spec in specs
        ]
        for name, output_name, xlabel, ylabel in KINEMATIC_2D_PLOTS:
            first = results_by_spec[0][name]
            total = np.sum([results[name].total for results in results_by_spec], axis=0)
            passed = np.sum([results[name].passed for results in results_by_spec], axis=0)
            paths.append(save_efficiency_2d(total, passed, first.x_edges, first.y_edges, output_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
            paths.extend(save_efficiency_2d_components(total, passed, first.x_edges, first.y_edges, denominator_2d, numerator_2d, output_name, group, xlabel, ylabel, spec, label, com, ext))
    return paths


def plot_efficiency(
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
    results_1d = {}
    roll_results = {}
    time_results = {}
    integrated_lumi_results = {}
    for spec in specs:
        results_1d[spec], roll_results[spec], time_results[spec], integrated_lumi_results[spec] = load_efficiency_results(histograms_by_spec[spec], EFF_1D_PLOTS, run_meta, TIME_EFFICIENCY_KEYS)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "efficiency", specs)
    for plot in EFF_1D_PLOTS:
        paths.append(draw_efficiency_1d([(spec, results_1d[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for region in ("barrel", "endcap"):
        paths.append(draw_nrolls_efficiency([(spec, roll_results[spec]) for spec in specs], region, comparison_output, label, com, ext))

    paths.extend(draw_run3_efficiency_2d(specs, histograms_by_spec, output, label, com, ext))
    if draw_yearly_2d:
        for spec in specs:
            paths.extend(draw_efficiency_2d_for_spec(histograms_by_spec[spec], spec, output, label, com, ext))

    time_spec = combine_dataset_specs(specs)
    run3_time = {
        key: merge_category_efficiencies([time_results[spec][key] for spec in specs])
        for key in TIME_EFFICIENCY_KEYS
    }
    run3_integrated_lumi = {
        key: merge_efficiency1d_results([integrated_lumi_results[spec][key] for spec in specs])
        for key in TIME_EFFICIENCY_KEYS
    }
    time_output = plot_output_dir(output, "efficiency", time_spec.year)
    integrated_lumi_output = plot_output_dir(output, "efficiency", time_spec.year)
    for plot in TIME_EFFICIENCY_PLOTS:
        paths.append(draw_time_efficiency(run3_time, plot, time_spec, time_output, label, com, ext))
    for plot in INTEGRATED_LUMI_EFFICIENCY_PLOTS:
        paths.append(draw_integrated_lumi_efficiency(run3_integrated_lumi, plot, time_spec, integrated_lumi_output, label, com, ext))

    if draw_roll_maps:
        if geom is None:
            raise RuntimeError("Efficiency roll maps require RPC geometry")
        for spec in specs:
            roll_result = roll_results[spec]
            masked = roll_mask_names(spec.year)
            eff = efficiency_series(roll_result.total_by_roll, roll_result.passed_by_roll)
            roll_map_specs = [
                RollMapSpec(
                    EFFICIENCY_ROLL_MAP["name"],
                    eff,
                    EFFICIENCY_ROLL_MAP["label"],
                    EFFICIENCY_ROLL_MAP["cmap"],
                    EFFICIENCY_ROLL_MAP["vmin"],
                    EFFICIENCY_ROLL_MAP["vmax"],
                    excluded_rolls=masked,
                )
            ]
            for roll_map in build_roll_maps(geom, roll_map_specs):
                paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "efficiency-map", spec.year), spec.year, label, com, spec.lumi, ext))
    return paths
