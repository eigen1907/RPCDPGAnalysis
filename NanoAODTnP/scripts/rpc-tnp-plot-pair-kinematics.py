#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import uproot
import matplotlib as mpl
mpl.use("agg")
import matplotlib.pyplot as plt
import mplhep as mh

from hist import Hist
from hist.axis import Regular


mh.style.use(mh.styles.CMS)


DEFAULT_COLORS = [
    "firebrick",
    "mediumblue",
    "darkgreen",
    "darkorange",
]

DEFAULT_HATCHES = [
    #"\\",
    #"/",
    #"+",
    #".",
    None,
    None,
    None,
    None,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        dest="inputs",
        action="append",
        required=True,
        help="Input ROOT file path. Repeat this option for multiple years."
    )
    parser.add_argument(
        "-y", "--year",
        dest="years",
        action="append",
        required=True,
        type=int,
        help="Year label matched to each input. Repeat in the same order as --input."
    )
    parser.add_argument(
        "--lumi",
        dest="lumis",
        action="append",
        type=float,
        default=None,
        help="Integrated luminosity matched to each input/year. Repeat in the same order as --input. "
             "If omitted, only the year is shown in the legend."
    )
    parser.add_argument(
        "-s", "--com",
        type=float,
        default=13.6,
        help="Center-of-mass energy in TeV."
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output directory."
    )
    parser.add_argument(
        "-l", "--label",
        default="Work in Progress",
        help="CMS extra label."
    )
    parser.add_argument(
        "--tree-name",
        default="pair_tree",
        help="Default input tree name."
    )
    parser.add_argument(
        "--branch",
        default="dimuon_mass",
        help="Default branch to plot."
    )
    parser.add_argument(
        "--xmin",
        type=float,
        default=70.0,
        help="Default histogram x minimum."
    )
    parser.add_argument(
        "--xmax",
        type=float,
        default=110.0,
        help="Default histogram x maximum."
    )
    parser.add_argument(
        "--nbins",
        type=int,
        default=80,
        help="Default number of histogram bins."
    )
    parser.add_argument(
        "--name",
        default="rpc_tnp_pair_mass",
        help="Default output file stem."
    )
    parser.add_argument(
        "--ext",
        default="png",
        choices=["png", "pdf"],
        help="Output file extension."
    )

    parser.add_argument(
        "--plot-probe-pt",
        action="store_true",
        help="Also make Probe Muon pT distribution."
    )
    parser.add_argument(
        "--plot-probe-eta",
        action="store_true",
        help="Also make Probe Muon eta distribution."
    )
    parser.add_argument(
        "--probe-tree-name",
        default=None,
        help="Tree name for probe distributions. If omitted, --tree-name is used."
    )

    parser.add_argument(
        "--probe-pt-branch",
        default="probe_pt",
        help="Branch name for Probe Muon pT."
    )
    parser.add_argument(
        "--probe-pt-xmin",
        type=float,
        default=0.0,
        help="Probe pT histogram x minimum."
    )
    parser.add_argument(
        "--probe-pt-xmax",
        type=float,
        default=200.0,
        help="Probe pT histogram x maximum."
    )
    parser.add_argument(
        "--probe-pt-nbins",
        type=int,
        default=100,
        help="Number of bins for Probe pT."
    )
    parser.add_argument(
        "--probe-pt-name",
        default="rpc-tnp-probe-pt",
        help="Output file stem for Probe pT."
    )

    parser.add_argument(
        "--probe-eta-branch",
        default="probe_eta",
        help="Branch name for Probe Muon eta."
    )
    parser.add_argument(
        "--probe-eta-xmin",
        type=float,
        default=-2.5,
        help="Probe eta histogram x minimum."
    )
    parser.add_argument(
        "--probe-eta-xmax",
        type=float,
        default=2.5,
        help="Probe eta histogram x maximum."
    )
    parser.add_argument(
        "--probe-eta-nbins",
        type=int,
        default=60,
        help="Number of bins for Probe eta."
    )
    parser.add_argument(
        "--probe-eta-name",
        default="rpc-tnp-probe-eta",
        help="Output file stem for Probe eta."
    )

    args = parser.parse_args()

    if len(args.inputs) != len(args.years):
        raise RuntimeError(
            f"Number of --input ({len(args.inputs)}) and --year ({len(args.years)}) must match"
        )

    if args.lumis is not None and len(args.lumis) not in (0, len(args.inputs)):
        raise RuntimeError(
            f"Number of --lumi ({len(args.lumis)}) must be either 0 or match --input ({len(args.inputs)})"
        )

    return args


def build_legend_label(year: int, lumi: float | None) -> str:
    if lumi is None:
        return rf"$%d$" % year
    return rf"$%d\ (%.2f\ fb^{{-1}})$" % (year, lumi)


def load_tree_branch(
    path: Path,
    tree_name: str,
    branch_name: str,
) -> np.ndarray:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            raise RuntimeError(f"Missing tree '{tree_name}' in {path}")

        tree = root_file[tree_name]
        keys = list(tree.keys())
        if branch_name not in keys:
            raise RuntimeError(f"Missing branch '{branch_name}' in {path}:{tree_name}")

        value = tree[branch_name].array(library="np")

    value = np.asarray(value, dtype=np.float64)
    value = value[np.isfinite(value)]
    return value


def make_xlabel(branch_name: str) -> str:
    if branch_name == "dimuon_mass":
        return r"$\mu^{+}\mu^{-}$ (Tag-Probe) invariant mass [$\mathrm{GeV}$]"
    if branch_name == "probe_pt":
        return r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]"
    if branch_name == "probe_eta":
        return r"Probe Muon $\eta$"
    return branch_name


def make_ylabel(x_min: float, x_max: float, n_bins: int, branch_name: str) -> str:
    bin_width = (x_max - x_min) / n_bins

    if branch_name in ("dimuon_mass", "probe_pt"):
        #return rf"Events / {bin_width:.1f} $\mathrm{{GeV}}$"
        return rf"Events"
    if branch_name == "probe_eta":
        #return rf"Events / {bin_width:.2f}"
        return rf"Events"
    #return rf"Events / {bin_width:.3g}"
    return rf"Events"


def plot_branch_distribution(
    input_paths: Sequence[Path],
    years: Sequence[int],
    lumis: Sequence[float] | None,
    output_dir: Path,
    cms_label: str,
    com_energy: float,
    tree_name: str,
    branch_name: str,
    x_min: float,
    x_max: float,
    n_bins: int,
    output_name: str,
    output_ext: str,
):
    fig, ax = plt.subplots(figsize=(12, 8))

    mh.cms.label(
        ax=ax,
        data=True,
        llabel=cms_label,
        year="Run 3",
        com=com_energy,
        loc=0,
        fontsize=24,
    )

    ax.set_xlabel(
        make_xlabel(branch_name),
        fontsize=22,
    )
    ax.set_xlim(x_min, x_max)

    all_hists = []
    max_count = 0.0

    for idx, (input_path, year) in enumerate(zip(input_paths, years)):
        lumi = None if lumis is None or len(lumis) == 0 else lumis[idx]
        label = build_legend_label(year, lumi)

        values = load_tree_branch(
            path=input_path,
            tree_name=tree_name,
            branch_name=branch_name,
        )

        hist_obj = Hist(Regular(n_bins, x_min, x_max))
        hist_obj.fill(values)

        counts = np.asarray(hist_obj.values(), dtype=np.float64)
        edges = np.asarray(hist_obj.axes[0].edges, dtype=np.float64)

        if len(counts) > 0:
            max_count = max(max_count, float(np.max(counts)))

        all_hists.append((year, label, counts, edges))

    if max_count > 0.0:
        scale_exp = int(np.floor(np.log10(max_count)))
    else:
        scale_exp = 0

    scale = 10.0 ** scale_exp

    for idx, (_, label, counts, edges) in enumerate(all_hists):
        counts_scaled = counts / scale

        ax.stairs(
            counts_scaled,
            edges,
            label=label,
            color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)],
            linewidth=2,
            hatch=DEFAULT_HATCHES[idx % len(DEFAULT_HATCHES)],
            fill=False,
        )

    ax.set_ylabel(
        make_ylabel(x_min, x_max, n_bins, branch_name),
        fontsize=22,
    )
    
    if max_count > 0.0:
        y_margin = 1.35 if branch_name == "probe_eta" else 1.20
        ax.set_ylim(0.0, y_margin * max_count / scale)

    ax.annotate(
        rf"$x10^{scale_exp}$",
        (-0.06, 1.0),
        xycoords="axes fraction",
        fontsize=18,
        horizontalalignment="left",
    )

    ax.legend(fontsize=18, handleheight=1.2, loc="upper right")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_name}.{output_ext}"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    return output_path


def main() -> None:
    args = parse_args()

    input_paths = [Path(each) for each in args.inputs]
    years = list(args.years)
    lumis = None if args.lumis is None else list(args.lumis)

    output_paths = []

    output_paths.append(
        plot_branch_distribution(
            input_paths=input_paths,
            years=years,
            lumis=lumis,
            output_dir=args.output,
            cms_label=args.label,
            com_energy=args.com,
            tree_name=args.tree_name,
            branch_name=args.branch,
            x_min=args.xmin,
            x_max=args.xmax,
            n_bins=args.nbins,
            output_name=args.name,
            output_ext=args.ext,
        )
    )

    probe_tree_name = args.probe_tree_name if args.probe_tree_name is not None else args.tree_name

    if args.plot_probe_pt:
        output_paths.append(
            plot_branch_distribution(
                input_paths=input_paths,
                years=years,
                lumis=lumis,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                tree_name=probe_tree_name,
                branch_name=args.probe_pt_branch,
                x_min=args.probe_pt_xmin,
                x_max=args.probe_pt_xmax,
                n_bins=args.probe_pt_nbins,
                output_name=args.probe_pt_name,
                output_ext=args.ext,
            )
        )

    if args.plot_probe_eta:
        output_paths.append(
            plot_branch_distribution(
                input_paths=input_paths,
                years=years,
                lumis=lumis,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                tree_name=probe_tree_name,
                branch_name=args.probe_eta_branch,
                x_min=args.probe_eta_xmin,
                x_max=args.probe_eta_xmax,
                n_bins=args.probe_eta_nbins,
                output_name=args.probe_eta_name,
                output_ext=args.ext,
            )
        )

    for output_path in output_paths:
        print(f"[done] saved: {output_path}", flush=True)


if __name__ == "__main__":
    main()