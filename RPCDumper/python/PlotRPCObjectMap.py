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
    "rpcRecHitsTree",
    "rpcRecHitsPhase2Tree",
]

DIGI_TREES = [
    "simMuonRPCDigisTree",
    "simMuonRPCDigisPhase2Tree",
    "simMuonIRPCDigisTree",
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

    files = sorted(each for each in path.rglob("*.root") if each.is_file())

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


def make_roll_key_arrays(
    region: np.ndarray,
    ring: np.ndarray,
    station: np.ndarray,
    sector: np.ndarray,
    layer: np.ndarray,
    subsector: np.ndarray,
    roll: np.ndarray,
) -> np.ndarray:
    return np.rec.fromarrays(
        [
            region.astype(np.int32),
            ring.astype(np.int32),
            station.astype(np.int32),
            sector.astype(np.int32),
            layer.astype(np.int32),
            subsector.astype(np.int32),
            roll.astype(np.int32),
        ],
        names=[
            "region",
            "ring",
            "station",
            "sector",
            "layer",
            "subsector",
            "roll",
        ],
    )


def roll_key_to_tuple(key) -> tuple[int, int, int, int, int, int, int]:
    return (
        int(key["region"]),
        int(key["ring"]),
        int(key["station"]),
        int(key["sector"]),
        int(key["layer"]),
        int(key["subsector"]),
        int(key["roll"]),
    )


def build_roll_phi_center_map(
    rolls: list[RPCRoll],
) -> dict[tuple[int, int, int, int, int, int, int], float]:
    out: dict[tuple[int, int, int, int, int, int, int], float] = {}

    for each in rolls:
        key = (
            int(each.id.region),
            int(each.id.ring),
            int(each.id.station),
            int(each.id.sector),
            int(each.id.layer),
            int(each.id.subsector),
            int(each.id.roll),
        )

        if each.id.barrel:
            phi_center = float(np.mean(each.phi))
            out[key] = phi_center

    return out


def pick_branch(available: set[str], candidates: list[str]) -> str | None:
    for name in candidates:
        if name in available:
            return name

    return None


def empty_points() -> dict[str, np.ndarray]:
    empty_f = np.asarray([], dtype=np.float64)
    empty_i = np.asarray([], dtype=np.int32)
    empty_o = np.asarray([], dtype=object)

    empty_key = np.rec.fromarrays(
        [empty_i, empty_i, empty_i, empty_i, empty_i, empty_i, empty_i],
        names=["region", "ring", "station", "sector", "layer", "subsector", "roll"],
    )

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
        "roll_key": empty_key,
    }


def load_points(input_path: Path, tree_name: str) -> dict[str, np.ndarray]:
    output_names = [
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

    parts: dict[str, list[np.ndarray]] = {name: [] for name in output_names}

    for file in resolve_input_files(input_path):
        tree_path = find_tree_path(file, tree_name)
        if tree_path is None:
            continue

        with uproot.open(file) as f:
            tree = f[tree_path]
            available = set(tree.keys())

            branch_map = {
                "region": pick_branch(available, ["region"]),
                "ring": pick_branch(available, ["ring"]),
                "station": pick_branch(available, ["station"]),
                "sector": pick_branch(available, ["sector"]),
                "layer": pick_branch(available, ["layer"]),
                "subsector": pick_branch(available, ["subsector"]),
                "roll": pick_branch(available, ["roll"]),
                "global_x": pick_branch(available, ["global_x", "rechit_global_x"]),
                "global_y": pick_branch(available, ["global_y", "rechit_global_y"]),
                "global_z": pick_branch(available, ["global_z", "rechit_global_z"]),
            }

            missing = [name for name, branch in branch_map.items() if branch is None]
            if missing:
                print(
                    f"[warning] skip map points for {tree_name} in {file}: "
                    f"missing branches = {', '.join(missing)}"
                )
                continue

            read_branches = list(branch_map.values())
            arr = tree.arrays(read_branches, library="np")

            for name in output_names:
                parts[name].append(arr[branch_map[name]])

    if len(parts["region"]) == 0:
        return empty_points()

    out = {name: np.concatenate(parts[name]) for name in output_names}

    region = out["region"].astype(np.int32)
    ring = out["ring"].astype(np.int32)
    station = out["station"].astype(np.int32)
    sector = out["sector"].astype(np.int32)
    layer = out["layer"].astype(np.int32)
    subsector = out["subsector"].astype(np.int32)
    roll = out["roll"].astype(np.int32)

    unit = np.asarray(
        [
            detector_unit(int(r), int(s), int(l))
            for r, s, l in zip(region, station, layer)
        ],
        dtype=object,
    )

    roll_key = make_roll_key_arrays(
        region=region,
        ring=ring,
        station=station,
        sector=sector,
        layer=layer,
        subsector=subsector,
        roll=roll,
    )

    return {
        "unit": unit,
        "global_x": out["global_x"].astype(np.float64),
        "global_y": out["global_y"].astype(np.float64),
        "global_z": out["global_z"].astype(np.float64),
        "region": region,
        "ring": ring,
        "station": station,
        "sector": sector,
        "layer": layer,
        "subsector": subsector,
        "roll": roll,
        "roll_key": roll_key,
    }


def wrap_phi_to_reference(phi: np.ndarray, phi_ref: float) -> np.ndarray:
    wrapped = phi.copy()

    delta = wrapped - phi_ref
    wrapped[delta > np.pi] -= 2.0 * np.pi
    wrapped[delta < -np.pi] += 2.0 * np.pi

    return wrapped


def compute_barrel_phi_from_rolls(
    x: np.ndarray,
    y: np.ndarray,
    roll_keys: np.ndarray,
    phi_center_map: dict[tuple[int, int, int, int, int, int, int], float],
) -> np.ndarray:
    phi = np.arctan2(y, x)
    phi[phi < 0] += 2.0 * np.pi

    if len(phi) == 0:
        return phi

    out = phi.copy()

    unique_keys, inverse = np.unique(roll_keys, return_inverse=True)

    for idx, key in enumerate(unique_keys):
        key_tuple = roll_key_to_tuple(key)
        phi_ref = phi_center_map.get(key_tuple)

        if phi_ref is None:
            continue

        mask = inverse == idx
        out[mask] = wrap_phi_to_reference(out[mask], phi_ref)

    return out


def project_points(
    is_barrel: bool,
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    roll_keys: np.ndarray | None = None,
    phi_center_map: dict[tuple[int, int, int, int, int, int, int], float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if is_barrel:
        if roll_keys is None or phi_center_map is None:
            raise ValueError("roll_keys and phi_center_map are required for barrel projection")

        phi = compute_barrel_phi_from_rolls(
            x=x,
            y=y,
            roll_keys=roll_keys,
            phi_center_map=phi_center_map,
        )

        return z, phi

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

    rolls = load_geometry(geom_path)
    rolls_by_unit = group_rolls_by_unit(rolls)

    for unit, each_rolls in rolls_by_unit.items():
        fig, ax = plt.subplots(figsize=(12, 9))

        draw_geometry(ax, each_rolls)

        ax.annotate(
            unit,
            (0.05, 0.925),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=20,
            weight="bold",
        )

        mh.cms.label(
            ax=ax,
            llabel=label,
            lumi=lumi,
            year=year,
            com=com,
        )

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

    all_rolls = load_geometry(geom_path)
    rolls_by_unit = group_rolls_by_unit(all_rolls)
    phi_center_map = build_roll_phi_center_map(all_rolls)

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
                is_barrel=is_barrel,
                x=arr["global_x"][mask],
                y=arr["global_y"][mask],
                z=arr["global_z"][mask],
                roll_keys=arr["roll_key"][mask],
                phi_center_map=phi_center_map if is_barrel else None,
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
            (0.05, 0.925),
            xycoords="axes fraction",
            va="top",
            ha="left",
            fontsize=20,
            weight="bold",
        )

        if drawn > 0:
            ax.legend(loc="upper right", fontsize=18, frameon=True)

        mh.cms.label(
            ax=ax,
            llabel=label,
            lumi=lumi,
            year=year,
            com=com,
        )

        fig.savefig(output_dir / f"{unit}.png", dpi=150)
        plt.close(fig)