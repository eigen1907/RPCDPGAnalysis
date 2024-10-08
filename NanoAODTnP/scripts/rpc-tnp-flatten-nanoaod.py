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
    parser.add_argument('-g', '--geom-path', required=True, type=Path,
                        help='csv file containing RPC roll information')
    #parser.add_argument('-r', '--run-path', required=True, type=Path,
    #                    help='csv file contaning existing run list')
    parser.add_argument('-o', '--output-path', default='output.root',
                        type=Path, help='output file name')
    parser.add_argument('-n', '--name', default='rpcTnP', type=str,
                        help='branch prefix')
    parser.add_argument('--roll-mask-path', type=str,
                        help='roll mask file')
    parser.add_argument('--run-mask-path', type=str,
                        help='run mask file')
    args = parser.parse_args()

    flatten_nanoaod(
        input_path=args.input_path,
        cert_path=args.cert_path,
        geom_path=args.geom_path,
        #run_path=args.run_path,
        output_path=args.output_path,
        name=args.name,
        roll_mask_path=args.roll_mask_path,
        run_mask_path=args.run_mask_path,
    )


if __name__ == "__main__":
    main()
