#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.PlotProbe import plot_probe  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import add_rpc_dataset_args, rpc_plot_kwargs, validate_rpc_dataset_args  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_rpc_dataset_args(parser)
    parser.add_argument("-g", "--geom-path", required=True, type=Path, help="CSV file containing RPC roll geometry for map outputs.")
    args = parser.parse_args()
    validate_rpc_dataset_args(args)
    return args


def main() -> None:
    plot_probe(**rpc_plot_kwargs(parse_args()))


if __name__ == "__main__":
    main()
