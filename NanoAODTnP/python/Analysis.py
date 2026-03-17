import json
from typing import Optional
from pathlib import Path
from functools import singledispatchmethod
import numpy as np
import numpy.typing as npt
from dataclasses import dataclass
import awkward as ak
import uproot


@dataclass
class LumiBlockChecker:
    """
    https://twiki.cern.ch/twiki/bin/view/CMSPublic/SWGuideGoodLumiSectionsJSONFile
    """
    cert: dict[np.uint32, npt.NDArray[np.uint32]]

    @staticmethod
    def _transform_lumi_ranges(lumi: list[tuple[int, int]]
    ) -> npt.NDArray[np.uint32]:
        """
        """
        flat_lumi = np.array(lumi, dtype=np.uint32).flatten()
        # [first, last] to (first, last]
        flat_lumi[::2] -= 1
        return flat_lumi

    @classmethod
    def from_dict(cls, cert: dict[int, list[tuple[int, int]]]):
        flat_cert = {np.uint32(run): cls._transform_lumi_ranges(lumi_ranges)
                     for run, lumi_ranges in cert.items()}
        return cls(flat_cert)

    @classmethod
    def from_json(cls, path):
        with open(path) as stream:
            cert = json.load(stream)
        return cls.from_dict(cert)

    @staticmethod
    def _get_lumi_mask(lumi_arr: npt.NDArray[np.uint32],
                     ranges: npt.NDArray[np.uint32]
    ) -> npt.NDArray[np.bool_]:
        """
        """
        # odd(even) indices indicate good(bad) lumi blocks
        indices = np.searchsorted(ranges, lumi_arr)
        mask = (indices & 0x1).astype(bool)
        return mask

    @singledispatchmethod
    def get_lumi_mask(self, run, lumi: npt.NDArray[np.uint32]):
        raise NotImplementedError(f'expected np.uint32, npt.NDArray[np.uint32]'
                                  f' or int but got {type(run)}')

    @get_lumi_mask.register(int)
    @get_lumi_mask.register(np.uint32)
    def _(self,
          run: np.uint32,
          lumi: npt.NDArray[np.uint32]
    ) -> npt.NDArray[np.bool_]:
        """
        """
        if isinstance(run, int):
            run = np.uint32(run)

        if run in self.cert:
            mask = self._get_lumi_mask(lumi, ranges=self.cert[run])
        else:
            mask = np.full_like(lumi, fill_value=False, dtype=bool)
        return mask

    @get_lumi_mask.register(np.ndarray)
    def _(self,
          run: npt.NDArray[np.uint32],
          lumi: npt.NDArray[np.uint32]
    ) -> npt.NDArray[np.bool_]:
        """
        """
        mask = np.full_like(lumi, fill_value=False, dtype=bool)
        for each in np.unique(run):
            run_mask = run == each
            mask[run_mask] = self.get_lumi_mask(each, lumi[run_mask])
        return mask


ALL_OPTIONAL_EVENT_KEYS = ('bunchCrossing', 'orbitNumber')

TRIAL_FLOAT_KEYS = {
    'tag_pt', 'tag_eta', 'tag_phi',
    'probe_pt', 'probe_eta', 'probe_phi',
    'probe_time', 'probe_dxdz', 'probe_dydz',
    'dimuon_pt', 'dimuon_mass',
    'residual_x', 'residual_y',
    'pull_x', 'pull_y', 'pull_x_v2', 'pull_y_v2',
}
TRIAL_INT_KEYS = {
    'region', 'ring', 'station', 'sector', 'layer', 'subsector', 'roll',
    'cls', 'bx',
}
TRIAL_BOOL_KEYS = {
    'is_fiducial', 'is_matched',
}
PAIR_KEYS = [
    'tag_pt', 'tag_eta', 'tag_phi',
    'probe_pt', 'probe_eta', 'probe_phi',
    'probe_time',
    'dimuon_pt', 'dimuon_mass',
]


def _get_tree_entry_count(tree_dict: dict[str, np.ndarray]) -> int:
    if len(tree_dict) == 0:
        return 0
    first_key = next(iter(tree_dict))
    return len(tree_dict[first_key])


def _ensure_required_fields(fields: list[str], required_fields: list[str], where: str):
    missing = [key for key in required_fields if key not in fields]
    if missing:
        raise RuntimeError(f"Missing required fields in {where}: {missing}")


def read_nanoaod_base(
    path: Path,
    cert_path: Path,
    treepath: str = 'Events',
    name: str = 'rpcTnP',
):
    with uproot.open(path) as input_file:
        if treepath not in input_file:
            raise RuntimeError(f"Missing tree '{treepath}' in {path}")

        tree = input_file[treepath]
        tree_keys = list(tree.keys())

        required_event_keys = ['run', 'luminosityBlock', 'event', f'n{name}']
        _ensure_required_fields(tree_keys, required_event_keys, f"{path}:{treepath}")

        prefixed_keys = [
            key for key in tree_keys
            if key.startswith(f'{name}_')
        ]
        if len(prefixed_keys) == 0:
            raise RuntimeError(f"No branches with prefix '{name}_' found in {path}:{treepath}")

        present_optional_event_keys = [
            key for key in ALL_OPTIONAL_EVENT_KEYS
            if key in tree_keys
        ]

        aliases = {
            key.removeprefix(f'{name}_'): key
            for key in prefixed_keys
        }
        aliases['size'] = f'n{name}'

        expressions = (
            list(aliases.keys())
            + ['run', 'luminosityBlock', 'event']
            + present_optional_event_keys
        )
        cut = f'(n{name} > 0)'

        base_tree = tree.arrays(
            expressions=expressions,
            aliases=aliases,
            cut=cut,
            library='ak'
        )

    lumi_block_checker = LumiBlockChecker.from_json(cert_path)

    run = np.asarray(ak.to_numpy(base_tree['run']), dtype=np.uint32)
    lumi_block = np.asarray(ak.to_numpy(base_tree['luminosityBlock']), dtype=np.uint32)
    lumi_mask = lumi_block_checker.get_lumi_mask(run, lumi_block)

    base_tree = base_tree[lumi_mask]

    n_event = len(base_tree)

    for key in ALL_OPTIONAL_EVENT_KEYS:
        if key in base_tree.fields:
            value = np.asarray(ak.to_numpy(base_tree[key]), dtype=np.int32)
        else:
            value = np.full(n_event, -1, dtype=np.int32)

        base_tree = ak.with_field(base_tree, ak.Array(value), key)

    return base_tree, list(ALL_OPTIONAL_EVENT_KEYS)


def build_trial_tree(
    base_tree,
    optional_event_keys,
):
    size = np.asarray(ak.to_numpy(base_tree['size']), dtype=np.int32)
    total_size = int(np.sum(size, dtype=np.int64))

    event_keys = {'run', 'luminosityBlock', 'event', 'size', *optional_event_keys}
    jagged_keys = [key for key in base_tree.fields if key not in event_keys]
    if len(jagged_keys) == 0:
        raise RuntimeError("No jagged rpcTnP branches found for trial_tree")

    counts_ref = np.asarray(ak.to_numpy(ak.num(base_tree[jagged_keys[0]], axis=1)), dtype=np.int32)
    if not np.array_equal(counts_ref, size):
        raise RuntimeError(
            f"Jagged count mismatch between '{jagged_keys[0]}' and 'size'"
        )

    for key in jagged_keys[1:]:
        counts = np.asarray(ak.to_numpy(ak.num(base_tree[key], axis=1)), dtype=np.int32)
        if not np.array_equal(counts, size):
            raise RuntimeError(
                f"Jagged count mismatch between '{key}' and 'size'"
            )

    trial_tree = {}

    for key in jagged_keys:
        flat_value = ak.flatten(base_tree[key], axis=1)
        flat_value = ak.to_numpy(flat_value)

        if len(flat_value) != total_size:
            raise RuntimeError(
                f"trial flatten size mismatch for '{key}': "
                f"{len(flat_value)} != {total_size}"
            )

        if key in TRIAL_FLOAT_KEYS:
            trial_tree[key] = np.asarray(flat_value, dtype=np.float64)
        elif key in TRIAL_INT_KEYS:
            trial_tree[key] = np.asarray(flat_value, dtype=np.int32)
        elif key in TRIAL_BOOL_KEYS:
            trial_tree[key] = np.asarray(flat_value, dtype=np.bool_)
        else:
            trial_tree[key] = np.asarray(flat_value)

    run = np.asarray(ak.to_numpy(base_tree['run']), dtype=np.uint32)
    lumi_block = np.asarray(ak.to_numpy(base_tree['luminosityBlock']), dtype=np.uint32)
    event = np.asarray(ak.to_numpy(base_tree['event']), dtype=np.uint64)

    if total_size > 0:
        trial_tree['run'] = np.asarray(np.repeat(run, size), dtype=np.uint32)
        trial_tree['luminosityBlock'] = np.asarray(np.repeat(lumi_block, size), dtype=np.uint32)
        trial_tree['event'] = np.asarray(np.repeat(event, size), dtype=np.uint64)

        for key in optional_event_keys:
            value = np.asarray(ak.to_numpy(base_tree[key]), dtype=np.int32)
            trial_tree[key] = np.asarray(np.repeat(value, size), dtype=np.int32)

        trial_tree['pair_index'] = np.zeros(total_size, dtype=np.int32)
        trial_tree['nrpcTnP'] = np.asarray(np.repeat(size, size), dtype=np.int32)

        trial_index = ak.local_index(base_tree[jagged_keys[0]], axis=1)
        trial_tree['trial_index'] = np.asarray(
            ak.to_numpy(ak.flatten(trial_index, axis=1)),
            dtype=np.int32
        )
    else:
        trial_tree['run'] = np.array([], dtype=np.uint32)
        trial_tree['luminosityBlock'] = np.array([], dtype=np.uint32)
        trial_tree['event'] = np.array([], dtype=np.uint64)

        for key in optional_event_keys:
            trial_tree[key] = np.array([], dtype=np.int32)

        trial_tree['pair_index'] = np.array([], dtype=np.int32)
        trial_tree['nrpcTnP'] = np.array([], dtype=np.int32)
        trial_tree['trial_index'] = np.array([], dtype=np.int32)

    return trial_tree


def build_pair_tree(
    base_tree,
    optional_event_keys,
):
    _ensure_required_fields(base_tree.fields, PAIR_KEYS, "base_tree for pair_tree")

    size = np.asarray(ak.to_numpy(base_tree['size']), dtype=np.int32)
    if np.any(size <= 0):
        raise RuntimeError("pair_tree found non-positive size after n{name} > 0 cut")

    for key in PAIR_KEYS:
        counts = np.asarray(ak.to_numpy(ak.num(base_tree[key], axis=1)), dtype=np.int32)
        if not np.array_equal(counts, size):
            raise RuntimeError(
                f"Pair jagged count mismatch between '{key}' and 'size'"
            )

    pair_tree = {}

    for key in PAIR_KEYS:
        first_value = ak.firsts(base_tree[key], axis=1)
        if bool(ak.any(ak.is_none(first_value))):
            raise RuntimeError(f"pair_tree found empty first element for '{key}'")

        pair_tree[key] = np.asarray(ak.to_numpy(first_value), dtype=np.float64)

    pair_tree['run'] = np.asarray(ak.to_numpy(base_tree['run']), dtype=np.uint32)
    pair_tree['luminosityBlock'] = np.asarray(ak.to_numpy(base_tree['luminosityBlock']), dtype=np.uint32)
    pair_tree['event'] = np.asarray(ak.to_numpy(base_tree['event']), dtype=np.uint64)

    for key in optional_event_keys:
        value = np.asarray(ak.to_numpy(base_tree[key]), dtype=np.int32)
        pair_tree[key] = np.asarray(value, dtype=np.int32)

    pair_tree['pair_index'] = np.zeros(len(size), dtype=np.int32)
    pair_tree['nrpcTnP'] = np.asarray(size, dtype=np.int32)

    return pair_tree


def validate_flat_tree(tree_dict: dict[str, np.ndarray], tree_name: str):
    lengths = {key: len(value) for key, value in tree_dict.items()}
    uniq = set(lengths.values())
    if len(uniq) != 1:
        raise RuntimeError(f"{tree_name} length mismatch: {lengths}")

    object_keys = [
        key for key, value in tree_dict.items()
        if np.asarray(value).dtype == object
    ]
    if object_keys:
        raise RuntimeError(f"{tree_name} has object dtype branches: {object_keys}")

    ndim_bad_keys = [
        key for key, value in tree_dict.items()
        if np.asarray(value).ndim != 1
    ]
    if ndim_bad_keys:
        raise RuntimeError(f"{tree_name} has non-1D branches: {ndim_bad_keys}")


def validate_output_root(path: Path):
    with uproot.open(path) as root_file:
        for tree_name in ('trial_tree', 'pair_tree'):
            if tree_name not in root_file:
                raise RuntimeError(f"missing tree '{tree_name}' in output")

            tree = root_file[tree_name]
            keys = list(tree.keys())
            if len(keys) == 0:
                raise RuntimeError(f"empty tree '{tree_name}' in output")

            for key in keys:
                branch = tree[key]

                _ = branch.entry_offsets

                if tree.num_entries > 0:
                    tree.arrays([key], entry_start=0, entry_stop=1, library='np')

                if tree.num_entries > 1:
                    tree.arrays(
                        [key],
                        entry_start=tree.num_entries - 1,
                        entry_stop=tree.num_entries,
                        library='np'
                    )


def flatten_nanoaod(
    input_path: Path,
    cert_path: Path,
    output_path: Path,
    name: str = 'rpcTnP',
):
    base_tree, optional_event_keys = read_nanoaod_base(
        path=input_path,
        cert_path=cert_path,
        treepath='Events',
        name=name,
    )

    trial_tree = build_trial_tree(
        base_tree=base_tree,
        optional_event_keys=optional_event_keys,
    )
    pair_tree = build_pair_tree(
        base_tree=base_tree,
        optional_event_keys=optional_event_keys,
    )

    validate_flat_tree(trial_tree, 'trial_tree')
    validate_flat_tree(pair_tree, 'pair_tree')

    output_path.parent.mkdir(parents=True, exist_ok=True)

    empty_marker = output_path.parent / f"{output_path.name}.empty"
    tmp_output_path = output_path.parent / f"{output_path.stem}.tmp{output_path.suffix}"

    trial_entries = _get_tree_entry_count(trial_tree)
    pair_entries = _get_tree_entry_count(pair_tree)

    if empty_marker.exists():
        empty_marker.unlink()
    if tmp_output_path.exists():
        tmp_output_path.unlink()

    if trial_entries == 0 and pair_entries == 0:
        if output_path.exists():
            output_path.unlink()
        empty_marker.write_text("empty\n")
        return

    trial_branches = {
        key: np.asarray(value).dtype
        for key, value in trial_tree.items()
    }
    pair_branches = {
        key: np.asarray(value).dtype
        for key, value in pair_tree.items()
    }

    try:
        with uproot.recreate(tmp_output_path) as output_file:
            output_file.mktree('trial_tree', trial_branches)
            output_file['trial_tree'].extend({
                key: np.asarray(value)
                for key, value in trial_tree.items()
            })

            output_file.mktree('pair_tree', pair_branches)
            output_file['pair_tree'].extend({
                key: np.asarray(value)
                for key, value in pair_tree.items()
            })

        validate_output_root(tmp_output_path)
        tmp_output_path.replace(output_path)

    except Exception:
        if tmp_output_path.exists():
            tmp_output_path.unlink()
        if output_path.exists():
            output_path.unlink()
        raise