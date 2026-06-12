from __future__ import annotations

from functools import singledispatchmethod
import json
from pathlib import Path

import awkward as ak
import numpy as np
import numpy.typing as npt
import uproot

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPC_GEOMETRY_KEYS, get_roll_name  # type: ignore

ALL_OPTIONAL_EVENT_KEYS = ("bunchCrossing", "orbitNumber")

RPC_FLOAT_KEYS = [
    "probe_pt",
    "probe_eta",
    "probe_phi",
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
RPC_INT_KEYS = ["cls", "bx"]
RPC_BOOL_KEYS = ["is_fiducial", "is_matched"]
RPC_KEYS = RPC_FLOAT_KEYS + list(RPC_GEOMETRY_KEYS) + RPC_INT_KEYS + RPC_BOOL_KEYS

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


def ensure_required_fields(fields: list[str], required_fields: list[str], where: str) -> None:
    missing = [key for key in required_fields if key not in fields]
    if missing:
        raise RuntimeError(f"Missing required fields in {where}: {missing}")


def build_roll_names(geometry: dict[str, np.ndarray]) -> np.ndarray:
    det_ids = np.column_stack([geometry[key] for key in RPC_GEOMETRY_KEYS])
    unique_det_ids, inverse = np.unique(det_ids, axis=0, return_inverse=True)
    unique_names = np.asarray([
        get_roll_name(*(int(value) for value in det_id))
        for det_id in unique_det_ids
    ], dtype=str)
    return unique_names[inverse]


def _flatten_branch(base_tree, key: str, total_size: int) -> np.ndarray:
    value = ak.to_numpy(ak.flatten(base_tree[key], axis=1))
    if len(value) != total_size:
        raise RuntimeError(f"rpc flatten size mismatch for '{key}': {len(value)} != {total_size}")
    return value


def build_rpc_tree(base_tree, optional_event_keys: list[str]) -> dict[str, np.ndarray]:
    ensure_required_fields(base_tree.fields, RPC_KEYS, "base_tree for rpc_tree")
    size = np.asarray(ak.to_numpy(base_tree["size"]), dtype=np.int32)
    total_size = int(np.sum(size, dtype=np.int64))
    for key in RPC_KEYS:
        if not np.array_equal(np.asarray(ak.to_numpy(ak.num(base_tree[key], axis=1)), dtype=np.int32), size):
            raise RuntimeError(f"RPC jagged count mismatch between '{key}' and 'size'")

    rpc_tree = {
        key: np.asarray(_flatten_branch(base_tree, key, total_size), dtype=np.float64)
        for key in RPC_FLOAT_KEYS
    }
    geometry = {}
    for key in (*RPC_GEOMETRY_KEYS, *RPC_INT_KEYS):
        value = np.asarray(_flatten_branch(base_tree, key, total_size), dtype=np.int32)
        rpc_tree[key] = value
        if key in RPC_GEOMETRY_KEYS:
            geometry[key] = value
    rpc_tree["roll_name"] = build_roll_names(geometry)
    for key in RPC_BOOL_KEYS:
        rpc_tree[key] = np.asarray(_flatten_branch(base_tree, key, total_size), dtype=np.bool_)
    rpc_tree["probe_p"] = rpc_tree["probe_pt"] * np.cosh(rpc_tree["probe_eta"])
    rpc_tree["probe_at_rpc_p"] = rpc_tree["probe_at_rpc_pt"] * np.cosh(rpc_tree["probe_at_rpc_eta"])

    event_values = (
        ("run", np.uint32),
        ("luminosityBlock", np.uint32),
        ("event", np.uint64),
        *((key, np.int32) for key in optional_event_keys),
    )
    for key, dtype in event_values:
        rpc_tree[key] = np.asarray(np.repeat(ak.to_numpy(base_tree[key]), size), dtype=dtype)
    return rpc_tree


def build_pair_tree(base_tree, optional_event_keys: list[str]) -> dict[str, np.ndarray]:
    ensure_required_fields(base_tree.fields, PAIR_KEYS, "base_tree for pair_tree")
    size = np.asarray(ak.to_numpy(base_tree["size"]), dtype=np.int32)
    if np.any(size <= 0):
        raise RuntimeError("pair_tree found non-positive size after nrpcTnP > 0 cut")
    for key in PAIR_KEYS:
        if not np.array_equal(np.asarray(ak.to_numpy(ak.num(base_tree[key], axis=1)), dtype=np.int32), size):
            raise RuntimeError(f"Pair jagged count mismatch between '{key}' and 'size'")

    pair_tree = {}
    for key in PAIR_KEYS:
        first_value = ak.firsts(base_tree[key], axis=1)
        if bool(ak.any(ak.is_none(first_value))):
            raise RuntimeError(f"pair_tree found empty first element for '{key}'")
        pair_tree[key] = np.asarray(ak.to_numpy(first_value), dtype=np.float64)
    pair_tree["n_rpc_crossing"] = size
    pair_tree["run"] = np.asarray(ak.to_numpy(base_tree["run"]), dtype=np.uint32)
    pair_tree["luminosityBlock"] = np.asarray(ak.to_numpy(base_tree["luminosityBlock"]), dtype=np.uint32)
    pair_tree["event"] = np.asarray(ak.to_numpy(base_tree["event"]), dtype=np.uint64)
    for key in optional_event_keys:
        pair_tree[key] = np.asarray(ak.to_numpy(base_tree[key]), dtype=np.int32)
    return pair_tree


def write_flat_root(output_path: Path, pair_tree: dict[str, np.ndarray], rpc_tree: dict[str, np.ndarray]) -> None:
    with uproot.recreate(output_path) as output_file:
        for tree_name, tree in (("pair_tree", pair_tree), ("rpc_tree", rpc_tree)):
            values = {key: np.asarray(value) for key, value in tree.items()}
            output_file.mktree(tree_name, {
                key: "string" if value.dtype.kind == "U" else value.dtype
                for key, value in values.items()
            })
            if len(next(iter(values.values()))):
                output_file[tree_name].extend(values)


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


def read_nanoaod_base(path: Path, cert_path: Path, treepath: str = "Events", name: str = "rpcTnP"):
    with uproot.open(path) as input_file:
        if treepath not in input_file:
            raise RuntimeError(f"Missing tree '{treepath}' in {path}")
        tree = input_file[treepath]
        tree_keys = list(tree.keys())
        ensure_required_fields(tree_keys, ["run", "luminosityBlock", "event", f"n{name}"], f"{path}:{treepath}")
        prefixed_keys = [key for key in tree_keys if key.startswith(f"{name}_")]
        if not prefixed_keys:
            raise RuntimeError(f"No branches with prefix '{name}_' found in {path}:{treepath}")
        optional_event_keys = [key for key in ALL_OPTIONAL_EVENT_KEYS if key in tree_keys]
        aliases = {key.removeprefix(f"{name}_"): key for key in prefixed_keys}
        aliases["size"] = f"n{name}"
        expressions = list(aliases) + ["run", "luminosityBlock", "event"] + optional_event_keys
        base_tree = tree.arrays(expressions=expressions, aliases=aliases, cut=f"(n{name} > 0)", library="ak")

    run = np.asarray(ak.to_numpy(base_tree["run"]), dtype=np.uint32)
    lumi = np.asarray(ak.to_numpy(base_tree["luminosityBlock"]), dtype=np.uint32)
    base_tree = base_tree[LumiBlockChecker.from_json(cert_path).get_lumi_mask(run, lumi)]
    for key in ALL_OPTIONAL_EVENT_KEYS:
        value = ak.to_numpy(base_tree[key]) if key in base_tree.fields else np.full(len(base_tree), -1)
        base_tree = ak.with_field(base_tree, ak.Array(np.asarray(value, dtype=np.int32)), key)
    return base_tree, list(ALL_OPTIONAL_EVENT_KEYS)
