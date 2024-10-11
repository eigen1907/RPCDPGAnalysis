from typing import Optional, Union
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
    color = cmap(normalized_values)
    if mask is not None:
        color[mask] = np.nan

    collection = PatchCollection(patches)
    collection.set_color(color)
    collection.set_edgecolor(edgecolor)
    collection.set_linewidth(lw)
    ax.add_collection(collection)

    # add colobar
    ax.autoscale_view()
    scalar_mappable = plt.cm.ScalarMappable(
        cmap=cmap,
        norm=plt.Normalize(vmin=vmin, vmax=vmax) # FIXME
    )
    scalar_mappable.set_array([])
    axes_divider = make_axes_locatable(ax)
    cax = axes_divider.append_axes("right", size="5%", pad=0.2)
    cax.figure.colorbar(scalar_mappable, cax=cax, pad=0.1)

    return ax.figure


def plot_eff_detector_unit(h_total,
                           h_passed,
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

    total = h_total[name_list].values() # type: ignore
    passed = h_passed[name_list].values() # type: ignore
    eff = np.divide(passed, total, out=np.zeros_like(total),
                    where=(total > 0))

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
        ax=ax
    )
    _, cax = fig.get_axes()

    xlabel = roll_list[0].polygon_xlabel
    ylabel = roll_list[0].polygon_ylabel
    ymax = roll_list[0].polygon_ymax

    ax.set_xlabel(xlabel) # type: ignore
    ax.set_ylabel(ylabel) # type: ignore

    cax_ylabel = 'Efficiency'
    if percentage:
        cax_ylabel += ' [%]'
    cax.set_ylabel(cax_ylabel)
    cax.set_ylim(vmin, vmax)
    ax.set_ylim(None, ymax) # type: ignore
    ax.annotate(detector_unit, (0.05, 0.925), weight='bold',
                xycoords='axes fraction') # type: ignore
    mh.cms.label(ax=ax, llabel=label, com=com, year=year)

    if output_path is not None:
        for suffix in ['.png', '.pdf']:
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
    input_file = uproot.open(input_path)

    if roll_blacklist_path is None:
        roll_blacklist = set()
    else:
        with open(roll_blacklist_path) as stream:
            roll_blacklist = set(json.load(stream))

    h_total: Hist = input_file['total'].to_hist() # type: ignore
    h_passed: Hist = input_file['passed'].to_hist() # type: ignore

    geom = pd.read_csv(geom_path)
    roll_list = [RPCRoll.from_row(row)
                 for _, row in geom.iterrows()
                 if row.roll_name not in roll_blacklist]

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    # wheel (or disk) to rolls
    unit_to_rolls = defaultdict(list)
    for roll in roll_list:
        unit_to_rolls[roll.id.detector_unit].append(roll)

    for detector_unit, roll_list in unit_to_rolls.items():
        output_path = output_dir / detector_unit
        plot_eff_detector_unit(
            h_total,
            h_passed,
            detector_unit=detector_unit,
            roll_list=roll_list,
            percentage=percentage,
            label=label,
            year=year,
            com=com,
            output_path=output_path,
            close=True
        )


