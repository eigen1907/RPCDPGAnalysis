from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import mean_and_error  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistIO import load_probe_result  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_legend, annotate_count_scale, bin_centers, bin_half_widths, build_dataset_specs, build_year_label, count_scale, dataset_specs_with_combined, draw_binned_errorbar, draw_errorbar_series, new_figure, plot_output_dir, save_figure, save_roll_value_map  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_series  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, regular_edges  # type: ignore


PROBE_DXDZ_EDGES = regular_edges(-0.6, 0.6, 120)
PROBE_ABS_DXDZ_EDGES = regular_edges(0.0, 0.6, 60)
PROBE_PT_EDGES = regular_edges(0.0, 100.0, 50)
PROBE_AT_RPC_PT_EDGES = regular_edges(0.0, 100.0, 50)
PROBE_P_EDGES = regular_edges(0.0, 200.0, 100)
PROBE_AT_RPC_P_EDGES = regular_edges(0.0, 200.0, 100)
DELTA_PT_EDGES = regular_edges(0.0, 100.0, 50)
DELTA_P_EDGES = regular_edges(0.0, 200.0, 100)

PROBE_HISTS = [
    {"name": "probe_at_rpc_dxdz", "output": "probe-at-rpc-dxdz", "branch": "probe_at_rpc_dxdz", "edges": PROBE_DXDZ_EDGES, "xlabel": r"Signed local slope $dx/dz$"},
    {"name": ABS_DXDZ_AXIS, "output": "probe-abs-dxdz", "branch": ABS_DXDZ_AXIS, "edges": PROBE_ABS_DXDZ_EDGES, "xlabel": r"$|\tan \alpha| = |dx/dz|$"},
    {"name": "probe_pt", "output": "probe-pt-rpc", "branch": "probe_pt", "edges": PROBE_PT_EDGES, "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]"},
    {"name": "probe_at_rpc_pt", "output": "probe-at-rpc-pt", "branch": "probe_at_rpc_pt", "edges": PROBE_AT_RPC_PT_EDGES, "xlabel": r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]"},
    {"name": "probe_p", "output": "probe-p", "branch": "probe_p", "edges": PROBE_P_EDGES, "xlabel": r"Probe Muon $p$ [$\mathrm{GeV}$]"},
    {"name": "probe_at_rpc_p", "output": "probe-at-rpc-p", "branch": "probe_at_rpc_p", "edges": PROBE_AT_RPC_P_EDGES, "xlabel": r"Probe at RPC $p$ [$\mathrm{GeV}$]"},
]
MIN_PROFILE_ENTRIES = 100.0
MIN_ROLL_ENTRIES = 100.0
PROBE_ROLL_MAPS = [
    {"name": "probe-at-rpc-pt", "mean": "probe_at_rpc_pt", "label": r"Mean Probe at RPC $p_{T}$ [$\mathrm{GeV}$]", "cmap": "viridis", "vmin": 0.0, "vmax": 60.0},
    {"name": "probe-at-rpc-p", "mean": "probe_at_rpc_p", "label": r"Mean Probe at RPC $p$ [$\mathrm{GeV}$]", "cmap": "viridis", "vmin": 0.0, "vmax": 120.0},
]
MOMENTUM_LOSS_PLOTS = [
    {
        "profile": "delta_pt_profile",
        "output": "mean-probe-pt-loss-vs-probe-pt",
        "edges": DELTA_PT_EDGES,
        "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
        "ylabel": r"Mean $p_{T}^{\mathrm{probe}} - p_{T}^{\mathrm{RPC}}$ [$\mathrm{GeV}$]",
    },
    {
        "profile": "delta_p_profile",
        "output": "mean-probe-p-loss-vs-probe-p",
        "edges": DELTA_P_EDGES,
        "xlabel": r"Probe Muon $p$ [$\mathrm{GeV}$]",
        "ylabel": r"Mean $p^{\mathrm{probe}} - p^{\mathrm{RPC}}$ [$\mathrm{GeV}$]",
    },
]


def draw_hist(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    fig, ax = new_figure(label, com)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel("Probe Crossings", fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    scale_exp, scale = count_scale(max_count)
    for idx, (spec, result) in enumerate(results):
        draw_binned_errorbar(ax, result.counts, result.edges, color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], label=build_year_label(spec.year, spec.lumi), scale=scale)
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.25 * max_count / scale)
    annotate_count_scale(ax, scale_exp)
    add_legend(ax)
    return save_figure(fig, output, plot["output"], ext)


def draw_momentum_loss(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    fig, ax = new_figure(label, com)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    for idx, (spec, profile) in enumerate(results):
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts, min_count=MIN_PROFILE_ENTRIES)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], build_year_label(spec.year, spec.lumi), xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    return save_figure(fig, output, plot["output"], ext)


def plot_probe(
    input_groups: Sequence[Sequence[Path]],
    years: Sequence[int],
    output: Path,
    lumis: Sequence[float],
    geom_path: Path,
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
) -> list[Path]:
    specs = build_dataset_specs(input_groups, years, lumis)
    output_specs = dataset_specs_with_combined(specs)
    results = {spec: load_probe_result(spec, PROBE_HISTS, DELTA_PT_EDGES, DELTA_P_EDGES) for spec in output_specs}

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "probe", specs)
    for plot in MOMENTUM_LOSS_PLOTS:
        paths.append(draw_momentum_loss([(spec, results[spec][plot["profile"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for plot in PROBE_HISTS:
        paths.append(draw_hist([(spec, results[spec]["hists"][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))

    geom = pd.read_csv(geom_path)
    for spec in output_specs:
        roll_result = results[spec]["roll_result"]
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
            for plot in PROBE_ROLL_MAPS
        ]
        for roll_map in build_roll_maps(geom, roll_map_specs):
            paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "probe", spec.year, "map"), spec.year, label, com, spec.lumi, ext))
    return paths
