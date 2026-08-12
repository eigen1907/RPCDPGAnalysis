#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.Analyze import analyze  # type: ignore

PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUN_BLACKLIST_PATH = PACKAGE_DIR / "data" / "blacklist" / "run" / "blackList.txt"


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
    parser.add_argument("--roll-blacklist-path", type=Path,
                        help="Roll blacklist text file applied while filling RPC histograms.")
    parser.add_argument("--run-blacklist-path", default=DEFAULT_RUN_BLACKLIST_PATH, type=Path,
                        help=f"Run blacklist text file applied while filling histograms. Default: {DEFAULT_RUN_BLACKLIST_PATH}")
    parser.add_argument("--no-roll-blacklist", action="store_true",
                        help="Do not apply the roll blacklist.")
    parser.add_argument("--no-run-blacklist", action="store_true",
                        help="Do not apply the run blacklist.")
    parser.add_argument("--tight-match", action="store_true",
                        help="Use abs(residual_x) <= 20 cm or abs(pull_x) <= 4 as the matched selection.")
    parser.add_argument("--all-probe-pt", dest="probe_pt_gt15", action="store_false", default=True,
                        help="Disable the default pT > 15 GeV probe selection.")
    parser.add_argument("--bx-zero", action="store_true",
                        help="Require BX == 0 for matched RPC hits; fiducial efficiency denominators are unchanged.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input_path.is_file():
        raise FileNotFoundError(f"Input NanoAOD file does not exist: {args.input_path}")
    if not args.cert_path.is_file():
        raise FileNotFoundError(f"Certification JSON does not exist: {args.cert_path}")
    if not args.no_roll_blacklist and args.roll_blacklist_path is None:
        raise ValueError("--roll-blacklist-path is required unless --no-roll-blacklist is set")
    if not args.no_roll_blacklist and not args.roll_blacklist_path.is_file():
        raise FileNotFoundError(f"Roll blacklist does not exist: {args.roll_blacklist_path}")
    if not args.no_run_blacklist and not args.run_blacklist_path.is_file():
        raise FileNotFoundError(f"Run blacklist does not exist: {args.run_blacklist_path}")
    analyze(
        input_path=args.input_path,
        cert_path=args.cert_path,
        output_path=args.output_path,
        roll_blacklist_path=args.roll_blacklist_path,
        run_blacklist_path=args.run_blacklist_path,
        apply_roll_blacklist=not args.no_roll_blacklist,
        apply_run_blacklist=not args.no_run_blacklist,
        tight_match=args.tight_match,
        probe_pt_gt15=args.probe_pt_gt15,
        bx_zero=args.bx_zero,
    )


if __name__ == "__main__":
    main()
