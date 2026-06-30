from __future__ import annotations

from pathlib import Path

import numpy as np

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_pair_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import DEFAULT_COLORS, comparison_output_dir, add_legend, annotate_count_scale, build_year_label, count_scale, draw_binned_errorbar, new_figure, save_figure  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import COUNT_MOMENTUM_EDGES, regular_edges  # type: ignore


PAIR_MASS_EDGES = regular_edges(70.0, 110.0, 80)
PAIR_MUON_PT_EDGES = COUNT_MOMENTUM_EDGES
PROBE_ETA_EDGES = regular_edges(-2.1, 2.1, 84)
TAG_ETA_EDGES = regular_edges(-2.4, 2.4, 96)

PAIR_1D = [
    {"name": "pair_mass", "output": "pair-mass", "branch": "pair_mass", "edges": PAIR_MASS_EDGES, "xlabel": r"$\mu^{+}\mu^{-}$ (Tag-Probe) invariant mass [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "probe_pt", "output": "probe-pt", "branch": "probe_pt", "edges": PAIR_MUON_PT_EDGES, "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "probe_eta", "output": "probe-eta", "branch": "probe_eta", "edges": PROBE_ETA_EDGES, "xlabel": r"Probe Muon $\eta$", "ylabel": "Events", "y_margin": 1.35},
    {"name": "tag_pt", "output": "tag-pt", "branch": "tag_pt", "edges": PAIR_MUON_PT_EDGES, "xlabel": r"Tag Muon $p_{T}$ [$\mathrm{GeV}$]", "ylabel": "Events", "y_margin": 1.20},
    {"name": "tag_eta", "output": "tag-eta", "branch": "tag_eta", "edges": TAG_ETA_EDGES, "xlabel": r"Tag Muon $\eta$", "ylabel": "Events", "y_margin": 1.35},
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


def plot_pair(
    specs,
    histograms_by_spec,
    output: Path,
    com: float = 13.6,
    label: str = "Work in Progress",
    ext: str = "png",
) -> list[Path]:
    all_1d = {}
    total_probes = 0
    print("[info] total number of probes", flush=True)
    for spec in specs:
        all_1d[spec] = load_pair_results(histograms_by_spec[spec], PAIR_1D)
        n_probes = all_1d[spec]["pair_mass"].n_values
        total_probes += n_probes
        print(f"  year={spec.year}  files={','.join(str(path) for path in spec.input_paths)}  n_probes={n_probes}", flush=True)
    print(f"[info] total probes (all inputs) = {total_probes}", flush=True)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "pair", specs)
    for plot in PAIR_1D:
        paths.append(draw_count_hist1d([(spec, all_1d[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    return paths
