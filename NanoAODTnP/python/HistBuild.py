from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import hist
import numpy as np
import uproot

from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import load_roll_blacklist  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import is_irpc_roll_name  # type: ignore


PACKAGE_DIR = Path(__file__).resolve().parents[1]
RUN_CATEGORY_PATH = PACKAGE_DIR / "data" / "lumi" / "run3.csv"
ROLL_CATEGORY_PATH = PACKAGE_DIR / "data" / "geometry" / "run3.csv"
HISTOGRAM_COMPRESSION = uproot.ZLIB(1)
PAIR_MASS_HISTOGRAM = "count_pair_mass"
PAIR_Q_OVER_P_HISTOGRAM = "count_pair_probe_q_over_p"
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
COUNT_MOMENTUM_EDGES = regular_edges(0.0, 300.0, 300)
COUNT_ETA_EDGES = regular_edges(-2.4, 2.4, 96)
COUNT_PHI_EDGES = regular_edges(-np.pi, np.pi, 128)
COUNT_Q_OVER_P_EDGES = regular_edges(-0.2, 0.2, 80)
PLOT_COUNT_MOMENTUM_EDGES = regular_edges(10.0, 200.0, 38)
PLOT_PT_EDGES = np.asarray([10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0, 120.0, 200.0], dtype=np.float64)
PLOT_P_EDGES = np.asarray([*(float(value) for value in range(0, 105, 5)), 120.0, 140.0, 200.0], dtype=np.float64)
PLOT_ETA_EDGES = regular_edges(-1.9, 1.9, 19)
PLOT_PHI_EDGES = regular_edges(-np.pi, np.pi, 64)
PLOT_PV_EDGES = regular_edges(0.0, 80.0, 8)
PLOT_Q_OVER_P_EDGES = regular_edges(-0.1, 0.1, 20)
VALUE_MOMENTUM_EDGES = COUNT_MOMENTUM_EDGES
PAIR_MUON_PT_EDGES = COUNT_MOMENTUM_EDGES
PAIR_MUON_PHI_EDGES = COUNT_PHI_EDGES
PROBE_ETA_EDGES = COUNT_ETA_EDGES
TAG_ETA_EDGES = COUNT_ETA_EDGES
RPC_CLS_EDGES = integer_edges(1, 30)
RPC_BX_EDGES = integer_edges(-4, 4)
RPC_PT_EDGES = regular_edges(0.0, 300.0, 300)
RPC_P_EDGES = regular_edges(0.0, 300.0, 300)
RPC_PV_EDGES = integer_edges(0, 100)
RPC_Q_OVER_P_EDGES = regular_edges(-0.2, 0.2, 80)
RPC_RESIDUAL_X_EDGES = regular_edges(-100.0, 100.0, 400)
RPC_2D_ETA_EDGES = COUNT_ETA_EDGES
RPC_2D_PHI_EDGES = COUNT_PHI_EDGES
FIDUCIAL_SELECTION = "fiducial"
MATCHED_SELECTION = "fiducial_matched"
TIGHT_MATCH_RESIDUAL_X_CM = 20.0
TIGHT_MATCH_PULL_X = 4.0
PROBE_PT_THRESHOLD_GEV = 15.0
PROBE_ABS_ETA_MAX = 1.9
CLS_RUN_STATION_PROFILE = f"profile_rpc_{MATCHED_SELECTION}_cls_by_run_station"

RPC_AXIS_EDGES = {
    "probe_pt": RPC_PT_EDGES,
    "probe_p": RPC_P_EDGES,
    "n_pv": RPC_PV_EDGES,
    "probe_q_over_p": RPC_Q_OVER_P_EDGES,
    "residual_x": RPC_RESIDUAL_X_EDGES,
    "bx": RPC_BX_EDGES,
    "cls": RPC_CLS_EDGES,
}
RPC_SELECTION_BRANCHES = {
    FIDUCIAL_SELECTION: (
        "probe_pt", "probe_p", "n_pv", "probe_q_over_p",
    ),
    MATCHED_SELECTION: (
        "probe_pt", "probe_p", "n_pv", "probe_q_over_p",
        "residual_x", "bx", "cls",
    ),
}
CLS_PROFILE_BRANCHES = (
    "probe_pt", "probe_p", "n_pv", "probe_q_over_p",
)
CLS_ROLL_PROFILE = f"profile_rpc_{MATCHED_SELECTION}_cls_by_roll"
RMS_PROFILE_BRANCHES = {
    "residual_x": ("probe_pt",),
}
KINEMATIC_2D_AXES = {
    "probe_pt_eta": ("probe_eta", RPC_2D_ETA_EDGES, "probe_pt", VALUE_MOMENTUM_EDGES),
    "probe_eta_phi": ("probe_eta", RPC_2D_ETA_EDGES, "probe_phi", RPC_2D_PHI_EDGES),
}


def pair_kinematics_name(prefix: str) -> str:
    return f"count_pair_{prefix}_pt_eta"


def pair_eta_phi_name(prefix: str) -> str:
    return f"count_pair_{prefix}_eta_phi"


def count_station_name(selection: str, branch: str) -> str:
    return f"count_rpc_{selection}_{branch}_by_station"


def count_roll_name(selection: str) -> str:
    return f"count_rpc_{selection}_by_roll"


def count_run_station_name(selection: str) -> str:
    return f"count_rpc_{selection}_by_run_station"


def cls_profile_station_name(branch: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_cls_by_{branch}_station"


def profile_1d_station_name(sample: str, branch: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_{sample}_by_{branch}_station"


def count_2d_station_name(selection: str, name: str) -> str:
    return f"count_rpc_{selection}_{name}_by_station"


def cls_profile_2d_station_name(name: str) -> str:
    return f"profile_rpc_{MATCHED_SELECTION}_cls_by_{name}_station"


RMS_STATION_PROFILE_NAMES = tuple(
    profile_1d_station_name(sample, branch)
    for sample, branches in RMS_PROFILE_BRANCHES.items()
    for branch in branches
)
KINEMATIC_2D_HISTOGRAM_NAMES = tuple(sorted(
    [
        count_2d_station_name(selection, name)
        for selection in (FIDUCIAL_SELECTION, MATCHED_SELECTION)
        for name in KINEMATIC_2D_AXES
    ]
    + [cls_profile_2d_station_name(name) for name in KINEMATIC_2D_AXES]
))
OPTIONAL_HISTOGRAM_NAMES = tuple(sorted((
    PAIR_Q_OVER_P_HISTOGRAM,
    *KINEMATIC_2D_HISTOGRAM_NAMES,
)))


def _histogram_names() -> tuple[str, ...]:
    names = [
        PAIR_MASS_HISTOGRAM,
        PAIR_Q_OVER_P_HISTOGRAM,
        pair_kinematics_name("probe"),
        pair_kinematics_name("tag"),
        pair_eta_phi_name("probe"),
        pair_eta_phi_name("tag"),
    ]
    for selection, branches in RPC_SELECTION_BRANCHES.items():
        names.extend(count_station_name(selection, branch) for branch in branches)
        names.extend((count_roll_name(selection), count_run_station_name(selection)))
    names.append(CLS_ROLL_PROFILE)
    names.extend(RMS_STATION_PROFILE_NAMES)
    names.extend(cls_profile_station_name(branch) for branch in CLS_PROFILE_BRANCHES)
    names.extend(KINEMATIC_2D_HISTOGRAM_NAMES)
    names.append(CLS_RUN_STATION_PROFILE)
    return tuple(sorted(names))


HISTOGRAM_NAMES = _histogram_names()


def _category_coordinates(values: np.ndarray, categories: tuple, missing: float | None = None) -> np.ndarray:
    index_by_category = {category: index + 0.5 for index, category in enumerate(categories)}
    if missing is None:
        return np.asarray([index_by_category[value] for value in values], dtype=np.float64)
    return np.asarray([index_by_category.get(value, missing) for value in values], dtype=np.float64)


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


def _hist2d(
    name: str,
    x_name: str,
    x_edges: np.ndarray,
    x_values: np.ndarray,
    y_name: str,
    y_edges: np.ndarray,
    y_values: np.ndarray,
    mask: np.ndarray,
    weights: np.ndarray | None = None,
):
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


def _hist3d(
    name: str,
    x_name: str,
    x_edges: np.ndarray,
    x_values: np.ndarray,
    y_name: str,
    y_edges: np.ndarray,
    y_values: np.ndarray,
    z_name: str,
    z_edges: np.ndarray,
    z_values: np.ndarray,
    mask: np.ndarray,
    weights: np.ndarray | None = None,
):
    x_values = np.asarray(x_values, dtype=np.float64)
    y_values = np.asarray(y_values, dtype=np.float64)
    z_values = np.asarray(z_values, dtype=np.float64)
    selected = np.asarray(mask, dtype=bool) & np.isfinite(x_values) & np.isfinite(y_values) & np.isfinite(z_values)
    storage = hist.storage.Double()
    if weights is not None:
        weights = np.asarray(weights, dtype=np.float64)
        selected &= np.isfinite(weights)
        storage = hist.storage.Weight()
    histogram = hist.Hist(
        hist.axis.Variable(x_edges, name=x_name, label=x_name),
        hist.axis.Variable(y_edges, name=y_name, label=y_name),
        hist.axis.Variable(z_edges, name=z_name, label=z_name),
        storage=storage,
        name=name,
    )
    histogram.fill(x_values[selected], y_values[selected], z_values[selected], weight=None if weights is None else weights[selected])
    return histogram


def matched_selection_mask(rpc_tree: dict[str, np.ndarray], tight_match: bool = False) -> np.ndarray:
    if not tight_match:
        return np.asarray(rpc_tree["is_matched"], dtype=bool)
    residual_x = np.asarray(rpc_tree["residual_x"], dtype=np.float64)
    pull_x = np.asarray(rpc_tree["pull_x"], dtype=np.float64)
    return (np.abs(residual_x) <= TIGHT_MATCH_RESIDUAL_X_CM) | (np.abs(pull_x) <= TIGHT_MATCH_PULL_X)


def load_run_blacklist(path: Path | str) -> set[int]:
    runs: set[int] = set()
    with open(path) as stream:
        for raw_line in stream:
            columns = raw_line.split("#", 1)[0].replace(",", " ").split()
            if columns:
                runs.add(int(columns[0]))
    return runs


def build_histograms(
    pair_tree: dict[str, np.ndarray],
    rpc_tree: dict[str, np.ndarray],
    roll_blacklist_path: Path | None,
    run_blacklist_path: Path | None = None,
    apply_roll_blacklist: bool = True,
    apply_run_blacklist: bool = True,
    tight_match: bool = False,
    probe_pt_gt15: bool = True,
    bx_zero: bool = False,
) -> dict[str, hist.Hist]:
    output: dict[str, hist.Hist] = {}
    stored_branches = set(RPC_AXIS_EDGES) | {
        branch
        for x_branch, _, y_branch, _ in KINEMATIC_2D_AXES.values()
        for branch in (x_branch, y_branch)
    } | set(RMS_PROFILE_BRANCHES)
    rpc_values = {branch: np.asarray(rpc_tree[branch]) for branch in stored_branches}

    roll_name_values = np.asarray(rpc_tree["roll_name"], dtype=str)
    roll_categories = roll_names()
    irpc = np.isin(roll_name_values, tuple(name for name in roll_categories if is_irpc_roll_name(name)))
    pair_has_legacy_rpc = np.zeros(len(pair_tree["run"]), dtype=bool)
    pair_has_legacy_rpc[np.asarray(rpc_tree["pair_index"], dtype=np.int64)[~irpc]] = True

    run_blacklist = load_run_blacklist(run_blacklist_path) if apply_run_blacklist and run_blacklist_path is not None else set()
    pair_blacklisted_run = np.isin(np.asarray(pair_tree["run"], dtype=np.uint32), tuple(run_blacklist))
    pair_probe_eta = np.asarray(pair_tree["probe_eta"], dtype=np.float64)
    pair_mask = ~pair_blacklisted_run & pair_has_legacy_rpc & (np.abs(pair_probe_eta) < PROBE_ABS_ETA_MAX)
    if probe_pt_gt15:
        pair_mask &= np.asarray(pair_tree["probe_pt"], dtype=np.float64) > PROBE_PT_THRESHOLD_GEV
    output[PAIR_MASS_HISTOGRAM] = _hist1d(PAIR_MASS_HISTOGRAM, "pair_mass", PAIR_MASS_EDGES, pair_tree["pair_mass"], pair_mask)
    output[PAIR_Q_OVER_P_HISTOGRAM] = _hist1d(
        PAIR_Q_OVER_P_HISTOGRAM,
        "probe_q_over_p",
        COUNT_Q_OVER_P_EDGES,
        pair_tree["probe_q_over_p"],
        pair_mask,
    )
    for prefix, eta_edges in (("probe", PROBE_ETA_EDGES), ("tag", TAG_ETA_EDGES)):
        name = pair_kinematics_name(prefix)
        output[name] = _hist2d(name, f"{prefix}_eta", eta_edges, pair_tree[f"{prefix}_eta"], f"{prefix}_pt", PAIR_MUON_PT_EDGES, pair_tree[f"{prefix}_pt"], pair_mask)
        name = pair_eta_phi_name(prefix)
        output[name] = _hist2d(name, f"{prefix}_eta", eta_edges, pair_tree[f"{prefix}_eta"], f"{prefix}_phi", PAIR_MUON_PHI_EDGES, pair_tree[f"{prefix}_phi"], pair_mask)

    geometry = roll_geometry()
    run_category_values = run_categories()
    station_index = {station: index + 0.5 for index, station in enumerate(STATION_NAMES)}
    roll_values = _category_coordinates(roll_name_values, roll_categories)
    station_values = np.asarray([station_index[geometry[name]] for name in roll_name_values], dtype=np.float64)
    run_values = _category_coordinates(np.asarray(rpc_tree["run"], dtype=np.uint32), run_category_values, missing=np.nan)
    roll_edges = np.arange(len(roll_categories) + 1, dtype=np.float64)
    station_edges = np.arange(len(STATION_NAMES) + 1, dtype=np.float64)
    run_edges = np.arange(len(run_category_values) + 1, dtype=np.float64)

    roll_blacklist = load_roll_blacklist(roll_blacklist_path) if apply_roll_blacklist and roll_blacklist_path is not None else set()
    blacklisted_roll = np.isin(roll_name_values, tuple(roll_blacklist))
    blacklisted_run = np.isin(np.asarray(rpc_tree["run"], dtype=np.uint32), tuple(run_blacklist))
    rpc_probe_eta = np.asarray(rpc_tree["probe_eta"], dtype=np.float64)
    accepted = ~blacklisted_roll & ~irpc & ~blacklisted_run & (np.abs(rpc_probe_eta) < PROBE_ABS_ETA_MAX)
    if probe_pt_gt15:
        accepted &= np.asarray(rpc_tree["probe_pt"], dtype=np.float64) > PROBE_PT_THRESHOLD_GEV
    fiducial = accepted & np.asarray(rpc_tree["is_fiducial"], dtype=bool)
    matched = matched_selection_mask(rpc_tree, tight_match=tight_match)
    if bx_zero:
        matched &= np.asarray(rpc_tree["bx"], dtype=np.int32) == 0
    selection_masks = {
        FIDUCIAL_SELECTION: fiducial,
        MATCHED_SELECTION: fiducial & matched,
    }

    for selection, mask in selection_masks.items():
        for branch in RPC_SELECTION_BRANCHES[selection]:
            name = count_station_name(selection, branch)
            output[name] = _hist2d(name, branch, RPC_AXIS_EDGES[branch], rpc_values[branch], "station", station_edges, station_values, mask)
        name = count_roll_name(selection)
        output[name] = _hist1d(name, "roll_name", roll_edges, roll_values, mask)
        name = count_run_station_name(selection)
        output[name] = _hist2d(name, "run", run_edges, run_values, "station", station_edges, station_values, mask)
        for plot_name, (x_branch, x_edges, y_branch, y_edges) in KINEMATIC_2D_AXES.items():
            name = count_2d_station_name(selection, plot_name)
            output[name] = _hist3d(name, x_branch, x_edges, rpc_values[x_branch], y_branch, y_edges, rpc_values[y_branch], "station", station_edges, station_values, mask)

    matched = selection_masks[MATCHED_SELECTION]
    output[CLS_ROLL_PROFILE] = _hist1d(CLS_ROLL_PROFILE, "roll_name", roll_edges, roll_values, matched, rpc_values["cls"])

    for sample, branches in RMS_PROFILE_BRANCHES.items():
        for branch in branches:
            name = profile_1d_station_name(sample, branch)
            output[name] = _hist2d(name, branch, RPC_AXIS_EDGES[branch], rpc_values[branch], "station", station_edges, station_values, matched, rpc_values[sample])

    cls_values = rpc_values["cls"]
    for branch in CLS_PROFILE_BRANCHES:
        name = cls_profile_station_name(branch)
        output[name] = _hist2d(name, branch, RPC_AXIS_EDGES[branch], rpc_values[branch], "station", station_edges, station_values, matched, cls_values)
    for plot_name, (x_branch, x_edges, y_branch, y_edges) in KINEMATIC_2D_AXES.items():
        name = cls_profile_2d_station_name(plot_name)
        output[name] = _hist3d(
            name,
            x_branch,
            x_edges,
            rpc_values[x_branch],
            y_branch,
            y_edges,
            rpc_values[y_branch],
            "station",
            station_edges,
            station_values,
            matched,
            cls_values,
        )
    output[CLS_RUN_STATION_PROFILE] = _hist2d(CLS_RUN_STATION_PROFILE, "run", run_edges, run_values, "station", station_edges, station_values, matched, cls_values)
    return output


def write_histogram_shard(
    output_path: Path,
    pair_tree: dict[str, np.ndarray],
    rpc_tree: dict[str, np.ndarray],
    roll_blacklist_path: Path | None,
    run_blacklist_path: Path | None = None,
    apply_roll_blacklist: bool = True,
    apply_run_blacklist: bool = True,
    tight_match: bool = False,
    probe_pt_gt15: bool = True,
    bx_zero: bool = False,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(output_path, compression=HISTOGRAM_COMPRESSION) as output:
        histograms = build_histograms(
            pair_tree,
            rpc_tree,
            roll_blacklist_path,
            run_blacklist_path=run_blacklist_path,
            apply_roll_blacklist=apply_roll_blacklist,
            apply_run_blacklist=apply_run_blacklist,
            tight_match=tight_match,
            probe_pt_gt15=probe_pt_gt15,
            bx_zero=bx_zero,
        )
        for name, histogram in sorted(histograms.items()):
            output[name] = histogram
