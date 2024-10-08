#!/usr/bin/env python3
import argparse
from pathlib import Path
from RPCDPGAnalysis.NanoAODTnP.Analysis import merge_flat_nanoaod_files


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-i', '--input-paths', nargs='+', required=True, type=Path,
                        help='input Flat NanoAOD file paths')
    parser.add_argument('-o', '--output-path', required=True, type=Path,
                        help='output file path')
    args = parser.parse_args()

    merge_flat_nanoaod_files(
        input_paths=args.input_paths,
        output_path=args.output_path,
    )


if __name__ == "__main__":
    main()
