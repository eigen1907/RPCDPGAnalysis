from collections import defaultdict
from pathlib import Path
from typing import Optional, Union
import json
import numpy as np
import numpy.typing as npt
import pandas as pd
import uproot
import matplotlib.pyplot as plt
from matplotlib.colors import Colormap
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
import mplhep as mh
from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCRoll # type: ignore



def plot_patches(patches: list[Polygon],
                 values: npt.NDArray[np.float32],
                 mask: Optional[npt.NDArray[np.bool_]] = None,
                 cmap: Union[Colormap, str] = 'magma',
                 edgecolor: str = 'gray',
                 ax: Optional[plt.Axes] = None,
                 vmin: Optional[Union[float, np.float32]] = None,
                 vmax: Optional[Union[float, np.float32]] = None,
                 lw: float = 2,
) -> plt.Figure:
    """
    """
    ax = ax or plt.gca()

    if vmin is None:
        vmin = np.nanmin(values)
    if vmax is None:
        vmax = np.nanmax(values)

    cmap = plt.get_cmap(cmap)

    normalized_values = (values - vmin) / (vmax - vmin)
    normalized_values = np.clip(normalized_values, 0.0, 1.0)
    normalized_values = np.nan_to_num(normalized_values, nan=0.0, posinf=1.0, neginf=0.0)

    color = cmap(normalized_values)

    if mask is not None:
        inactive_color = np.array([0.85, 0.85, 0.85, 1.0], dtype=np.float64)
        color[mask] = inactive_color

    collection = PatchCollection(patches)
    collection.set_color(color)
    collection.set_edgecolor(edgecolor)
    collection.set_linewidth(lw)
    ax.add_collection(collection)

    ax.autoscale_view()
    scalar_mappable = plt.cm.ScalarMappable(
        cmap=cmap,
        norm=plt.Normalize(vmin=vmin, vmax=vmax)
    )
    scalar_mappable.set_array([])
    axes_divider = make_axes_locatable(ax)
    cax = axes_divider.append_axes("right", size="5%", pad=0.2)
    cax.figure.colorbar(scalar_mappable, cax=cax, pad=0.1)

    return ax.figure


def load_eff_detector(input_path: Path,
                      geom_path: Path):
    input_file = uproot.open(input_path)

    branches = [
        'region', 'ring', 'station', 'sector', 'layer', 'subsector', 'roll',
        'is_fiducial', 'is_matched',
    ]

    arrays = input_file['trial_tree'].arrays(branches, library='np')

    trial_df = pd.DataFrame({
        key: arrays[key]
        for key in branches
    })

    geom = pd.read_csv(geom_path)

    key_cols = ['region', 'ring', 'station', 'sector', 'layer', 'subsector', 'roll']
    geom_key = geom[key_cols + ['roll_name']].drop_duplicates()

    trial_df = trial_df.merge(
        geom_key,
        on=key_cols,
        how='left',
        validate='many_to_one',
    )

    missing_mask = trial_df['roll_name'].isna()
    if missing_mask.any():
        missing_rows = trial_df.loc[missing_mask, key_cols].drop_duplicates()
        raise ValueError(
            'Some trial_tree rows could not be matched to geom.csv.\n'
            f'Number of unmatched detector keys: {len(missing_rows)}\n'
            f'Examples:\n{missing_rows.head()}'
        )

    fiducial_mask = trial_df['is_fiducial'].astype(bool).to_numpy()
    passed_mask = (
        trial_df['is_fiducial'].astype(bool).to_numpy()
        & trial_df['is_matched'].astype(bool).to_numpy()
    )

    total_by_roll = (
        trial_df.loc[fiducial_mask]
        .groupby('roll_name')
        .size()
        .astype(np.int64)
    )

    passed_by_roll = (
        trial_df.loc[passed_mask]
        .groupby('roll_name')
        .size()
        .astype(np.int64)
    )

    return total_by_roll, passed_by_roll


def plot_eff_roll(total_by_roll: pd.Series,
                  passed_by_roll: pd.Series,
                  detector_unit: str,
                  roll_list: list[RPCRoll],
                  percentage: bool,
                  label: str,
                  year: Union[int, str],
                  com: float,
                  output_path: Optional[Path],
                  close: bool,
):
    """
    plot eff
    """
    name_list = [each.id.name for each in roll_list]

    total = total_by_roll.reindex(name_list, fill_value=0).to_numpy(dtype=np.float64)
    passed = passed_by_roll.reindex(name_list, fill_value=0).to_numpy(dtype=np.float64)

    eff = np.divide(
        passed,
        total,
        out=np.zeros_like(total, dtype=np.float64),
        where=(total > 0),
    )

    patches = [each.polygon for each in roll_list]
    values = 100 * eff if percentage else eff
    inactive_roll_mask = total < 1
    vmin = 0
    vmax = 100 if percentage else 1

    fig, ax = plt.subplots()
    fig = plot_patches(
        patches=patches,
        values=values,
        mask=inactive_roll_mask,
        vmin=vmin,
        vmax=vmax,
        ax=ax,
    )
    _, cax = fig.get_axes()

    xlabel = roll_list[0].polygon_xlabel
    ylabel = roll_list[0].polygon_ylabel
    ymax = roll_list[0].polygon_ymax

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    cax_ylabel = 'Efficiency'
    if percentage:
        cax_ylabel += ' [%]'
    cax.set_ylabel(cax_ylabel)
    cax.set_ylim(vmin, vmax)
    ax.set_ylim(None, ymax)
    ax.annotate(
        detector_unit,
        (0.05, 0.925),
        weight='bold',
        xycoords='axes fraction',
    )
    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    if output_path is not None:
        for suffix in ['.pdf']:
            fig.savefig(output_path.with_suffix(suffix))

    if close:
        plt.close(fig)

    return fig


def plot_eff_detector(input_path: Path,
                      geom_path: Path,
                      output_dir: Path,
                      com: float,
                      year: Union[int, str],
                      label: str,
                      percentage: bool = True,
                      roll_blacklist_path: Optional[Path] = None,
):
    if roll_blacklist_path is None:
        roll_blacklist = set()
    else:
        with open(roll_blacklist_path) as stream:
            roll_blacklist = set(json.load(stream))

    total_by_roll, passed_by_roll = load_eff_detector(
        input_path=input_path,
        geom_path=geom_path,
    )

    geom = pd.read_csv(geom_path)
    roll_list = [
        RPCRoll.from_row(row)
        for _, row in geom.iterrows()
        if row.roll_name not in roll_blacklist
    ]

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    # wheel (or disk) to rolls
    unit_to_rolls = defaultdict(list)
    for roll in roll_list:
        unit_to_rolls[roll.id.detector_unit].append(roll)

    for detector_unit, unit_roll_list in unit_to_rolls.items():
        output_path = output_dir / detector_unit
        plot_eff_roll(
            total_by_roll=total_by_roll,
            passed_by_roll=passed_by_roll,
            detector_unit=detector_unit,
            roll_list=unit_roll_list,
            percentage=percentage,
            label=label,
            year=year,
            com=com,
            output_path=output_path,
            close=True,
        )


