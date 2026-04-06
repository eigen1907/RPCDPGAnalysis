from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
import uproot

import matplotlib as mpl
mpl.use("agg")

import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
import mplhep as mh

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCRoll  # type: ignore


mh.style.use(mh.styles.CMS)


SUPPORTED_TREES = [
    "rpcRecHitTree",
    "rpcRecHitPhase2Tree",
    "rpcDigiTree",
    "rpcDigiPhase2Tree",
    "irpcDigiTree",
]


@dataclass(frozen=True)
class TreeSpec:
    tree_name: str
    label: str
    marker: str = "."
    size: float = 4.0
    alpha: float = 1.0


def _resolve_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.rglob("*.root"))


def _strip_cycle(name: str) -> str:
    return name.split(";")[0]


def _basename(name: str) -> str:
    return _strip_cycle(name).split("/")[-1]


def get_available_trees(input_path: Path) -> list[str]:
    input_file = _resolve_input_files(input_path)[0]

    with uproot.open(input_file) as f:
        names = []
        for key, cls in f.classnames(recursive=True).items():
            if "TTree" not in cls:
                continue
            name = _basename(key)
            if name in SUPPORTED_TREES:
                names.append(name)

    return names


def _find_tree_path(input_file: Path, tree_name: str) -> str:
    with uproot.open(input_file) as f:
        for key, cls in f.classnames(recursive=True).items():
            if "TTree" not in cls:
                continue
            path = _strip_cycle(key)
            if _basename(path) == tree_name:
                return path

    raise RuntimeError(f"Tree not found: {tree_name}")


def _to_string_array(values: np.ndarray) -> np.ndarray:
    out = []
    for value in values:
        if isinstance(value, bytes):
            out.append(value.decode())
        else:
            out.append(str(value))
    return np.asarray(out, dtype=object)


def load_geometry(geom_path: Path) -> list[RPCRoll]:
    geom = pd.read_csv(geom_path)
    return [RPCRoll.from_row(row) for _, row in geom.iterrows()]


def load_tree_points(
    input_path: Path,
    tree_name: str,
) -> dict[str, np.ndarray]:
    branches = ["roll_name", "global_x", "global_y", "global_z"]
    out = {branch: [] for branch in branches}

    for input_file in _resolve_input_files(input_path):
        tree_path = _find_tree_path(input_file, tree_name)
        with uproot.open(input_file) as f:
            arrays = f[tree_path].arrays(branches, library="np")

        for branch in branches:
            out[branch].append(arrays[branch])

    merged = {
        branch: parts[0] if len(parts) == 1 else np.concatenate(parts, axis=0)
        for branch, parts in out.items()
    }

    merged["roll_name"] = _to_string_array(merged["roll_name"])
    merged["global_x"] = np.asarray(merged["global_x"], dtype=np.float64)
    merged["global_y"] = np.asarray(merged["global_y"], dtype=np.float64)
    merged["global_z"] = np.asarray(merged["global_z"], dtype=np.float64)

    return merged


def group_rolls_by_detector_unit(roll_list: list[RPCRoll]) -> dict[str, list[RPCRoll]]:
    out: dict[str, list[RPCRoll]] = defaultdict(list)
    for roll in roll_list:
        out[roll.id.detector_unit].append(roll)
    return out


def draw_geometry(
    ax: plt.Axes,
    patches: list,
    facecolor: str = "0.96",
    edgecolor: str = "black",
    linewidth: float = 1.0,
) -> None:
    collection = PatchCollection(patches)
    collection.set_facecolor(facecolor)
    collection.set_edgecolor(edgecolor)
    collection.set_linewidth(linewidth)
    ax.add_collection(collection)
    ax.autoscale_view()


def set_detector_axes(ax: plt.Axes, unit_rolls: list[RPCRoll]) -> None:
    ax.set_xlabel(unit_rolls[0].polygon_xlabel)
    ax.set_ylabel(unit_rolls[0].polygon_ylabel)
    ax.set_ylim(None, unit_rolls[0].polygon_ymax)


def _is_barrel_unit(detector_unit: str) -> bool:
    return detector_unit.startswith("W")


def _project_points_for_unit(
    detector_unit: str,
    unit_rolls: list[RPCRoll],
    global_x: np.ndarray,
    global_y: np.ndarray,
    global_z: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if _is_barrel_unit(detector_unit):
        x_plot = global_z
        y_plot = np.arctan2(global_y, global_x)

        ymax = float(unit_rolls[0].polygon_ymax)
        if abs(ymax) > 10.0:
            y_plot = np.degrees(y_plot)

        return x_plot, y_plot

    return global_x, global_y


def plot_detector_geometry_map(
    roll_list: list[RPCRoll],
    output_dir: Path,
    label: str,
    year: Union[int, str],
    com: float,
    lumi: float | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for detector_unit, unit_rolls in group_rolls_by_detector_unit(roll_list).items():
        patches = [roll.polygon for roll in unit_rolls]

        fig, ax = plt.subplots(figsize=(12, 9))
        draw_geometry(ax, patches)
        set_detector_axes(ax, unit_rolls)

        ax.annotate(
            f"{detector_unit}\nRolls: {len(unit_rolls)}",
            (0.05, 0.93),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=12,
            weight="bold",
        )

        mh.cms.label(ax=ax, llabel=label, lumi=lumi, year=year, com=com)
        fig.savefig(output_dir / f"{detector_unit}.png", dpi=150)
        plt.close(fig)


def plot_detector_scatter_overlay(
    roll_list: list[RPCRoll],
    tree_points: dict[str, dict[str, np.ndarray]],
    tree_specs: list[TreeSpec],
    output_dir: Path,
    label: str,
    year: Union[int, str],
    com: float,
    lumi: float | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for detector_unit, unit_rolls in group_rolls_by_detector_unit(roll_list).items():
        roll_names = {roll.id.name for roll in unit_rolls}
        patches = [roll.polygon for roll in unit_rolls]

        fig, ax = plt.subplots(figsize=(12, 9))
        draw_geometry(ax, patches)
        set_detector_axes(ax, unit_rolls)

        n_drawn = 0

        for spec in tree_specs:
            arrays = tree_points[spec.tree_name]

            mask = np.isin(arrays["roll_name"], list(roll_names))
            mask = (
                mask
                & np.isfinite(arrays["global_x"])
                & np.isfinite(arrays["global_y"])
                & np.isfinite(arrays["global_z"])
            )

            if not np.any(mask):
                continue

            x_plot, y_plot = _project_points_for_unit(
                detector_unit=detector_unit,
                unit_rolls=unit_rolls,
                global_x=arrays["global_x"][mask],
                global_y=arrays["global_y"][mask],
                global_z=arrays["global_z"][mask],
            )

            ax.scatter(
                x_plot,
                y_plot,
                s=spec.size,
                alpha=spec.alpha,
                marker=spec.marker,
                label=f"{spec.label} ({len(x_plot)})",
            )
            n_drawn += 1

        ax.annotate(
            detector_unit,
            (0.05, 0.93),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=12,
            weight="bold",
        )

        if n_drawn > 0:
            ax.legend(loc="upper right", fontsize=11, frameon=True)

        mh.cms.label(ax=ax, llabel=label, lumi=lumi, year=year, com=com)
        fig.savefig(output_dir / f"{detector_unit}.png", dpi=150)
        plt.close(fig)


def run_geometry_plotting(
    geom_path: Path,
    output_dir: Path,
    label: str = "Phase2 Simulation Private Work",
    year: Union[int, str] = "",
    com: float = 14,
    lumi: float | None = None,
) -> None:
    roll_list = load_geometry(geom_path)
    plot_detector_geometry_map(
        roll_list=roll_list,
        output_dir=output_dir,
        label=label,
        year=year,
        com=com,
        lumi=lumi,
    )


def run_scatter_plotting(
    input_path: Path,
    geom_path: Path,
    output_dir: Path,
    tree_specs: list[TreeSpec],
    label: str = "Phase2 Simulation Private Work",
    year: Union[int, str] = "",
    com: float = 14,
    lumi: float | None = None,
) -> None:
    roll_list = load_geometry(geom_path)

    tree_points = {
        spec.tree_name: load_tree_points(input_path, spec.tree_name)
        for spec in tree_specs
    }

    plot_detector_scatter_overlay(
        roll_list=roll_list,
        tree_points=tree_points,
        tree_specs=tree_specs,
        output_dir=output_dir,
        label=label,
        year=year,
        com=com,
        lumi=lumi,
    )