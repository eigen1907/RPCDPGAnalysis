#!/usr/bin/env python3

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.PlotEffDetector import plot_eff_detector  # type: ignore


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-i", "--input-path", required=True, type=Path,
                        help="root file or directory containing flat ROOT files")
    parser.add_argument("-g", "--geom-path", required=True, type=Path,
                        help="csv file containing RPC roll information")
    parser.add_argument("-s", "--com", required=True, type=float,
                        help="centre-of-mass energy (e.g. 13.6)")
    parser.add_argument("-y", "--year", required=True, type=str,
                        help="year (e.g. 2023 or 2023D)")
    parser.add_argument("--lumi", default=None, type=float,
                        help="integrated luminosity in fb^-1")
    parser.add_argument("-o", "--output-dir", default=Path.cwd(), type=Path,
                        help="output directory")
    parser.add_argument("--percentage", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="express efficiency as a percentage")
    parser.add_argument("--roll-blacklist-path", default=None, type=Path,
                        help="json file containing a list of rolls to be excluded from plots")
    parser.add_argument("--hide-irpc", action="store_true",
                        help="do not draw iRPC rolls (RE±3/4, ring 1)")
    parser.add_argument("--exclude-eff-below", default=None, type=float,
                        help="draw rolls below this efficiency threshold as hatched Excluded")
    parser.add_argument("--excluded-legend-loc", default="best", type=str,
                        help='matplotlib legend location for the "Excluded" label')
    parser.add_argument("-l", "--label", default="Work in Progress", type=str,
                        help='label to be used in plots (e.g. "CMS Preliminary")')
    args = parser.parse_args()

    plot_eff_detector(**vars(args))


if __name__ == "__main__":
    main()