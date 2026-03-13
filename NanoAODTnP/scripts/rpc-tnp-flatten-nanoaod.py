#!/usr/bin/env python3
import argparse
from pathlib import Path
from RPCDPGAnalysis.NanoAODTnP.Analysis import flatten_nanoaod


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-i', '--input-path', required=True, type=Path,
                        help='input NanoAOD file')
    parser.add_argument('-c', '--cert-path', required=True, type=Path,
                        help='Golden JSON file')
    parser.add_argument('-o', '--output-path', default='output.root',
                        type=Path, help='output file name')
    parser.add_argument('-n', '--name', default='rpcTnP', type=str,
                        help='branch prefix')
    args = parser.parse_args()

    flatten_nanoaod(
        input_path=args.input_path,
        cert_path=args.cert_path,
        output_path=args.output_path,
        name=args.name,
    )


if __name__ == "__main__":
    main()
