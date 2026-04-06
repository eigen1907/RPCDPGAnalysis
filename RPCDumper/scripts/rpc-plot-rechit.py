#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

from RPCDPGAnalysis.RPCDumper.PlotRPCObjectMap import (
    TreeSpec,
    get_available_trees,
    run_scatter_plotting,
)


def get_pkg_dir() -> Path:
    return Path(os.environ["CMSSW_BASE"]) / "src" / "RPCDPGAnalysis" / "RPCDumper"


def parse_args() -> argparse.Namespace:
    pkg = get_pkg_dir()
    data = pkg / "data"

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=data / "sample-rechit.root")
    parser.add_argument("--geom", type=Path, default=data / "sample-geo.csv")
    parser.add_argument("--output", type=Path, default=pkg / "plots" / "rechit")
    parser.add_argument("--label", type=str, default="Phase2 Simulation Private Work")
    parser.add_argument("--year", type=str, default="")
    parser.add_argument("--com", type=float, default=14)
    parser.add_argument("--lumi", type=float, default=None)

    parser.add_argument("--no-rechit", action="store_true")
    parser.add_argument("--rechit-phase2", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    available = set(get_available_trees(args.input))

    tree_specs: list[TreeSpec] = []

    if (not args.no_rechit) and ("rpcRecHitTree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="rpcRecHitTree",
                label="RPCRecHit",
                marker=".",
                size=5.0,
                alpha=0.75,
            )
        )

    if args.rechit_phase2 and ("rpcRecHitPhase2Tree" in available):
        tree_specs.append(
            TreeSpec(
                tree_name="rpcRecHitPhase2Tree",
                label="RPCRecHitPhase2",
                marker="x",
                size=10.0,
                alpha=0.8,
            )
        )

    if not tree_specs:
        return

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