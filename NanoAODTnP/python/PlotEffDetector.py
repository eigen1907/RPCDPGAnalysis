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


ROLL_KEY_DTYPE = np.dtype([
    ("region", np.int16),
    ("ring", np.int16),
    ("station", np.int16),
    ("sector", np.int16),
    ("layer", np.int16),
    ("subsector", np.int16),
    ("roll", np.int16),
])


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


def make_roll_key_array_from_arrays(arrays: dict[str, np.ndarray]) -> np.ndarray:
    out = np.empty(len(arrays["region"]), dtype=ROLL_KEY_DTYPE)
    out["region"] = np.asarray(arrays["region"], dtype=np.int16)
    out["ring"] = np.asarray(arrays["ring"], dtype=np.int16)
    out["station"] = np.asarray(arrays["station"], dtype=np.int16)
    out["sector"] = np.asarray(arrays["sector"], dtype=np.int16)
    out["layer"] = np.asarray(arrays["layer"], dtype=np.int16)
    out["subsector"] = np.asarray(arrays["subsector"], dtype=np.int16)
    out["roll"] = np.asarray(arrays["roll"], dtype=np.int16)
    return out


def make_roll_key_tuples_from_arrays(
    arrays: dict[str, np.ndarray],
) -> list[tuple[int, int, int, int, int, int, int]]:
    return list(zip(
        np.asarray(arrays["region"], dtype=np.int16).tolist(),
        np.asarray(arrays["ring"], dtype=np.int16).tolist(),
        np.asarray(arrays["station"], dtype=np.int16).tolist(),
        np.asarray(arrays["sector"], dtype=np.int16).tolist(),
        np.asarray(arrays["layer"], dtype=np.int16).tolist(),
        np.asarray(arrays["subsector"], dtype=np.int16).tolist(),
        np.asarray(arrays["roll"], dtype=np.int16).tolist(),
    ))


def build_geom_roll_name_map(
    geom: pd.DataFrame,
) -> dict[tuple[int, int, int, int, int, int, int], str]:
    key_cols = ["region", "ring", "station", "sector", "layer", "subsector", "roll"]
    geom_key = geom[key_cols + ["roll_name"]].drop_duplicates()

    geom_arrays = {
        "region": geom_key["region"].to_numpy(np.int16),
        "ring": geom_key["ring"].to_numpy(np.int16),
        "station": geom_key["station"].to_numpy(np.int16),
        "sector": geom_key["sector"].to_numpy(np.int16),
        "layer": geom_key["layer"].to_numpy(np.int16),
        "subsector": geom_key["subsector"].to_numpy(np.int16),
        "roll": geom_key["roll"].to_numpy(np.int16),
    }
    geom_keys = make_roll_key_tuples_from_arrays(geom_arrays)
    roll_names = geom_key["roll_name"].to_numpy(dtype=object)

    return {key: name for key, name in zip(geom_keys, roll_names)}


def map_roll_keys_to_names(
    roll_keys: np.ndarray,
    roll_name_map: dict[tuple[int, int, int, int, int, int, int], str],
    input_file: Path,
) -> np.ndarray:
    unique_keys, inverse = np.unique(roll_keys, return_inverse=True)

    unique_key_tuples = [
        (
            int(key["region"]),
            int(key["ring"]),
            int(key["station"]),
            int(key["sector"]),
            int(key["layer"]),
            int(key["subsector"]),
            int(key["roll"]),
        )
        for key in unique_keys
    ]

    unique_names = []
    missing_keys = []

    for key_tuple in unique_key_tuples:
        name = roll_name_map.get(key_tuple)
        if name is None:
            missing_keys.append(key_tuple)
            unique_names.append(None)
        else:
            unique_names.append(name)

    if len(missing_keys) > 0:
        missing_rows = pd.DataFrame(
            missing_keys,
            columns=["region", "ring", "station", "sector", "layer", "subsector", "roll"],
        )
        raise ValueError(
            "Some trial_tree rows could not be matched to geom.csv.\n"
            f"Input file: {input_file}\n"
            f"Number of unmatched detector keys: {len(missing_keys)}\n"
            f"Examples:\n{missing_rows.head()}"
        )

    unique_names = np.asarray(unique_names, dtype=object)
    return unique_names[inverse]


def count_names(values: np.ndarray) -> pd.Series:
    if len(values) == 0:
        return pd.Series(dtype=np.int64)

    unique_names, counts = np.unique(values, return_counts=True)
    return pd.Series(counts.astype(np.int64), index=unique_names)


def load_eff_detector(
    input_path: Path,
    geom: pd.DataFrame,
):
    input_files = _resolve_input_files(input_path)

    branches = [
        "region", "ring", "station", "sector", "layer", "subsector", "roll",
        "is_fiducial", "is_matched",
    ]

    roll_name_map = build_geom_roll_name_map(geom)

    total_by_roll = pd.Series(dtype=np.int64)
    passed_by_roll = pd.Series(dtype=np.int64)

    for each_input_path in input_files:
        with uproot.open(each_input_path) as input_file:
            if "trial_tree" not in input_file:
                raise RuntimeError(f"Missing tree 'trial_tree' in {each_input_path}")

            arrays = input_file["trial_tree"].arrays(branches, library="np")

        roll_keys = make_roll_key_array_from_arrays(arrays)
        roll_names = map_roll_keys_to_names(
            roll_keys=roll_keys,
            roll_name_map=roll_name_map,
            input_file=each_input_path,
        )

        fiducial_mask = np.asarray(arrays["is_fiducial"], dtype=bool)
        passed_mask = fiducial_mask & np.asarray(arrays["is_matched"], dtype=bool)

        each_total_by_roll = count_names(roll_names[fiducial_mask])
        each_passed_by_roll = count_names(roll_names[passed_mask])

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

    geom = pd.read_csv(geom_path)

    total_by_roll, passed_by_roll = load_eff_detector(
        input_path=input_path,
        geom=geom,
    )

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