from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import hist
import numpy as np
import uproot

from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import load_roll_blacklist  # type: ignore


PACKAGE_DIR = Path(__file__).resolve().parents[1]
RUN_CATEGORY_PATH = PACKAGE_DIR / "data" / "lumi" / "run3.csv"
ROLL_CATEGORY_PATH = PACKAGE_DIR / "data" / "geometry" / "run3.csv"
HISTOGRAM_COMPRESSION = uproot.ZLIB(1)
PAIR_MASS_HISTOGRAM = "count_pair_mass"
STATION_NAMES = (
    "RB1in", "RB1out", "RB2in", "RB2out", "RB3", "RB4",
    "RE-1", "RE-2", "RE-3", "RE-4",
    "RE+1", "RE+2", "RE+3", "RE+4",
)


@lru_cache(maxsize=1)
def run_categories() -> tuple[int, ...]:
    with RUN_CATEGORY_PATH.open(newline="") as stream:
        return tuple(sorted({
            int(row[0].split(":", 1)[0])
            for row in csv.reader(stream)
            if row and not row[0].lstrip().startswith("#")
        }))


@lru_cache(maxsize=1)
def roll_geometry() -> dict[str, str]:
    geometry = {}
    with ROLL_CATEGORY_PATH.open(newline="") as stream:
        for row in csv.DictReader(stream):
            roll_name = str(row["roll_name"]).strip()
            region = int(row["region"])
            station = int(row["station"])

            if region == 0 and station in (1, 2):
                suffix = "in" if int(row["layer"]) == 1 else "out"
                station_name = f"RB{station}{suffix}"
            elif region == 0:
                station_name = f"RB{station}"
            else:
                station_name = f"RE{region * station:+d}"

            geometry[roll_name] = station_name
    return geometry


@lru_cache(maxsize=1)
def roll_names() -> tuple[str, ...]:
    return tuple(sorted(roll_geometry()))


def regular_edges(low: float, high: float, n_bins: int) -> np.ndarray:
    return np.linspace(low, high, n_bins + 1, dtype=np.float64)


def integer_edges(low: int, high: int) -> np.ndarray:
    return np.arange(low - 0.5, high + 1.5, 1.0, dtype=np.float64)


PAIR_MASS_EDGES = regular_edges(70.0, 110.0, 160)
PAIR_MUON_PT_EDGES = regular_edges(0.0, 100.0, 100)
PROBE_ETA_EDGES = regular_edges(-2.1, 2.1, 168)
TAG_ETA_EDGES = regular_edges(-2.4, 2.4, 192)
RPC_CLS_EDGES = integer_edges(1, 10)
RPC_BX_EDGES = integer_edges(-4, 4)
RPC_PT_EDGES = regular_edges(0.0, 100.0, 100)
RPC_P_EDGES = regular_edges(0.0, 200.0, 200)
RPC_DXDZ_EDGES = regular_edges(-1.0, 1.0, 200)
RPC_ABS_DXDZ_EDGES = regular_edges(0.0, 1.0, 100)
RPC_RESIDUAL_X_EDGES = regular_edges(-20.0, 20.0, 200)
ABS_DXDZ_AXIS = "abs_probe_at_rpc_dxdz"
FIDUCIAL_SELECTION = "fiducial"
MATCHED_SELECTION = "fiducial_matched"
CLS_RUN_STATION_PROFILE = f"profile_rpc_{MATCHED_SELECTION}_cls_by_run_station"

RPC_AXIS_EDGES = {
    "probe_pt": RPC_PT_EDGES,
    "probe_at_rpc_pt": RPC_PT_EDGES,
    "probe_p": RPC_P_EDGES,
    "probe_at_rpc_p": RPC_P_EDGES,
    "residual_x": RPC_RESIDUAL_X_EDGES,
    "probe_at_rpc_dxdz": RPC_DXDZ_EDGES,
    ABS_DXDZ_AXIS: RPC_ABS_DXDZ_EDGES,
    "bx": RPC_BX_EDGES,
    "cls": RPC_CLS_EDGES,
}
RPC_SELECTIONS = (FIDUCIAL_SELECTION, MATCHED_SELECTION)
CLS_PROFILE_BRANCHES = (
    "probe_pt", "probe_at_rpc_pt", "probe_p", "probe_at_rpc_p", ABS_DXDZ_AXIS,
)
ROLL_PROFILE_BRANCHES = ("probe_pt", "probe_at_rpc_pt", "probe_p", "probe_at_rpc_p", "cls", "bx")
PROBE_ROLL_PROFILES = tuple(name for name in ROLL_PROFILE_BRANCHES if name not in ("cls", "bx"))
ONE_DIMENSIONAL_PROFILES = {
    "delta_pt": "probe_pt",
    "delta_p": "probe_p",
}


def pair_kinematics_name(prefix: str) -> str:
    return f"count_pair_{prefix}_pt_eta"


def count_station_name(selection: str, branch: str) -> str:
    return f"count_rpc_{selection}_{branch}_by_station"


def count_roll_name(selection: str) -> str:
    return f"count_rpc_{selection}_by_roll"


def count_run_station_name(selection: str) -> str:
    return f"count_rpc_{selection}_by_run_station"


def profile_roll_name(sample: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_{sample}_by_roll"


def cls_profile_station_name(branch: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_cls_by_{branch}_station"


def profile_1d_name(sample: str, branch: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_{sample}_by_{branch}"


def _histogram_names() -> tuple[str, ...]:
    names = [PAIR_MASS_HISTOGRAM, pair_kinematics_name("probe"), pair_kinematics_name("tag")]
    for selection in RPC_SELECTIONS:
        names.extend(count_station_name(selection, branch) for branch in RPC_AXIS_EDGES)
        names.extend((count_roll_name(selection), count_run_station_name(selection)))
    names.extend(profile_roll_name(sample) for sample in ROLL_PROFILE_BRANCHES)
    names.extend(profile_1d_name(sample, branch) for sample, branch in ONE_DIMENSIONAL_PROFILES.items())
    names.extend(cls_profile_station_name(branch) for branch in CLS_PROFILE_BRANCHES)
    names.append(CLS_RUN_STATION_PROFILE)
    return tuple(sorted(names))


HISTOGRAM_NAMES = _histogram_names()


def _category_coordinates(values: np.ndarray, categories: tuple) -> np.ndarray:
    index_by_category = {category: index + 0.5 for index, category in enumerate(categories)}
    return np.asarray([index_by_category[value] for value in values], dtype=np.float64)


def _hist1d(name: str, axis_name: str, edges: np.ndarray, values: np.ndarray, mask: np.ndarray, weights: np.ndarray | None = None):
    values = np.asarray(values, dtype=np.float64)
    selected = np.asarray(mask, dtype=bool) & np.isfinite(values)
    storage = hist.storage.Double()
    if weights is not None:
        weights = np.asarray(weights, dtype=np.float64)
        selected &= np.isfinite(weights)
        storage = hist.storage.Weight()
    histogram = hist.Hist(hist.axis.Variable(edges, name=axis_name, label=axis_name), storage=storage, name=name)
    histogram.fill(values[selected], weight=None if weights is None else weights[selected])
    return histogram


def _hist2d(name: str, x_name: str, x_edges: np.ndarray, x_values: np.ndarray, y_name: str, y_edges: np.ndarray, y_values: np.ndarray, mask: np.ndarray, weights: np.ndarray | None = None):
    x_values = np.asarray(x_values, dtype=np.float64)
    y_values = np.asarray(y_values, dtype=np.float64)
    selected = np.asarray(mask, dtype=bool) & np.isfinite(x_values) & np.isfinite(y_values)
    storage = hist.storage.Double()
    if weights is not None:
        weights = np.asarray(weights, dtype=np.float64)
        selected &= np.isfinite(weights)
        storage = hist.storage.Weight()
    histogram = hist.Hist(
        hist.axis.Variable(x_edges, name=x_name, label=x_name),
        hist.axis.Variable(y_edges, name=y_name, label=y_name),
        storage=storage,
        name=name,
    )
    histogram.fill(x_values[selected], y_values[selected], weight=None if weights is None else weights[selected])
    return histogram


def build_histograms(pair_tree: dict[str, np.ndarray], rpc_tree: dict[str, np.ndarray], roll_blacklist_path: Path) -> dict[str, hist.Hist]:
    output: dict[str, hist.Hist] = {}
    rpc_values = {branch: np.asarray(rpc_tree[branch]) for branch in RPC_AXIS_EDGES if branch != ABS_DXDZ_AXIS}
    rpc_values[ABS_DXDZ_AXIS] = np.abs(rpc_values["probe_at_rpc_dxdz"])
    rpc_values["delta_pt"] = rpc_values["probe_pt"] - rpc_values["probe_at_rpc_pt"]
    rpc_values["delta_p"] = rpc_values["probe_p"] - rpc_values["probe_at_rpc_p"]

    pair_mask = np.ones(len(pair_tree["pair_mass"]), dtype=bool)
    output[PAIR_MASS_HISTOGRAM] = _hist1d(PAIR_MASS_HISTOGRAM, "pair_mass", PAIR_MASS_EDGES, pair_tree["pair_mass"], pair_mask)
    for prefix, eta_edges in (("probe", PROBE_ETA_EDGES), ("tag", TAG_ETA_EDGES)):
        name = pair_kinematics_name(prefix)
        output[name] = _hist2d(name, f"{prefix}_pt", PAIR_MUON_PT_EDGES, pair_tree[f"{prefix}_pt"], f"{prefix}_eta", eta_edges, pair_tree[f"{prefix}_eta"], pair_mask)

    roll_name_values = np.asarray(rpc_tree["roll_name"], dtype=str)
    geometry = roll_geometry()
    roll_categories = roll_names()
    run_category_values = run_categories()
    station_index = {station: index + 0.5 for index, station in enumerate(STATION_NAMES)}
    roll_values = _category_coordinates(roll_name_values, roll_categories)
    station_values = np.asarray([station_index[geometry[name]] for name in roll_name_values], dtype=np.float64)
    run_values = _category_coordinates(np.asarray(rpc_tree["run"]), run_category_values)
    roll_edges = np.arange(len(roll_categories) + 1, dtype=np.float64)
    station_edges = np.arange(len(STATION_NAMES) + 1, dtype=np.float64)
    run_edges = np.arange(len(run_category_values) + 1, dtype=np.float64)

    accepted = ~np.isin(roll_name_values, tuple(load_roll_blacklist(roll_blacklist_path)))
    fiducial = accepted & np.asarray(rpc_tree["is_fiducial"], dtype=bool)
    selection_masks = {
        FIDUCIAL_SELECTION: fiducial,
        MATCHED_SELECTION: fiducial & np.asarray(rpc_tree["is_matched"], dtype=bool),
    }

    for selection, mask in selection_masks.items():
        for branch, edges in RPC_AXIS_EDGES.items():
            name = count_station_name(selection, branch)
            output[name] = _hist2d(name, branch, edges, rpc_values[branch], "station", station_edges, station_values, mask)
        name = count_roll_name(selection)
        output[name] = _hist1d(name, "roll_name", roll_edges, roll_values, mask)
        name = count_run_station_name(selection)
        output[name] = _hist2d(name, "run", run_edges, run_values, "station", station_edges, station_values, mask)

    matched = selection_masks[MATCHED_SELECTION]
    for branch in ROLL_PROFILE_BRANCHES:
        name = profile_roll_name(branch)
        output[name] = _hist1d(name, "roll_name", roll_edges, roll_values, matched, rpc_values[branch])

    for sample, branch in ONE_DIMENSIONAL_PROFILES.items():
        name = profile_1d_name(sample, branch)
        output[name] = _hist1d(name, branch, RPC_AXIS_EDGES[branch], rpc_values[branch], matched, rpc_values[sample])

    cls_values = rpc_values["cls"]
    for branch in CLS_PROFILE_BRANCHES:
        name = cls_profile_station_name(branch)
        output[name] = _hist2d(name, branch, RPC_AXIS_EDGES[branch], rpc_values[branch], "station", station_edges, station_values, matched, cls_values)
    output[CLS_RUN_STATION_PROFILE] = _hist2d(CLS_RUN_STATION_PROFILE, "run", run_edges, run_values, "station", station_edges, station_values, matched, cls_values)
    return output


def write_histogram_shard(output_path: Path, pair_tree: dict[str, np.ndarray], rpc_tree: dict[str, np.ndarray], roll_blacklist_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(output_path, compression=HISTOGRAM_COMPRESSION) as output:
        for name, histogram in sorted(build_histograms(pair_tree, rpc_tree, roll_blacklist_path).items()):
            output[name] = histogram
