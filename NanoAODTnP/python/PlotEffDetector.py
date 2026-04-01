from collections import defaultdict
from pathlib import Path
from typing import Optional, Union
import json

import numpy as np
import numpy.typing as npt
import pandas as pd
import uproot

import matplotlib as mpl
mpl.use("agg")

import matplotlib.pyplot as plt
from matplotlib.colors import Colormap
from matplotlib.patches import Polygon, Patch
from matplotlib.collections import PatchCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
import mplhep as mh

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCRoll  # type: ignore


mh.style.use(mh.styles.CMS)


def plot_patches(
    patches: list[Polygon],
    values: npt.NDArray[np.float32],
    draw_mask: Optional[npt.NDArray[np.bool_]] = None,
    excluded_mask: Optional[npt.NDArray[np.bool_]] = None,
    inactive_mask: Optional[npt.NDArray[np.bool_]] = None,
    cmap: Union[Colormap, str] = "RdYlGn",
    edgecolor: str = "black",
    ax: Optional[plt.Axes] = None,
    vmin: Optional[Union[float, np.float32]] = None,
    vmax: Optional[Union[float, np.float32]] = None,
    lw: float = 2,
) -> plt.Figure:
    ax = ax or plt.gca()

    n_patch = len(patches)

    if draw_mask is None:
        draw_mask = np.ones(n_patch, dtype=bool)
    else:
        draw_mask = np.asarray(draw_mask, dtype=bool)

    if excluded_mask is None:
        excluded_mask = np.zeros(n_patch, dtype=bool)
    else:
        excluded_mask = np.asarray(excluded_mask, dtype=bool) & draw_mask

    if inactive_mask is None:
        inactive_mask = np.zeros(n_patch, dtype=bool)
    else:
        inactive_mask = np.asarray(inactive_mask, dtype=bool) & draw_mask & ~excluded_mask

    active_mask = draw_mask & ~excluded_mask & ~inactive_mask

    if vmin is None:
        vmin = np.nanmin(values)
    if vmax is None:
        vmax = np.nanmax(values)

    cmap = plt.get_cmap(cmap)

    denom = vmax - vmin
    if denom == 0:
        normalized_values = np.zeros_like(values, dtype=np.float64)
    else:
        normalized_values = (values - vmin) / denom

    normalized_values = np.clip(normalized_values, 0.0, 1.0)
    normalized_values = np.nan_to_num(
        normalized_values,
        nan=0.0,
        posinf=1.0,
        neginf=0.0,
    )

    if np.any(active_mask):
        active_patches = [patches[i] for i in np.where(active_mask)[0]]
        active_values = normalized_values[active_mask]
        active_colors = cmap(active_values)

        active_collection = PatchCollection(active_patches)
        active_collection.set_facecolor(active_colors)
        active_collection.set_edgecolor(edgecolor)
        active_collection.set_linewidth(lw)
        ax.add_collection(active_collection)

    if np.any(inactive_mask):
        inactive_patches = [patches[i] for i in np.where(inactive_mask)[0]]

        inactive_collection = PatchCollection(inactive_patches)
        inactive_collection.set_facecolor(np.array([0.85, 0.85, 0.85, 1.0], dtype=np.float64))
        inactive_collection.set_edgecolor(edgecolor)
        inactive_collection.set_linewidth(lw)
        ax.add_collection(inactive_collection)

    if np.any(excluded_mask):
        excluded_patches = [patches[i] for i in np.where(excluded_mask)[0]]

        excluded_collection = PatchCollection(excluded_patches)
        excluded_collection.set_facecolor(np.array([0.20, 0.20, 0.20, 1.0], dtype=np.float64))
        excluded_collection.set_edgecolor("black")
        excluded_collection.set_linewidth(lw)
        excluded_collection.set_hatch("////")
        ax.add_collection(excluded_collection)

    ax.autoscale_view()

    scalar_mappable = plt.cm.ScalarMappable(
        cmap=cmap,
        norm=plt.Normalize(vmin=vmin, vmax=vmax),
    )
    scalar_mappable.set_array([])

    axes_divider = make_axes_locatable(ax)
    cax = axes_divider.append_axes("right", size="5%", pad=0.2)
    cax.figure.colorbar(scalar_mappable, cax=cax, pad=0.1)

    return ax.figure


def _resolve_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix != ".root":
            raise ValueError(f"Expected a ROOT file, got: {input_path}")
        return [input_path]

    if input_path.is_dir():
        files = sorted(path for path in input_path.rglob("*.root") if path.is_file())
        if len(files) == 0:
            raise FileNotFoundError(f"No ROOT files found under: {input_path}")
        return files

    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def load_eff_detector(
    input_path: Path,
    geom_path: Path,
):
    input_files = _resolve_input_files(input_path)

    branches = [
        "region", "ring", "station", "sector", "layer", "subsector", "roll",
        "is_fiducial", "is_matched",
    ]

    geom = pd.read_csv(geom_path)
    key_cols = ["region", "ring", "station", "sector", "layer", "subsector", "roll"]
    geom_key = geom[key_cols + ["roll_name"]].drop_duplicates()

    total_by_roll = pd.Series(dtype=np.int64)
    passed_by_roll = pd.Series(dtype=np.int64)

    for each_input_path in input_files:
        with uproot.open(each_input_path) as input_file:
            if "trial_tree" not in input_file:
                raise RuntimeError(f"Missing tree 'trial_tree' in {each_input_path}")

            arrays = input_file["trial_tree"].arrays(branches, library="np")

        trial_df = pd.DataFrame({key: arrays[key] for key in branches})

        trial_df = trial_df.merge(
            geom_key,
            on=key_cols,
            how="left",
            validate="many_to_one",
        )

        missing_mask = trial_df["roll_name"].isna()
        if missing_mask.any():
            missing_rows = trial_df.loc[missing_mask, key_cols].drop_duplicates()
            raise ValueError(
                "Some trial_tree rows could not be matched to geom.csv.\n"
                f"Input file: {each_input_path}\n"
                f"Number of unmatched detector keys: {len(missing_rows)}\n"
                f"Examples:\n{missing_rows.head()}"
            )

        fiducial_mask = trial_df["is_fiducial"].astype(bool).to_numpy()
        passed_mask = (
            trial_df["is_fiducial"].astype(bool).to_numpy()
            & trial_df["is_matched"].astype(bool).to_numpy()
        )

        each_total_by_roll = (
            trial_df.loc[fiducial_mask]
            .groupby("roll_name")
            .size()
            .astype(np.int64)
        )

        each_passed_by_roll = (
            trial_df.loc[passed_mask]
            .groupby("roll_name")
            .size()
            .astype(np.int64)
        )

        total_by_roll = total_by_roll.add(each_total_by_roll, fill_value=0)
        passed_by_roll = passed_by_roll.add(each_passed_by_roll, fill_value=0)

    return total_by_roll.astype(np.int64), passed_by_roll.astype(np.int64)


def is_irpc_roll(roll: RPCRoll) -> bool:
    return (
        abs(int(roll.id.region)) == 1
        and int(roll.id.ring) == 1
        and int(roll.id.station) in (3, 4)
    )


def plot_eff_roll(
    total_by_roll: pd.Series,
    passed_by_roll: pd.Series,
    detector_unit: str,
    roll_list: list[RPCRoll],
    percentage: bool,
    label: str,
    year: Union[int, str],
    com: float,
    lumi: Optional[float],
    output_path: Optional[Path],
    close: bool,
    exclude_eff_below: Optional[float] = None,
    excluded_legend_loc: str = "best",
):
    name_list = [each.id.name for each in roll_list]

    total = total_by_roll.reindex(name_list, fill_value=0).to_numpy(dtype=np.float64)
    passed = passed_by_roll.reindex(name_list, fill_value=0).to_numpy(dtype=np.float64)

    eff = np.divide(
        passed,
        total,
        out=np.zeros_like(total, dtype=np.float64),
        where=(total > 0),
    )
    eff_percent = 100.0 * eff

    patches = [each.polygon for each in roll_list]
    values = eff_percent if percentage else eff

    draw_mask = np.ones_like(total, dtype=bool)
    inactive_roll_mask = total < 1

    excluded_roll_mask = np.zeros_like(total, dtype=bool)
    if exclude_eff_below is not None:
        excluded_roll_mask = (total > 0) & (eff_percent < exclude_eff_below)

    vmin = 0.0
    vmax = 100.0 if percentage else 1.0

    fig, ax = plt.subplots(figsize=(12, 9))
    fig = plot_patches(
        patches=patches,
        values=values,
        draw_mask=draw_mask,
        excluded_mask=excluded_roll_mask,
        inactive_mask=inactive_roll_mask,
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

    cax_ylabel = "Efficiency"
    if percentage:
        cax_ylabel += " [%]"
    cax.set_ylabel(cax_ylabel)
    cax.set_ylim(vmin, vmax)
    ax.set_ylim(None, ymax)

    ax.annotate(
        detector_unit,
        (0.05, 0.925),
        weight="bold",
        xycoords="axes fraction",
    )

    if np.any(excluded_roll_mask):
        excluded_handle = Patch(
            facecolor="0.20",
            edgecolor="black",
            hatch="////",
            label="Excluded",
        )
        ax.legend(
            handles=[excluded_handle],
            frameon=False,
            loc=excluded_legend_loc,
            handlelength=1.2,
            handletextpad=0.4,
            borderaxespad=0.5,
        )

    mh.cms.label(
        ax=ax,
        llabel=label,
        lumi=lumi,
        year=year,
        com=com,
    )

    if output_path is not None:
        fig.savefig(output_path.with_suffix(".png"))

    if close:
        plt.close(fig)

    return fig


def plot_eff_detector(
    input_path: Path,
    geom_path: Path,
    output_dir: Path,
    com: float,
    year: Union[int, str],
    label: str,
    lumi: Optional[float] = None,
    percentage: bool = True,
    roll_blacklist_path: Optional[Path] = None,
    hide_irpc: bool = False,
    exclude_eff_below: Optional[float] = None,
    excluded_legend_loc: str = "best",
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

    if hide_irpc:
        roll_list = [roll for roll in roll_list if not is_irpc_roll(roll)]

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

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
            lumi=lumi,
            output_path=output_path,
            close=True,
            exclude_eff_below=exclude_eff_below,
            excluded_legend_loc=excluded_legend_loc,
        )