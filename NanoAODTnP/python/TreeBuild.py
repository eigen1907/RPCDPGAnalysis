from __future__ import annotations

from functools import singledispatchmethod
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
    "rho",
    "probe_at_rpc_pt",
    "probe_at_rpc_eta",
    "probe_at_rpc_phi",
    "probe_at_rpc_dxdz",
    "probe_at_rpc_local_x",
    "residual_x",
    "residual_y",
    "pull_x",
    "pull_y",
    "pull_x_v2",
    "pull_y_v2",
]
RPC_INT_KEYS = ["cls", "bx", "probe_q", "n_pv", "n_good_pv"]
RPC_BOOL_KEYS = ["is_fiducial", "is_matched"]

PAIR_KEYS = [
    "tag_pt",
    "tag_eta",
    "tag_phi",
    "probe_pt",
    "probe_eta",
    "probe_phi",
    "probe_time",
    "pair_pt",
    "pair_mass",
]


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
    rpc_tree["probe_p"] = rpc_tree["probe_pt"] * np.cosh(rpc_tree["probe_eta"])
    rpc_tree["probe_at_rpc_p"] = rpc_tree["probe_at_rpc_pt"] * np.cosh(rpc_tree["probe_at_rpc_eta"])
    rpc_tree["probe_q_over_p"] = np.divide(
        rpc_tree["probe_q"],
        rpc_tree["probe_p"],
        out=np.full_like(rpc_tree["probe_p"], np.nan, dtype=np.float64),
        where=rpc_tree["probe_p"] > 0.0,
    )
    rpc_tree["run"] = np.asarray(np.repeat(ak.to_numpy(base_tree["run"]), size), dtype=np.uint32)
    return rpc_tree


def build_pair_tree(base_tree) -> dict[str, np.ndarray]:
    return {
        key: np.asarray(ak.to_numpy(ak.firsts(base_tree[key], axis=1)), dtype=np.float64)
        for key in PAIR_KEYS
    }


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

    @singledispatchmethod
    def get_lumi_mask(self, run, lumi: npt.NDArray[np.uint32]):
        raise NotImplementedError(f"expected np.uint32, np.ndarray or int but got {type(run)}")

    @get_lumi_mask.register(int)
    @get_lumi_mask.register(np.uint32)
    def _(self, run: np.uint32, lumi: npt.NDArray[np.uint32]) -> npt.NDArray[np.bool_]:
        run = np.uint32(run)
        if run not in self.cert:
            return np.full_like(lumi, fill_value=False, dtype=bool)
        return self._get_lumi_mask(lumi, self.cert[run])

    @get_lumi_mask.register(np.ndarray)
    def _(self, run: npt.NDArray[np.uint32], lumi: npt.NDArray[np.uint32]) -> npt.NDArray[np.bool_]:
        mask = np.full_like(lumi, fill_value=False, dtype=bool)
        for each in np.unique(run):
            selected = run == each
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
        base_tree = tree.arrays(
            expressions=list(aliases) + ["run", "luminosityBlock"],
            aliases=aliases,
            cut=f"(n{TABLE_NAME} > 0)",
            library="ak",
        )

    run = np.asarray(ak.to_numpy(base_tree["run"]), dtype=np.uint32)
    lumi = np.asarray(ak.to_numpy(base_tree["luminosityBlock"]), dtype=np.uint32)
    return base_tree[LumiBlockChecker.from_json(cert_path).get_lumi_mask(run, lumi)]
