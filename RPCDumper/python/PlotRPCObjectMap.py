from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


RECHIT_TREES = [
    "rpcRecHitTree",
    "rpcRecHitPhase2Tree",
]

DIGI_TREES = [
    "rpcDigiTree",
    "rpcDigiPhase2Tree",
    "irpcDigiTree",
]

SUPPORTED_TREES = RECHIT_TREES + DIGI_TREES


@dataclass(frozen=True)
class TreeSpec:
    tree_name: str
    label: str
    marker: str
    size: float
    alpha: float


def detector_unit(region: int, station: int, layer: int) -> str:
    if region == 0:
        if station <= 2:
            return f"RB{station}{'in' if layer == 1 else 'out'}"
        return f"RB{station}"
    return f"RE{region * station:+d}"


def resolve_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = sorted(path.rglob("*.root"))
    if not files:
        raise FileNotFoundError(f"No ROOT files found under: {path}")
    return files


def basename(key: str) -> str:
    return key.split(";")[0].split("/")[-1]


def find_tree_path(file: Path, tree_name: str) -> str | None:
    with uproot.open(file) as f:
        for key in f.keys(recursive=True):
            if basename(key) == tree_name:
                return key.split(";")[0]
    return None


def get_available_trees(
    input_path: Path,
    allowed_trees: list[str] | None = None,
) -> list[str]:
    target_trees = SUPPORTED_TREES if allowed_trees is None else allowed_trees
    found = set()

    for file in resolve_input_files(input_path):
        with uproot.open(file) as f:
            for key in f.keys(recursive=True):
                name = basename(key)
                if name in target_trees:
                    found.add(name)

    return [name for name in target_trees if name in found]


def load_geometry(geom_path: Path) -> list[RPCRoll]:
    df = pd.read_csv(geom_path)
    return [RPCRoll.from_row(row) for _, row in df.iterrows()]


def group_rolls_by_unit(rolls: list[RPCRoll]) -> dict[str, list[RPCRoll]]:
    out: dict[str, list[RPCRoll]] = {}
    for roll in rolls:
        out.setdefault(roll.id.detector_unit, []).append(roll)
    return out


def load_points(input_path: Path, tree_name: str) -> dict[str, np.ndarray]:
    branches = [
        "region",
        "ring",
        "station",
        "sector",
        "layer",
        "subsector",
        "roll",
        "global_x",
        "global_y",
        "global_z",
    ]

    parts: dict[str, list[np.ndarray]] = {name: [] for name in branches}

    for file in resolve_input_files(input_path):
        tree_path = find_tree_path(file, tree_name)
        if tree_path is None:
            continue

        with uproot.open(file) as f:
            arr = f[tree_path].arrays(branches, library="np")

        for name in branches:
            parts[name].append(arr[name])

    if not parts["region"]:
        empty_f = np.asarray([], dtype=np.float64)
        empty_i = np.asarray([], dtype=np.int32)
        empty_o = np.asarray([], dtype=object)
        return {
            "unit": empty_o,
            "global_x": empty_f,
            "global_y": empty_f,
            "global_z": empty_f,
            "region": empty_i,
            "ring": empty_i,
            "station": empty_i,
            "sector": empty_i,
            "layer": empty_i,
            "subsector": empty_i,
            "roll": empty_i,
        }

    out = {name: np.concatenate(parts[name]) for name in branches}

    region = out["region"].astype(np.int32)
    station = out["station"].astype(np.int32)
    layer = out["layer"].astype(np.int32)

    unit = np.asarray(
        [detector_unit(int(r), int(s), int(l)) for r, s, l in zip(region, station, layer)],
        dtype=object,
    )

    return {
        "unit": unit,
        "global_x": out["global_x"].astype(np.float64),
        "global_y": out["global_y"].astype(np.float64),
        "global_z": out["global_z"].astype(np.float64),
        "region": region,
        "ring": out["ring"].astype(np.int32),
        "station": station,
        "sector": out["sector"].astype(np.int32),
        "layer": layer,
        "subsector": out["subsector"].astype(np.int32),
        "roll": out["roll"].astype(np.int32),
    }


def barrel_phi(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    phi = np.arctan2(y, x)
    phi[phi < 0] += 2.0 * np.pi
    if len(phi) >= 3 and abs(phi[0] - phi[2]) > np.pi:
        phi[phi > np.pi] -= 2.0 * np.pi
    return phi


def project_points(
    is_barrel: bool,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if is_barrel:
        return z, barrel_phi(x, y)
    return x, y


def draw_geometry(ax: plt.Axes, rolls: list[RPCRoll]) -> None:
    patches = [roll.polygon for roll in rolls]
    ax.add_collection(
        PatchCollection(
            patches,
            facecolor="0.96",
            edgecolor="black",
            linewidth=1.0,
        )
    )
    ax.autoscale_view()
    ax.set_xlabel(rolls[0].polygon_xlabel)
    ax.set_ylabel(rolls[0].polygon_ylabel)
    if rolls[0].polygon_ymax is not None:
        ax.set_ylim(None, rolls[0].polygon_ymax)


def run_geometry_plotting(
    geom_path: Path,
    output_dir: Path,
    label: str = "Phase2 Simulation Private Work",
    year: str = "",
    com: float = 14,
    lumi: float | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    rolls_by_unit = group_rolls_by_unit(load_geometry(geom_path))

    for unit, rolls in rolls_by_unit.items():
        fig, ax = plt.subplots(figsize=(12, 9))
        draw_geometry(ax, rolls)

        ax.annotate(
            unit,
            (0.05, 0.93),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=12,
            weight="bold",
        )

        mh.cms.label(ax=ax, llabel=label, lumi=lumi, year=year, com=com)
        fig.savefig(output_dir / f"{unit}.png", dpi=150)
        plt.close(fig)


def run_scatter_plotting(
    input_path: Path,
    geom_path: Path,
    output_dir: Path,
    tree_specs: list[TreeSpec],
    label: str = "Phase2 Simulation Private Work",
    year: str = "",
    com: float = 14,
    lumi: float | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    rolls_by_unit = group_rolls_by_unit(load_geometry(geom_path))
    points_by_tree = {
        spec.tree_name: load_points(input_path, spec.tree_name)
        for spec in tree_specs
    }

    for unit, rolls in rolls_by_unit.items():
        fig, ax = plt.subplots(figsize=(12, 9))
        draw_geometry(ax, rolls)

        drawn = 0
        is_barrel = unit.startswith("RB")

        for spec in tree_specs:
            arr = points_by_tree[spec.tree_name]

            mask = (
                (arr["unit"] == unit)
                & np.isfinite(arr["global_x"])
                & np.isfinite(arr["global_y"])
                & np.isfinite(arr["global_z"])
            )

            if not np.any(mask):
                continue

            xp, yp = project_points(
                is_barrel,
                arr["global_x"][mask],
                arr["global_y"][mask],
                arr["global_z"][mask],
            )

            ax.scatter(
                xp,
                yp,
                s=spec.size,
                alpha=spec.alpha,
                marker=spec.marker,
                label=f"{spec.label} ({len(xp)})",
            )
            drawn += 1

        ax.annotate(
            unit,
            (0.05, 0.93),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=12,
            weight="bold",
        )

        if drawn > 0:
            ax.legend(loc="upper right", fontsize=11, frameon=True)

        mh.cms.label(ax=ax, llabel=label, lumi=lumi, year=year, com=com)
        fig.savefig(output_dir / f"{unit}.png", dpi=150)
        plt.close(fig)