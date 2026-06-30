#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.Analyze import analyze  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze one RPC TnP NanoAOD file and write a histogram ROOT shard."
    )
    parser.add_argument("-i", "--input", dest="input_path", required=True, type=Path,
                        help="Input NanoAOD ROOT file.")
    parser.add_argument("-c", "--cert", dest="cert_path", required=True, type=Path,
                        help="Certification JSON file.")
    parser.add_argument("-o", "--output", dest="output_path", required=True, type=Path,
                        help="Histogram ROOT output path.")
    parser.add_argument("--roll-blacklist-path", required=True, type=Path,
                        help="Roll blacklist text file applied while filling RPC histograms.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input_path.is_file():
        raise FileNotFoundError(f"Input NanoAOD file does not exist: {args.input_path}")
    if not args.cert_path.is_file():
        raise FileNotFoundError(f"Certification JSON does not exist: {args.cert_path}")
    if not args.roll_blacklist_path.is_file():
        raise FileNotFoundError(f"Roll blacklist does not exist: {args.roll_blacklist_path}")
    analyze(
        input_path=args.input_path,
        cert_path=args.cert_path,
        output_path=args.output_path,
        roll_blacklist_path=args.roll_blacklist_path,
    )


if __name__ == "__main__":
    main()
