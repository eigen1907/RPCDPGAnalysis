#!/usr/bin/env python3
"""
"""
from pathlib import Path
import argparse
import matplotlib as mpl
import mplhep as mh
from RPCDPGAnalysis.NanoAODTnP.Plotting import plot_eff_detector # type: ignore

mpl.use('agg')
mh.style.use(mh.styles.CMS)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-i', '--input-path', required=True, type=Path,
                        help='root file created by rpc-tnp-flatten-nanoaod.py')
    parser.add_argument('-g', '--geom-path', required=True, type=Path,
                        help='csv file containing RPC roll information')
    parser.add_argument('-s', '--com', required=True, type=float,
                        help='centre-of-mass energy (e.g. 13.6)')
    parser.add_argument('-y', '--year', required=True, type=str,
                        help='year (e.g. 2023 or 2023D)')
    parser.add_argument('-o', '--output-dir', default=Path.cwd(), type=Path, 
                        help='output directory')
    parser.add_argument('--percentage', action=argparse.BooleanOptionalAction,
                        default=True,
                        help='express efficiency as a percentage')
    parser.add_argument('--roll-blacklist-path', default=None, type=Path,
                        help=('json file containing a list of rolls to be '
                              'excluded from plots'))

    label_group = parser.add_mutually_exclusive_group()
    label_list = ['Preliminary', 'Data', 'Simulation', 'Private Work']
    for label in label_list:
        flag = '--' + label.lower().replace(' ', '-')
        help_msg = f"top left label is set to '{label}'"
        label_group.add_argument(flag, action='store_const', dest='label',
                                 const=label, help=help_msg)
    parser.set_defaults(label=label_list[0])

    args = parser.parse_args()

    plot_eff_detector(**vars(args))


if __name__ == "__main__":
    main()
