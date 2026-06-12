#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.PlotRPC import plot_rpc  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import add_rpc_dataset_args, rpc_plot_kwargs, validate_rpc_dataset_args  # type: ignore


PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUN_META_PATH = PACKAGE_DIR / "data/lumi/run3.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_rpc_dataset_args(parser)
    parser.add_argument("-g", "--geom-path", required=True, type=Path, help="CSV file containing RPC roll geometry for map outputs.")
    parser.add_argument("--run-meta-path", dest="run_meta_paths", action="append", nargs="+", type=Path,
                        help=f"Run metadata CSV, directory, or glob. Default: {DEFAULT_RUN_META_PATH}")
    args = parser.parse_args()
    if args.run_meta_paths is None:
        args.run_meta_paths = [DEFAULT_RUN_META_PATH]
    validate_rpc_dataset_args(args)
    return args


def main() -> None:
    plot_rpc(**rpc_plot_kwargs(parse_args()))


if __name__ == "__main__":
    main()
