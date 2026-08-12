#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUN_META_PATH = PACKAGE_DIR / "data/lumi/run3.csv"
DEFAULT_GEOM_PATH = PACKAGE_DIR / "data/geometry/run3.csv"


def add_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--input", dest="input_groups", action="append", nargs="+", required=True, type=Path,
                        help="Input merged histogram ROOT file(s) for one year. Repeat for multiple years.")
    parser.add_argument("-y", "--year", dest="years", action="append", required=True, type=int,
                        help="Year label matched to each --input group.")
    parser.add_argument("--lumi", dest="lumis", action="append", required=True, type=float,
                        help="Integrated luminosity matched to each --input group.")
    parser.add_argument("-s", "--com", type=float, default=13.6, help="Center-of-mass energy in TeV.")
    parser.add_argument("-o", "--output", required=True, type=Path,
                        help="Common plot output root; Run3/RunYYYY, category, and plot-type directories are created automatically.")
    parser.add_argument("-l", "--label", default="Preliminary", help="CMS extra label.")
    parser.add_argument("--ext", choices=["png", "pdf"], default="png", help="Output file extension.")
    parser.add_argument("--yearly-2d", action="store_true",
                        help="Also draw per-year efficiency and mean-CLS 2D plots under RunYYYY.")
    parser.add_argument("--efficiency-maps", action="store_true",
                        help="Also draw per-year roll efficiency maps.")
    parser.add_argument("--roll-maps", action="store_true",
                        help="Also draw per-year roll mean-CLS maps.")
    parser.add_argument("--no-excluded-rolls", dest="show_excluded_rolls", action="store_false", default=True,
                        help="Do not hatch yearly blacklist rolls on roll map plots.")
    parser.add_argument("--all-probe-pt", dest="probe_pt_gt15", action="store_false", default=True,
                        help="Use the full probe-pT plotting range instead of starting at 15 GeV.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_dataset_args(parser)
    parser.add_argument("-g", "--geom-path", type=Path, default=DEFAULT_GEOM_PATH,
                        help=f"CSV file containing RPC roll geometry for map outputs. Default: {DEFAULT_GEOM_PATH}")
    parser.add_argument("--run-meta-path", type=Path, default=DEFAULT_RUN_META_PATH,
                        help=f"Run metadata CSV. Default: {DEFAULT_RUN_META_PATH}")
    args = parser.parse_args()
    if not (len(args.input_groups) == len(args.years) == len(args.lumis)):
        parser.error("--input, --year, and --lumi must be repeated the same number of times")
    return args


def main() -> None:
    args = parse_args()
    from RPCDPGAnalysis.NanoAODTnP.Plot import plot_all  # type: ignore

    plot_all(**vars(args))


if __name__ == "__main__":
    main()
