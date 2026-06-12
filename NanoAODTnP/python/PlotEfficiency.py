from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_efficiency_results, merge_category_efficiencies, merge_efficiency1d_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.BuildUtils import clopper_pearson_count_yerr, clopper_pearson_efficiency_yerr, efficiency_series, efficiency_stats  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_cms_label, add_legend, bin_centers, bin_half_widths, build_dataset_specs, build_year_label, cms_year_label, combine_dataset_specs, dataset_specs_with_combined, draw_binned_errorbar, draw_errorbar_series, new_figure, plot_output_dir, save_figure, save_roll_value_map  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_series  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, regular_edges  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadRunMeta import read_run_meta  # type: ignore


REGION_TITLES = {"barrel": "RPC Barrel", "endcap": "RPC Endcap"}
DEFAULT_EFF_THRESHOLD = 70.0
MIN_EFFICIENCY_BIN_ENTRIES = 100.0
MIN_ROLL_ENTRIES = 100.0
PT_EDGES = regular_edges(0.0, 100.0, 20)
P_EDGES = regular_edges(0.0, 200.0, 40)
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

EFF_1D_PLOTS: list[dict] = []
for region in ("barrel", "endcap"):
    EFF_1D_PLOTS.append({
        "name": f"eff_abs_dxdz_{region}",
        "output": f"eff-abs-dxdz-{region}",
        "branch": ABS_DXDZ_AXIS,
        "edges": ABS_DXDZ_EDGES_BY_REGION[region],
        "xlabel": r"Projected local slope $|dx/dz|$",
        "region": region,
        "panel_label": REGION_TITLES[region],
    })
    for branch, output, edges, xlabel in KINEMATIC_PLOTS:
        EFF_1D_PLOTS.append({
            "name": f"eff_{branch}_{region}",
            "output": f"eff-{output}-{region}",
            "branch": branch,
            "edges": edges,
            "xlabel": xlabel,
            "region": region,
            "panel_label": REGION_TITLES[region],
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

MONTHLY_EFFICIENCY_PLOTS = [
    {
        "output": "eff-month-rb",
        "series": BARREL_STATION_SERIES,
    },
    {
        "output": "eff-month-re-plus",
        "series": tuple((f"RE+{station}", f"RE+{station}") for station in range(1, 5)),
    },
    {
        "output": "eff-month-re-minus",
        "series": tuple((f"RE-{station}", f"RE-{station}") for station in range(1, 5)),
    },
    {
        "output": "eff-month-region",
        "series": (("barrel", "Barrel"), ("endcap", "Endcap")),
    },
]

MONTHLY_EFFICIENCY_KEYS = tuple(dict.fromkeys(
    key
    for plot in MONTHLY_EFFICIENCY_PLOTS
    for key, _ in plot["series"]
))
INTEGRATED_LUMI_EFFICIENCY_PLOTS = [
    {**plot, "output": plot["output"].replace("eff-month-", "eff-integ-lumi-")}
    for plot in MONTHLY_EFFICIENCY_PLOTS
]


def draw_efficiency_1d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    ax.set_ylim(0.0, 105.0)
    for idx, (spec, profile) in enumerate(results):
        mask, eff, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total, min_total=MIN_EFFICIENCY_BIN_ENTRIES)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], eff, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], build_year_label(spec.year, spec.lumi), xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    return save_figure(fig, output, output_name, ext)


def draw_monthly_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel("Month", fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_ylim(0.0, 105.0)
    month_labels = sorted({
        month
        for key, _ in plot["series"]
        for month in result_by_key[key].labels
    })
    month_positions = {month: idx for idx, month in enumerate(month_labels)}
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, efficiency, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total, min_total=MIN_EFFICIENCY_BIN_ENTRIES)
        if not np.any(mask):
            continue
        x = np.asarray([month_positions[month] for month in profile.labels[mask]], dtype=np.float64)
        draw_errorbar_series(ax, x, efficiency, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, yerr=yerr, marker_size=5)
    ax.set_xticks(np.arange(len(month_labels), dtype=np.float64))
    ax.set_xticklabels(month_labels, rotation=45, ha="right")
    add_legend(ax, loc="best")
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def draw_integrated_lumi_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    print(f"[info] plotting {output_name}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    ax.set_xlabel(r"Integrated Luminosity [fb$^{-1}$]", fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    ax.set_ylim(0.0, 105.0)
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, efficiency, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total, min_total=MIN_EFFICIENCY_BIN_ENTRIES)
        if not np.any(mask):
            continue
        draw_errorbar_series(ax, bin_centers(profile.edges)[mask], efficiency, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, xerr=bin_half_widths(profile.edges)[mask], yerr=yerr, marker_size=5)
    add_legend(ax, loc="best")
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def draw_nrolls_efficiency(results, region: str, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = f"nrolls-eff-{region}"
    print(f"[info] plotting {output_name}", flush=True)
    fig, ax = new_figure(label, com)
    ax.text(0.04, 0.94, REGION_TITLES[region], transform=ax.transAxes, ha="left", va="top", fontsize=22)
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
        handle = draw_binned_errorbar(ax, counts, edges, color=color, label=build_year_label(spec.year, spec.lumi), yerr=clopper_pearson_count_yerr(counts))
        legend_handles.append(handle)
        mean_good, frac_bad = efficiency_stats(values, DEFAULT_EFF_THRESHOLD)
        legend_labels.append(f"{build_year_label(spec.year, spec.lumi):<18}{mean_good:>10.1f}{frac_bad:>10.1f}")
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.35 * max_count)
    ax.legend(legend_handles, legend_labels, loc="upper left", bbox_to_anchor=(0.02, 0.88), frameon=False, handlelength=1.8, handleheight=1.2, labelspacing=0.35, borderpad=0.2, prop=FontProperties(family=["DejaVu Sans Mono"], size=16))
    return save_figure(fig, output, output_name, ext)


def plot_efficiency(
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
    results_1d = {}
    roll_results = {}
    monthly_results = {}
    integrated_lumi_results = {}
    for spec in map_specs:
        results_1d[spec], roll_results[spec], monthly_results[spec], integrated_lumi_results[spec] = load_efficiency_results(spec, EFF_1D_PLOTS, run_meta, MONTHLY_EFFICIENCY_KEYS)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "efficiency", specs)
    for plot in EFF_1D_PLOTS:
        paths.append(draw_efficiency_1d([(spec, results_1d[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for region in ("barrel", "endcap"):
        paths.append(draw_nrolls_efficiency([(spec, roll_results[spec]) for spec in specs], region, comparison_output, label, com, ext))

    time_spec = combine_dataset_specs(specs)
    run3_monthly = {
        key: merge_category_efficiencies([monthly_results[spec][key] for spec in specs])
        for key in MONTHLY_EFFICIENCY_KEYS
    }
    run3_integrated_lumi = {
        key: merge_efficiency1d_results([integrated_lumi_results[spec][key] for spec in specs])
        for key in MONTHLY_EFFICIENCY_KEYS
    }
    monthly_output = plot_output_dir(output, "efficiency", time_spec.year, "time/month")
    integrated_lumi_output = plot_output_dir(output, "efficiency", time_spec.year, "time/integrated-lumi")
    for plot in MONTHLY_EFFICIENCY_PLOTS:
        paths.append(draw_monthly_efficiency(run3_monthly, plot, time_spec, monthly_output, label, com, ext))
    for plot in INTEGRATED_LUMI_EFFICIENCY_PLOTS:
        paths.append(draw_integrated_lumi_efficiency(run3_integrated_lumi, plot, time_spec, integrated_lumi_output, label, com, ext))

    geom = pd.read_csv(geom_path)
    for spec in map_specs:
        roll_result = roll_results[spec]
        masked = roll_mask_series(years if str(spec.year) == "3" else spec.year)
        eff = efficiency_series(roll_result.total_by_roll, roll_result.passed_by_roll).where(roll_result.total_by_roll >= MIN_ROLL_ENTRIES)
        roll_map_specs = [
            RollMapSpec(
                EFFICIENCY_ROLL_MAP["name"],
                eff,
                EFFICIENCY_ROLL_MAP["label"],
                EFFICIENCY_ROLL_MAP["cmap"],
                EFFICIENCY_ROLL_MAP["vmin"],
                EFFICIENCY_ROLL_MAP["vmax"],
                excluded_by_roll=masked,
            )
        ]
        for roll_map in build_roll_maps(geom, roll_map_specs):
            paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "efficiency", spec.year, "map"), spec.year, label, com, spec.lumi, ext))
    return paths
