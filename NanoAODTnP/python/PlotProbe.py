from __future__ import annotations

from pathlib import Path

import numpy as np

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import mean_and_error  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistIO import load_probe_result, merge_profile1d_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_legend, annotate_count_scale, bin_centers, bin_half_widths, build_year_label, combine_dataset_specs, count_scale, draw_binned_errorbar, draw_errorbar_series, new_figure, save_figure  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import ABS_DXDZ_AXIS, COUNT_MOMENTUM_EDGES, VALUE_MOMENTUM_EDGES, regular_edges  # type: ignore


REGION_TITLES = {"barrel": "RPC Barrel", "endcap": "RPC Endcap"}
PROBE_DXDZ_EDGES = regular_edges(-1.5, 1.5, 150)
PROBE_ABS_DXDZ_EDGES = regular_edges(0.0, 1.5, 75)
PROBE_PT_EDGES = COUNT_MOMENTUM_EDGES
PROBE_AT_RPC_PT_EDGES = COUNT_MOMENTUM_EDGES
PROBE_P_EDGES = COUNT_MOMENTUM_EDGES
PROBE_AT_RPC_P_EDGES = COUNT_MOMENTUM_EDGES
DELTA_PT_EDGES = VALUE_MOMENTUM_EDGES
DELTA_P_EDGES = VALUE_MOMENTUM_EDGES

PROBE_HISTS = [
    {"name": "probe_pt", "output": "probe-pt-rpc", "branch": "probe_pt", "edges": PROBE_PT_EDGES, "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", "region": "all"},
    {"name": "probe_at_rpc_pt", "output": "probe-at-rpc-pt", "branch": "probe_at_rpc_pt", "edges": PROBE_AT_RPC_PT_EDGES, "xlabel": r"Probe at RPC $p_{T}$ [$\mathrm{GeV}$]", "region": "all"},
    {"name": "probe_p", "output": "probe-p", "branch": "probe_p", "edges": PROBE_P_EDGES, "xlabel": r"Probe Muon $p$ [$\mathrm{GeV}$]", "region": "all"},
    {"name": "probe_at_rpc_p", "output": "probe-at-rpc-p", "branch": "probe_at_rpc_p", "edges": PROBE_AT_RPC_P_EDGES, "xlabel": r"Probe at RPC $p$ [$\mathrm{GeV}$]", "region": "all"},
]
for region in ("barrel", "endcap"):
    PROBE_HISTS.append({"name": f"probe_at_rpc_dxdz_{region}", "output": f"probe-at-rpc-dxdz-{region}", "branch": "probe_at_rpc_dxdz", "edges": PROBE_DXDZ_EDGES, "xlabel": r"Signed local slope $dx/dz$", "region": region, "panel_label": REGION_TITLES[region]})
    PROBE_HISTS.append({"name": f"{ABS_DXDZ_AXIS}_{region}", "output": f"probe-abs-dxdz-{region}", "branch": ABS_DXDZ_AXIS, "edges": PROBE_ABS_DXDZ_EDGES, "xlabel": r"$|\tan \alpha| = |dx/dz|$", "region": region, "panel_label": REGION_TITLES[region]})
MOMENTUM_LOSS_REGION_SERIES = (
    ("barrel", "Barrel"),
    ("endcap-minus", "Endcap-"),
    ("endcap-plus", "Endcap+"),
)
MOMENTUM_LOSS_PROFILE_GROUPS = ("all",) + tuple(group for group, _ in MOMENTUM_LOSS_REGION_SERIES)
MOMENTUM_LOSS_PLOTS = [
    {
        "profile": "delta_pt_profiles",
        "output": "mean-probe-pt-loss-vs-probe-pt",
        "edges": DELTA_PT_EDGES,
        "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
        "ylabel": r"Mean $p_{T}^{\mathrm{probe}} - p_{T}^{\mathrm{RPC}}$ [$\mathrm{GeV}$]",
    },
    {
        "profile": "delta_p_profiles",
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
    if "panel_label" in plot:
        ax.text(0.04, 0.94, plot["panel_label"], transform=ax.transAxes, ha="left", va="top", fontsize=22)
    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    scale_exp, scale = count_scale(max_count)
    for idx, (spec, result) in enumerate(results):
        draw_binned_errorbar(ax, result.counts, result.edges, color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], label=build_year_label(spec.year, spec.lumi), scale=scale)
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.25 * max_count / scale)
    annotate_count_scale(ax, scale_exp)
    add_legend(ax)
    return save_figure(fig, output, plot["output"], ext)


def draw_momentum_loss(series, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    fig, ax = new_figure(label, com)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    for idx, (series_label, profile) in enumerate(series):
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if np.any(mask):
            draw_errorbar_series(ax, bin_centers(profile.edges)[mask], mean, DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], series_label, xerr=bin_half_widths(profile.edges)[mask], yerr=yerr)
    add_legend(ax, loc="best")
    return save_figure(fig, output, plot["output"], ext)


def plot_probe(
    specs,
    histograms_by_spec,
    output: Path,
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
) -> list[Path]:
    results = {
        spec: load_probe_result(histograms_by_spec[spec], PROBE_HISTS, DELTA_PT_EDGES, DELTA_P_EDGES, MOMENTUM_LOSS_PROFILE_GROUPS)
        for spec in specs
    }

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "probe", specs)
    combined_spec = combine_dataset_specs(specs)
    for plot in MOMENTUM_LOSS_PLOTS:
        combined_profiles = {
            group: merge_profile1d_results([results[spec][plot["profile"]][group] for spec in specs])
            for group in MOMENTUM_LOSS_PROFILE_GROUPS
        }
        paths.append(draw_momentum_loss(
            [(build_year_label(combined_spec.year, combined_spec.lumi), combined_profiles["all"])],
            plot,
            comparison_output,
            label,
            com,
            ext,
        ))
        paths.append(draw_momentum_loss(
            [(series_label, combined_profiles[group]) for group, series_label in MOMENTUM_LOSS_REGION_SERIES],
            {**plot, "output": f"{plot['output']}-by-region"},
            comparison_output,
            label,
            com,
            ext,
        ))
    for plot in PROBE_HISTS:
        paths.append(draw_hist([(spec, results[spec]["hists"][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    return paths
