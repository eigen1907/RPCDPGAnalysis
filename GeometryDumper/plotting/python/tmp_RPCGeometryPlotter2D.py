from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.offsetbox as offsetbox
import tqdm


def load_region_geometry(
    input_path: str,
    region_name: str,
):
    geometry = pd.read_csv(input_path, sep=',', index_col=False)
    region_geometry = geometry[geometry['roll_name'].str.startswith(region_name)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-path',
                        type=str, required=True,
                        help='input geometry csv file made by RPCGeometryDumper')
    parser.add_argument('-r', '--region-name',
                        type=str, required=True,
                        help='RPC region, e.g. RE-3 or RE+4 etc,,')
    parser.add_argument('-o', '--output-dir',
                        type=Path, default=(Path.cwd() / 'plot'),
                        help='output directory')
    parser.add_argument('-s', '--plot-style',
                        type=str, default='XY',
                        help='plot axis & style: {"XY", "XY_LR", "XY_FB", "YZ_FB", "XYZ_FB", "XYZ_FB_Anim"}')
    args = parser.parse_args()

    region_geometry = load_region_geometry(args.input_path, args.region_name)

    if   args.plot_style == "XY":           plotting_XY(args.output_dir)
    elif args.plot_style == "XY_LR":        plotting_XY_LR(args.output_dir)
    elif args.plot_style == "XY_FB":        plotting_XY_FB(args.output_dir)
    elif args.plot_style == "YZ_FB":        plotting_YZ_FB(args.output_dir)
    elif args.plot_style == "XYZ_FB":       plotting_XYZ_FB(args.output_dir)
    elif args.plot_style == "XYZ_FB_Anim":  plotting_XYZ_FB_Anim(args.output_dir)

if __name__ == "__main__":
    main()