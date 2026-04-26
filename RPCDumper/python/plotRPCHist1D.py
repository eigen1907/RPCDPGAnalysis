from __future__ import annotations

from pathlib import Path

import numpy as np
import uproot
from hist import Hist
import hist
import matplotlib as mpl

mpl.use("agg")
import matplotlib.pyplot as plt
import mplhep as mh

from RPCDPGAnalysis.RPCDumper.PlotRPCObjectMap import (
    TreeSpec,
    resolve_input_files,
    find_tree_path,
)

mh.style.use(mh.styles.CMS)


def pick_branch(branches: set[str], names: list[str]) -> str | None:
    for name in names:
        if name in branches:
            return name
    return None


def read_branch(input_path: Path, tree_name: str, branch: str) -> np.ndarray:
    values = []

    for file_path in resolve_input_files(input_path):
        tree_path = find_tree_path(file_path, tree_name)
        if tree_path is None:
            continue

        with uproot.open(file_path) as root_file:
            tree = root_file[tree_path]
            branches = set(tree.keys())

            if branch == "rechit_xerr":
                source = pick_branch(branches, ["rechit_local_err_xx", "local_err_xx"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")
                arr = np.sqrt(np.maximum(arr, 0.0))

            elif branch == "rechit_yerr":
                source = pick_branch(branches, ["rechit_local_err_yy", "local_err_yy"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")
                arr = np.sqrt(np.maximum(arr, 0.0))

            elif branch == "rechit_local_x":
                source = pick_branch(branches, ["rechit_local_x", "local_x"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_local_y":
                source = pick_branch(branches, ["rechit_local_y", "local_y"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_local_z":
                source = pick_branch(branches, ["rechit_local_z", "local_z"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_cls":
                source = pick_branch(branches, ["rechit_cls", "cluster_size"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_time":
                source = pick_branch(branches, ["rechit_time", "time"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_time_error":
                source = pick_branch(branches, ["rechit_time_error", "time_error"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_bx":
                source = pick_branch(branches, ["rechit_bx", "bx"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            elif branch == "rechit_local_err_xy":
                source = pick_branch(branches, ["rechit_local_err_xy", "local_err_xy"])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            else:
                source = pick_branch(branches, [branch])
                if source is None:
                    continue
                arr = tree[source].array(library="np")

            values.append(arr)

    if len(values) == 0:
        return np.array([])

    values = np.concatenate(values)
    values = values[np.isfinite(values)]

    return values


def run_hist1d_plotting(
    input_path: Path,
    output_dir: Path,
    tree_specs: list[TreeSpec],
    hist_list: list[tuple[str, int, float, float, str, str]],
    label: str = "Phase2 Simulation Private Work",
    year: str = "",
    com: float = 14,
    lumi: float | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for branch, bins, xmin, xmax, xlabel, output_name in hist_list:
        fig, ax = plt.subplots(figsize=(12, 9))

        n_drawn = 0

        for spec in tree_specs:
            values = read_branch(
                input_path=input_path,
                tree_name=spec.tree_name,
                branch=branch,
            )

            if len(values) == 0:
                continue

            h = Hist(
                hist.axis.Regular(
                    bins,
                    xmin,
                    xmax,
                    name="x",
                    label=xlabel,
                )
            )
            h.fill(x=values)

            mh.histplot(
                h,
                ax=ax,
                histtype="step",
                linewidth=2,
                density=True,
                label=f"{spec.label} ({len(values)})",
            )

            n_drawn += 1

        if n_drawn == 0:
            plt.close(fig)
            print(f"[warning] skip {branch}: no entries")
            continue

        ax.set_xlabel(xlabel)
        ax.set_ylabel("Normalized entries")
        ax.legend(loc="best", fontsize=16, frameon=True)
        ax.grid(True, linestyle="--", alpha=0.4)

        mh.cms.label(
            ax=ax,
            llabel=label,
            year=year,
            com=com,
            lumi=lumi,
        )

        output_path = output_dir / f"{output_name}.png"
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        print(f"[info] saved {output_path}")


def digi_hist_list() -> list[tuple[str, int, float, float, str, str]]:
    return [
        ("strip", 200, 0.5, 200.5, "Digi strip", "strip"),
        ("bx", 21, -10.5, 10.5, "Digi BX", "bx"),
        ("bxLR", 21, -10.5, 10.5, "Digi BX LR", "bxlr"),
        ("bxHR", 21, -10.5, 10.5, "Digi BX HR", "bxhr"),
        ("sbx", 32, -0.5, 31.5, "Digi sub-BX", "sbx"),
        ("sbxLR", 32, -0.5, 31.5, "Digi sub-BX LR", "sbxlr"),
        ("sbxHR", 32, -0.5, 31.5, "Digi sub-BX HR", "sbxhr"),
        ("fineLR", 64, -0.5, 63.5, "Digi fine LR", "finelr"),
        ("fineHR", 64, -0.5, 63.5, "Digi fine HR", "finehr"),
        ("local_x", 120, -150.0, 150.0, "Digi local x [cm]", "local_x"),
        ("local_y", 120, -150.0, 150.0, "Digi local y [cm]", "local_y"),
        ("local_z", 40, -5.0, 5.0, "Digi local z [cm]", "local_z"),
        ("time", 120, -50.0, 50.0, "Digi time [ns]", "time"),
    ]


def rechit_hist_list() -> list[tuple[str, int, float, float, str, str]]:
    return [
        ("rechit_local_x", 120, -150.0, 150.0, "RecHit local x [cm]", "local_x"),
        ("rechit_local_y", 120, -150.0, 150.0, "RecHit local y [cm]", "local_y"),
        ("rechit_local_z", 40, -5.0, 5.0, "RecHit local z [cm]", "local_z"),
        ("rechit_xerr", 100, 0.0, 5.0, "RecHit local x error [cm]", "xerr"),
        ("rechit_yerr", 100, 0.0, 5.0, "RecHit local y error [cm]", "yerr"),
        ("rechit_local_err_xy", 100, -5.0, 5.0, "RecHit local error xy [cm^{2}]", "xyerr"),
        ("rechit_cls", 20, 0.5, 20.5, "RecHit cluster size", "cls"),
        ("rechit_time", 120, -50.0, 50.0, "RecHit time [ns]", "time"),
        ("rechit_time_error", 80, -2.0, 10.0, "RecHit time error [ns]", "time_err"),
        ("rechit_bx", 21, -10.5, 10.5, "RecHit BX", "bx"),
    ]