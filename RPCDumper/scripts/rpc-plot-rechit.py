#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

from RPCDPGAnalysis.RPCDumper.PlotRPCObjectMap import (
    RECHIT_TREES,
    TreeSpec,
    get_available_trees,
    run_scatter_plotting,
)

from RPCDPGAnalysis.RPCDumper.plotRPCHist1D import (
    rechit_hist_list,
    run_hist1d_plotting,
)


def get_pkg_dir() -> Path:
    return Path(os.environ["CMSSW_BASE"]) / "src" / "RPCDPGAnalysis" / "RPCDumper"


def parse_args() -> argparse.Namespace:
    pkg = get_pkg_dir()
    data = pkg / "data"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-i", "--input", type=Path, default=data / "rechits.root")
    parser.add_argument("-g", "--geom", type=Path, default=data / "geometry.csv")
    parser.add_argument("-o", "--output", type=Path, default=pkg / "plots" / "rechit")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    label = "Phase2 Simulation Private Work"
    year = ""
    com = 14
    lumi = None

    available = set(get_available_trees(args.input, allowed_trees=RECHIT_TREES))
    print("[info] available trees:", ", ".join(sorted(available)) if available else "(none)")

    tree_specs: list[TreeSpec] = []

    if "rpcRecHitsTree" in available:
        tree_specs.append(
            TreeSpec(
                tree_name="rpcRecHitsTree",
                label="rpcRecHits",
                marker="o",
                size=18.0,
                alpha=0.90,
            )
        )

    if "rpcRecHitsPhase2Tree" in available:
        tree_specs.append(
            TreeSpec(
                tree_name="rpcRecHitsPhase2Tree",
                label="rpcRecHitsPhase2",
                marker="x",
                size=18.0,
                alpha=0.90,
            )
        )

    if not tree_specs:
        print("[warning] No rechit trees were found.")
        return

    print("[info] trees to draw:", ", ".join(spec.tree_name for spec in tree_specs))

    run_scatter_plotting(
        input_path=args.input,
        geom_path=args.geom,
        output_dir=args.output / "map2d",
        tree_specs=tree_specs,
        label=label,
        year=year,
        com=com,
        lumi=lumi,
    )

    run_hist1d_plotting(
        input_path=args.input,
        output_dir=args.output / "hist1d",
        tree_specs=tree_specs,
        hist_list=rechit_hist_list(),
        label=label,
        year=year,
        com=com,
        lumi=lumi,
    )


if __name__ == "__main__":
    main()