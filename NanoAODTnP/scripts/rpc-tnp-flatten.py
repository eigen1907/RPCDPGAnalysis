#!/usr/bin/env python3
import argparse
from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.Analysis import flatten_nanoaod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_path")
    parser.add_argument("-c", "--cert_path", type=Path)
    parser.add_argument("-o", "--output_path", type=Path)
    parser.add_argument("-n", "--name", nargs="?", default="rpcTnP")
    args = parser.parse_args()

    flatten_nanoaod(
        input_path=args.input_path,
        cert_path=args.cert_path,
        output_path=args.output_path,
        name=args.name,
    )


if __name__ == "__main__":
    main()