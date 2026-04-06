#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path

from RPCDPGAnalysis.RPCDumper.PlotRPCObjectMap import run_geometry_plotting


def get_pkg_dir() -> Path:
    return Path(os.environ["CMSSW_BASE"]) / "src" / "RPCDPGAnalysis" / "RPCDumper"


def parse_args() -> argparse.Namespace:
    pkg = get_pkg_dir()
    data = pkg / "data"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-g", "--geom", type=Path, default=data / "geometry.csv")
    parser.add_argument("-o", "--output", type=Path, default=pkg / "plots" / "geometry")
    parser.add_argument("--label", type=str, default="Phase2 Simulation Private Work")
    parser.add_argument("--year", type=str, default="")
    parser.add_argument("--com", type=float, default=14)
    parser.add_argument("--lumi", type=float, default=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_geometry_plotting(
        geom_path=args.geom,
        output_dir=args.output,
        label=args.label,
        year=args.year,
        com=args.com,
        lumi=args.lumi,
    )


if __name__ == "__main__":
    main()