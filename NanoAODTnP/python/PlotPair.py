from __future__ import annotations

from pathlib import Path

import numpy as np

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_pair_2d_results, load_pair_results  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import (  # type: ignore
    add_tag_and_probe_label,
    annotate_count_scale,
    build_year_label,
    combine_dataset_specs,
    comparison_output_dir,
    count_scale,
    draw_binned_stairs,
    draw_year_summary,
    new_figure,
    save_binned_value_map,
    save_figure,
    year_color,
)
from RPCDPGAnalysis.NanoAODTnP.PlotConfig import with_probe_pt_minimum  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import (  # type: ignore
    PLOT_COUNT_MOMENTUM_EDGES,
    PLOT_ETA_EDGES,
    PLOT_PHI_EDGES,
    PLOT_Q_OVER_P_EDGES,
    regular_edges,
)


PAIR_MASS_EDGES = regular_edges(70.0, 110.0, 80)
PAIR_MUON_PT_EDGES = PLOT_COUNT_MOMENTUM_EDGES
PAIR_MUON_ETA_EDGES = PLOT_ETA_EDGES
PAIR_MUON_PHI_EDGES = PLOT_PHI_EDGES
PAIR_MUON_Q_OVER_P_EDGES = PLOT_Q_OVER_P_EDGES

PAIR_1D = [
    {
        "name": "pair_mass",
        "output": "pair-mass",
        "branch": "pair_mass",
        "edges": PAIR_MASS_EDGES,
        "xlabel": r"$\mu^{+}\mu^{-}$ (Tag-Probe) invariant mass [$\mathrm{GeV}$]",
        "ylabel": "Events",
        "y_margin": 1.20,
    },
    {
        "name": "probe_pt",
        "output": "probe-pt",
        "branch": "probe_pt",
        "edges": PAIR_MUON_PT_EDGES,
        "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
        "ylabel": "Events",
        "y_margin": 1.20,
    },
    {
        "name": "probe_eta",
        "output": "probe-eta",
        "branch": "probe_eta",
        "edges": PAIR_MUON_ETA_EDGES,
        "xlabel": r"Probe Muon $\eta$",
        "ylabel": "Events",
        "y_margin": 1.35,
    },
    {
        "name": "probe_phi",
        "output": "probe-phi",
        "branch": "probe_phi",
        "edges": PAIR_MUON_PHI_EDGES,
        "xlabel": r"Probe Muon $\phi$",
        "ylabel": "Events",
        "y_margin": 1.35,
    },
    {
        "name": "probe_q_over_p",
        "output": "probe-q-over-p",
        "branch": "probe_q_over_p",
        "edges": PAIR_MUON_Q_OVER_P_EDGES,
        "xlabel": r"Probe Muon $q/p$ [$\mathrm{GeV}^{-1}$]",
        "ylabel": "Events",
        "y_margin": 1.35,
    },
    {
        "name": "tag_pt",
        "output": "tag-pt",
        "branch": "tag_pt",
        "edges": PAIR_MUON_PT_EDGES,
        "xlabel": r"Tag Muon $p_{T}$ [$\mathrm{GeV}$]",
        "ylabel": "Events",
        "y_margin": 1.20,
    },
    {
        "name": "tag_eta",
        "output": "tag-eta",
        "branch": "tag_eta",
        "edges": PAIR_MUON_ETA_EDGES,
        "xlabel": r"Tag Muon $\eta$",
        "ylabel": "Events",
        "y_margin": 1.35,
    },
    {
        "name": "tag_phi",
        "output": "tag-phi",
        "branch": "tag_phi",
        "edges": PAIR_MUON_PHI_EDGES,
        "xlabel": r"Tag Muon $\phi$",
        "ylabel": "Events",
        "y_margin": 1.35,
    },
]

PAIR_2D = [
    {
        "name": "probe_pt_eta",
        "output": "probe-pt-eta",
        "branch": "probe_pt_eta",
        "x_edges": PAIR_MUON_ETA_EDGES,
        "y_edges": PAIR_MUON_PT_EDGES,
        "xlabel": r"Probe Muon $\eta$",
        "ylabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
    },
    {
        "name": "probe_eta_phi",
        "output": "probe-eta-phi",
        "branch": "probe_eta_phi",
        "x_edges": PAIR_MUON_ETA_EDGES,
        "y_edges": PAIR_MUON_PHI_EDGES,
        "xlabel": r"Probe Muon $\eta$",
        "ylabel": r"Probe Muon $\phi$",
    },
    {
        "name": "tag_pt_eta",
        "output": "tag-pt-eta",
        "branch": "tag_pt_eta",
        "x_edges": PAIR_MUON_ETA_EDGES,
        "y_edges": PAIR_MUON_PT_EDGES,
        "xlabel": r"Tag Muon $\eta$",
        "ylabel": r"Tag Muon $p_{T}$ [$\mathrm{GeV}$]",
    },
    {
        "name": "tag_eta_phi",
        "output": "tag-eta-phi",
        "branch": "tag_eta_phi",
        "x_edges": PAIR_MUON_ETA_EDGES,
        "y_edges": PAIR_MUON_PHI_EDGES,
        "xlabel": r"Tag Muon $\eta$",
        "ylabel": r"Tag Muon $\phi$",
    },
]


def draw_count_hist1d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    fig, ax = new_figure(label, com)
    add_tag_and_probe_label(ax)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    scale_exp, scale = count_scale(max_count)
    for idx, (spec, result) in enumerate(results):
        draw_binned_stairs(ax, result.counts, result.edges, color=year_color(spec.year, idx), label="_nolegend_", scale=scale)
    if max_count > 0.0:
        ax.set_ylim(0.0, plot["y_margin"] * max_count / scale)
    annotate_count_scale(ax, scale_exp)
    draw_year_summary(ax, [
        (year_color(spec.year, idx), build_year_label(spec.year, spec.lumi))
        for idx, (spec, result) in enumerate(results)
    ])
    return save_figure(fig, output, plot["output"], ext)


def draw_count_hist2d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    print(f"[info] plotting {plot['output']}", flush=True)
    spec = combine_dataset_specs([spec for spec, _ in results])
    first = results[0][1]
    counts = np.sum([result.counts for _, result in results], axis=0)
    finite = counts[np.isfinite(counts) & (counts > 0.0)]
    vmax = max(float(np.max(finite)) if len(finite) else 0.0, 1.0)
    return save_binned_value_map(
        counts,
        first.x_edges,
        first.y_edges,
        plot["xlabel"],
        plot["ylabel"],
        "Events",
        output,
        plot["output"],
        label,
        com,
        spec.lumi,
        spec.year,
        ext,
        "viridis",
        0.0,
        vmax,
        mask_zero=True,
    )


def plot_pair(
    specs,
    histograms_by_spec,
    output: Path,
    com: float = 13.6,
    label: str = "Preliminary",
    ext: str = "png",
    probe_pt_minimum: float | None = None,
) -> list[Path]:
    plots_1d = with_probe_pt_minimum(PAIR_1D, probe_pt_minimum)
    plots_2d = with_probe_pt_minimum(PAIR_2D, probe_pt_minimum)
    all_1d = {}
    all_2d = {}
    total_probes = 0
    print("[info] total number of probes", flush=True)
    for spec in specs:
        all_1d[spec] = load_pair_results(histograms_by_spec[spec], plots_1d)
        all_2d[spec] = load_pair_2d_results(histograms_by_spec[spec], plots_2d)
        n_probes = all_1d[spec]["pair_mass"].n_values
        total_probes += n_probes
        print(f"  year={spec.year}  files={','.join(str(path) for path in spec.input_paths)}  n_probes={n_probes}", flush=True)
    print(f"[info] total probes (all inputs) = {total_probes}", flush=True)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "pair/1d", specs)
    for plot in plots_1d:
        results = [(spec, all_1d[spec][plot["name"]]) for spec in specs if plot["name"] in all_1d[spec]]
        if results:
            paths.append(draw_count_hist1d(results, plot, comparison_output, label, com, ext))
    output_2d = comparison_output_dir(output, "pair/2d", specs)
    for plot in plots_2d:
        paths.append(draw_count_hist2d([(spec, all_2d[spec][plot["name"]]) for spec in specs], plot, output_2d, label, com, ext))
    return paths
