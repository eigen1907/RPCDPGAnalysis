#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

from RPCDPGAnalysis.RPCDumper.PlotRPCObjectMap import (
    DIGI_TREES,
    TreeSpec,
    get_available_trees,
    run_scatter_plotting,
)


def get_pkg_dir() -> Path:
    return Path(os.environ["CMSSW_BASE"]) / "src" / "RPCDPGAnalysis" / "RPCDumper"


def parse_args() -> argparse.Namespace:
    pkg = get_pkg_dir()
    data = pkg / "data"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input", type=Path, default=data / "sample-digi.root")
    parser.add_argument("-g", "--geom", type=Path, default=data / "sample-geo.csv")
    parser.add_argument("-o", "--output", type=Path, default=pkg / "plots" / "digi")
    parser.add_argument("--label", type=str, default="Phase2 Simulation Private Work")
    parser.add_argument("--year", type=str, default="")
    parser.add_argument("--com", type=float, default=14)
    parser.add_argument("--lumi", type=float, default=None)

    parser.add_argument("--no-rpc-digi", action="store_true")
    parser.add_argument("--no-rpc-digi-phase2", action="store_true")
    parser.add_argument("--no-irpc", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    available = set(get_available_trees(args.input, allowed_trees=DIGI_TREES))

    print("[info] available trees:", ", ".join(sorted(available)) if available else "(none)")

    tree_specs: list[TreeSpec] = []

    if (not args.no_rpc_digi) and ("rpcDigiTree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="rpcDigiTree",
                label="RPCDigi",
                marker=".",
                size=4.0,
                alpha=0.70,
            )
        )

    if (not args.no_rpc_digi_phase2) and ("rpcDigiPhase2Tree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="rpcDigiPhase2Tree",
                label="RPCDigiPhase2",
                marker="x",
                size=10.0,
                alpha=0.80,
            )
        )

    if (not args.no_irpc) and ("irpcDigiTree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="irpcDigiTree",
                label="IRPCDigi",
                marker="^",
                size=8.0,
                alpha=0.75,
            )
        )

    if not tree_specs:
        print("[warning] No requested digi trees were found.")
        return

    print("[info] trees to draw:", ", ".join(spec.tree_name for spec in tree_specs))

    run_scatter_plotting(
        input_path=args.input,
        geom_path=args.geom,
        output_dir=args.output,
        tree_specs=tree_specs,
        label=args.label,
        year=args.year,
        com=args.com,
        lumi=args.lumi,
    )


if __name__ == "__main__":
    main()