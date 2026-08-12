from __future__ import annotations

import json
from pathlib import Path

import awkward as ak
import numpy as np
import numpy.typing as npt
import uproot

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPC_GEOMETRY_KEYS, get_roll_name  # type: ignore

TREE_PATH = "Events"
TABLE_NAME = "rpcTnP"

RPC_FLOAT_KEYS = [
    "probe_pt",
    "probe_eta",
    "probe_phi",
    "residual_x",
    "pull_x",
]
RPC_INT_KEYS = ["cls", "bx", "probe_q", "n_pv"]
RPC_BOOL_KEYS = ["is_fiducial", "is_matched"]

PAIR_KEYS = [
    "tag_pt",
    "tag_eta",
    "tag_phi",
    "probe_pt",
    "probe_eta",
    "probe_phi",
    "probe_q",
    "probe_time",
    "pair_pt",
    "pair_mass",
]
REQUIRED_BASE_KEYS = frozenset((
    *RPC_FLOAT_KEYS,
    *RPC_INT_KEYS,
    *RPC_BOOL_KEYS,
    *RPC_GEOMETRY_KEYS,
    *PAIR_KEYS,
))


def build_roll_names(geometry: dict[str, np.ndarray]) -> np.ndarray:
    det_ids = np.column_stack([geometry[key] for key in RPC_GEOMETRY_KEYS])
    unique_det_ids, inverse = np.unique(det_ids, axis=0, return_inverse=True)
    unique_names = np.asarray([
        get_roll_name(*(int(value) for value in det_id))
        for det_id in unique_det_ids
    ], dtype=str)
    return unique_names[inverse]


def _flatten_branch(base_tree, key: str) -> np.ndarray:
    return ak.to_numpy(ak.flatten(base_tree[key], axis=1))


def _add_probe_momentum(tree: dict[str, np.ndarray]) -> None:
    tree["probe_p"] = tree["probe_pt"] * np.cosh(tree["probe_eta"])
    tree["probe_q_over_p"] = np.divide(
        tree["probe_q"],
        tree["probe_p"],
        out=np.full_like(tree["probe_p"], np.nan, dtype=np.float64),
        where=tree["probe_p"] > 0.0,
    )


def build_rpc_tree(base_tree) -> dict[str, np.ndarray]:
    size = np.asarray(ak.to_numpy(base_tree["size"]), dtype=np.int32)
    rpc_tree = {
        key: np.asarray(_flatten_branch(base_tree, key), dtype=np.float64)
        for key in RPC_FLOAT_KEYS
    }
    geometry = {}
    for key in (*RPC_GEOMETRY_KEYS, *RPC_INT_KEYS):
        value = np.asarray(_flatten_branch(base_tree, key), dtype=np.int32)
        rpc_tree[key] = value
        if key in RPC_GEOMETRY_KEYS:
            geometry[key] = value
    rpc_tree["roll_name"] = build_roll_names(geometry)
    for key in RPC_BOOL_KEYS:
        rpc_tree[key] = np.asarray(_flatten_branch(base_tree, key), dtype=np.bool_)
    _add_probe_momentum(rpc_tree)
    rpc_tree["pair_index"] = np.repeat(np.arange(len(size), dtype=np.int64), size)
    rpc_tree["run"] = np.asarray(np.repeat(ak.to_numpy(base_tree["run"]), size), dtype=np.uint32)
    return rpc_tree


def build_pair_tree(base_tree) -> dict[str, np.ndarray]:
    pair_tree = {
        key: np.asarray(ak.to_numpy(ak.firsts(base_tree[key], axis=1)), dtype=np.float64)
        for key in PAIR_KEYS
    }
    _add_probe_momentum(pair_tree)
    pair_tree["run"] = np.asarray(ak.to_numpy(base_tree["run"]), dtype=np.uint32)
    return pair_tree


class LumiBlockChecker:
    """https://twiki.cern.ch/twiki/bin/view/CMSPublic/SWGuideGoodLumiSectionsJSONFile"""

    def __init__(self, cert: dict[np.uint32, npt.NDArray[np.uint32]]):
        self.cert = cert

    @staticmethod
    def _transform_lumi_ranges(lumi: list[tuple[int, int]]) -> npt.NDArray[np.uint32]:
        flat_lumi = np.array(lumi, dtype=np.uint32).flatten()
        flat_lumi[::2] -= 1
        return flat_lumi

    @classmethod
    def from_json(cls, path: Path):
        with path.open() as stream:
            cert = json.load(stream)
        return cls({
            np.uint32(run): cls._transform_lumi_ranges(lumi_ranges)
            for run, lumi_ranges in cert.items()
        })

    @staticmethod
    def _get_lumi_mask(lumi: npt.NDArray[np.uint32], ranges: npt.NDArray[np.uint32]) -> npt.NDArray[np.bool_]:
        return (np.searchsorted(ranges, lumi) & 0x1).astype(bool)

    def get_lumi_mask(self, run, lumi: npt.NDArray[np.uint32]) -> npt.NDArray[np.bool_]:
        if np.isscalar(run):
            run = np.uint32(run)
            if run not in self.cert:
                return np.full_like(lumi, fill_value=False, dtype=bool)
            return self._get_lumi_mask(lumi, self.cert[run])

        run_values = np.asarray(run, dtype=np.uint32)
        mask = np.full_like(lumi, fill_value=False, dtype=bool)
        for each in np.unique(run_values):
            selected = run_values == each
            mask[selected] = self.get_lumi_mask(each, lumi[selected])
        return mask


def read_nanoaod_base(path: Path, cert_path: Path):
    with uproot.open(path) as input_file:
        tree = input_file[TREE_PATH]
        tree_keys = list(tree.keys())
        aliases = {
            key.removeprefix(f"{TABLE_NAME}_"): key
            for key in tree_keys
            if key.startswith(f"{TABLE_NAME}_")
        }
        aliases["size"] = f"n{TABLE_NAME}"
        missing = sorted(REQUIRED_BASE_KEYS - set(aliases))
        if missing:
            raise RuntimeError(f"Missing NanoAOD branches: {', '.join(missing)}")
        selected_aliases = {key: aliases[key] for key in sorted(REQUIRED_BASE_KEYS)}
        selected_aliases["size"] = aliases["size"]
        base_tree = tree.arrays(
            expressions=list(selected_aliases) + ["run", "luminosityBlock"],
            aliases=selected_aliases,
            cut=f"(n{TABLE_NAME} > 0)",
            library="ak",
        )

    run = np.asarray(ak.to_numpy(base_tree["run"]), dtype=np.uint32)
    lumi = np.asarray(ak.to_numpy(base_tree["luminosityBlock"]), dtype=np.uint32)
    return base_tree[LumiBlockChecker.from_json(cert_path).get_lumi_mask(run, lumi)]
