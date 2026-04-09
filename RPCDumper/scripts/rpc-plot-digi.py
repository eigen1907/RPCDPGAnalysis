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
    parser.add_argument("-i", "--input", type=Path, default=data / "digis.root")
    parser.add_argument("-g", "--geom", type=Path, default=data / "geometry.csv")
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

    if (not args.no_rpc_digi) and ("simMuonRPCDigisTree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="simMuonRPCDigisTree",
                label="simMuonRPCDigis",
                marker="o",
                size=18.0,
                alpha=0.90,
            )
        )

    if (not args.no_rpc_digi_phase2) and ("simMuonRPCDigisPhase2Tree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="simMuonRPCDigisPhase2Tree",
                label="simMuonRPCDigisPhase2",
                marker="x",
                size=18.0,
                alpha=0.90,
            )
        )

    if (not args.no_irpc) and ("simMuonIRPCDigisTree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="simMuonIRPCDigisTree",
                label="simMuonIRPCDigis",
                marker="^",
                size=18.0,
                alpha=0.9,
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