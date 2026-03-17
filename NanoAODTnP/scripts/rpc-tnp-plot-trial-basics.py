#!/usr/bin/env python3

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.PlotTrialBasics import plot_trial_basics  # type: ignore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-path', type=Path, required=True)
    parser.add_argument('-o', '--output-dir', type=Path, required=True)
    parser.add_argument('-s', '--com', type=float, required=True)
    parser.add_argument('-y', '--year', required=True)
    parser.add_argument('-l', '--label', default='Private Work', type=str)
    args = parser.parse_args()

    plot_trial_basics(
        input_path=args.input_path,
        output_dir=args.output_dir,
        com=args.com,
        year=args.year,
        label=args.label,
    )


if __name__ == '__main__':
    main()