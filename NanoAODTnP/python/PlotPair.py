from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_pair_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_cms_label, add_legend, annotate_count_scale, build_dataset_specs, build_year_label, cms_year_label, count_scale, dataset_specs_with_combined, draw_binned_errorbar, draw_colormesh, new_figure, plot_output_dir, save_figure  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import regular_edges  # type: ignore


MIN_2D_BIN_ENTRIES = 100.0
PAIR_MASS_EDGES = regular_edges(70.0, 110.0, 80)
PAIR_MUON_PT_EDGES = regular_edges(0.0, 100.0, 50)
PROBE_ETA_EDGES = regular_edges(-2.1, 2.1, 84)
TAG_ETA_EDGES = regular_edges(-2.4, 2.4, 96)

PAIR_1D = [
    {"name": "pair_mass", "output": "pair-mass", "branch": "pair_mass", "edges": PAIR_MASS_EDGES, "xlabel": r"$\mu^{+}\mu^{-}$ (Tag-Probe) invariant mass [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "probe_pt", "output": "probe-pt", "branch": "probe_pt", "edges": PAIR_MUON_PT_EDGES, "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "probe_eta", "output": "probe-eta", "branch": "probe_eta", "edges": PROBE_ETA_EDGES, "xlabel": r"Probe Muon $\eta$", "ylabel": "Events", "y_margin": 1.35},
    {"name": "tag_pt", "output": "tag-pt", "branch": "tag_pt", "edges": PAIR_MUON_PT_EDGES, "xlabel": r"Tag Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "tag_eta", "output": "tag-eta", "branch": "tag_eta", "edges": TAG_ETA_EDGES, "xlabel": r"Tag Muon $\eta$", "ylabel": "Events", "y_margin": 1.35},
]
PAIR_2D = [
    {"name": "probe_pt_eta", "output": "probe-pt-eta", "x_branch": "probe_pt", "y_branch": "probe_eta", "x_edges": PAIR_MUON_PT_EDGES, "y_edges": PROBE_ETA_EDGES, "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": r"Probe Muon $\eta$"},
    {"name": "tag_pt_eta", "output": "tag-pt-eta", "x_branch": "tag_pt", "y_branch": "tag_eta", "x_edges": PAIR_MUON_PT_EDGES, "y_edges": TAG_ETA_EDGES, "xlabel": r"Tag Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": r"Tag Muon $\eta$"},
]


def draw_count_hist1d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    fig, ax = new_figure(label, com)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    scale_exp, scale = count_scale(max_count)
    for idx, (spec, result) in enumerate(results):
        draw_binned_errorbar(ax, result.counts, result.edges, color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)], label=build_year_label(spec.year, spec.lumi), scale=scale)
    if max_count > 0.0:
        ax.set_ylim(0.0, plot["y_margin"] * max_count / scale)
    annotate_count_scale(ax, scale_exp)
    add_legend(ax, frameon=True)
    return save_figure(fig, output, plot["output"], ext)


def draw_count_hist2d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> list[Path]:
    paths: list[Path] = []
    for spec, result in results:
        print(f"[info] plotting {plot['output']}-Run{spec.year}", flush=True)
        fig, ax = plt.subplots(figsize=(12, 8))
        add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
        ax.set_xlabel(plot["xlabel"], fontsize=22)
        ax.set_ylabel(plot["ylabel"], fontsize=22)
        ax.set_xlim(float(plot["x_edges"][0]), float(plot["x_edges"][-1]))
        ax.set_ylim(float(plot["y_edges"][0]), float(plot["y_edges"][-1]))
        draw_colormesh(fig, ax, result.counts, result.x_edges, result.y_edges, "Events", min_visible_value=MIN_2D_BIN_ENTRIES)
        paths.append(save_figure(fig, plot_output_dir(output, "pair", spec.year, "2d"), plot["output"], ext))
    return paths


def plot_pair(
    input_groups: Sequence[Sequence[Path]],
    years: Sequence[int],
    output: Path,
    lumis: Sequence[float],
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
) -> list[Path]:
    specs = build_dataset_specs(input_groups, years, lumis)
    output_specs = dataset_specs_with_combined(specs)
    all_1d = {}
    all_2d = {}
    total_probes = 0
    print("[info] total number of probes", flush=True)
    for spec in specs:
        result_1d, result_2d = load_pair_results(spec, PAIR_1D, PAIR_2D)
        all_1d[spec] = result_1d
        all_2d[spec] = result_2d
        n_probes = result_1d["pair_mass"].n_values
        total_probes += n_probes
        print(f"  year={spec.year}  files={','.join(str(path) for path in spec.input_paths)}  n_probes={n_probes}", flush=True)
    print(f"[info] total probes (all inputs) = {total_probes}", flush=True)
    for spec in output_specs[len(specs):]:
        all_1d[spec], all_2d[spec] = load_pair_results(spec, PAIR_1D, PAIR_2D)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "pair", specs)
    for plot in PAIR_1D:
        paths.append(draw_count_hist1d([(spec, all_1d[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for plot in PAIR_2D:
        paths.extend(draw_count_hist2d(
            [(spec, all_2d[spec][plot["name"]]) for spec in output_specs],
            plot,
            output,
            label,
            com,
            ext,
        ))
    return paths
