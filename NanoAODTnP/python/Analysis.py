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


def read_nanoaod_by_trial(path,
                          cert_path: Path,
                          treepath: str = 'Events',
                          name: str = 'rpcTnP',
):
    tree = uproot.open(f'{path}:{treepath}')

    float_keys = {
        'tag_pt', 'tag_eta', 'tag_phi',
        'probe_pt', 'probe_eta', 'probe_phi',
        'probe_time', 'probe_dxdz', 'probe_dydz',
        'dimuon_pt', 'dimuon_mass',
        'residual_x', 'residual_y',
        'pull_x', 'pull_y', 'pull_x_v2', 'pull_y_v2',
    }
    int_keys = {
        'region', 'ring', 'station', 'sector', 'layer', 'subsector', 'roll',
        'cls', 'bx',
    }
    bool_keys = {
        'is_fiducial', 'is_matched',
    }

    optional_event_keys = [
        key for key in ('bunchCrossing', 'orbitNumber')
        if key in tree.keys()
    ]

    aliases = {
        key.removeprefix(f'{name}_'): key
        for key in tree.keys()
        if key.startswith(name)
    }
    aliases['size'] = f'n{name}'

    expressions = list(aliases.keys()) + ['run', 'luminosityBlock', 'event'] + optional_event_keys
    cut = f'(n{name} > 0)'

    trial_tree: dict[str, np.ndarray] = tree.arrays(
        expressions=expressions,
        aliases=aliases,
        cut=cut,
        library='np'
    )

    run = np.asarray(trial_tree.pop('run'), dtype=np.uint32)
    lumi_block = np.asarray(trial_tree.pop('luminosityBlock'), dtype=np.uint32)
    event = np.asarray(trial_tree.pop('event'), dtype=np.uint64)
    size = np.asarray(trial_tree.pop('size'), dtype=np.int32)

    optional_event_arrays = {
        key: np.asarray(trial_tree.pop(key))
        for key in optional_event_keys
    }

    lumi_block_checker = LumiBlockChecker.from_json(cert_path)
    lumi_mask = lumi_block_checker.get_lumi_mask(run, lumi_block)

    run = run[lumi_mask]
    lumi_block = lumi_block[lumi_mask]
    event = event[lumi_mask]
    size = size[lumi_mask]

    optional_event_arrays = {
        key: value[lumi_mask]
        for key, value in optional_event_arrays.items()
    }

    trial_tree = {
        key: value[lumi_mask]
        for key, value in trial_tree.items()
    }

    flat_trial_tree = {}
    for key, value in trial_tree.items():
        flat_value = np.concatenate(value) if len(value) > 0 else np.array([])

        if key in float_keys:
            flat_trial_tree[key] = np.asarray(flat_value, dtype=np.float64)
        elif key in int_keys:
            flat_trial_tree[key] = np.asarray(flat_value, dtype=np.int32)
        elif key in bool_keys:
            flat_trial_tree[key] = np.asarray(flat_value, dtype=np.bool_)
        else:
            flat_trial_tree[key] = np.asarray(flat_value)

    total_size = int(np.sum(size, dtype=np.int64))

    if total_size > 0:
        flat_trial_tree['run'] = np.asarray(np.repeat(run, size), dtype=np.uint32)
        flat_trial_tree['luminosityBlock'] = np.asarray(np.repeat(lumi_block, size), dtype=np.uint32)
        flat_trial_tree['event'] = np.asarray(np.repeat(event, size), dtype=np.uint64)

        for key, value in optional_event_arrays.items():
            flat_trial_tree[key] = np.asarray(np.repeat(value, size), dtype=value.dtype)

        flat_trial_tree['pair_index'] = np.zeros(total_size, dtype=np.int32)
        flat_trial_tree['nrpcTnP'] = np.asarray(np.repeat(size, size), dtype=np.int32)

        trial_index = []
        for n in size:
            n = int(n)
            if n > 0:
                trial_index.append(np.arange(n, dtype=np.int32))

        flat_trial_tree['trial_index'] = (
            np.concatenate(trial_index)
            if len(trial_index) > 0 else np.array([], dtype=np.int32)
        )
    else:
        flat_trial_tree['run'] = np.array([], dtype=np.uint32)
        flat_trial_tree['luminosityBlock'] = np.array([], dtype=np.uint32)
        flat_trial_tree['event'] = np.array([], dtype=np.uint64)

        for key in optional_event_keys:
            flat_trial_tree[key] = np.array([], dtype=optional_event_arrays[key].dtype)

        flat_trial_tree['pair_index'] = np.array([], dtype=np.int32)
        flat_trial_tree['nrpcTnP'] = np.array([], dtype=np.int32)
        flat_trial_tree['trial_index'] = np.array([], dtype=np.int32)

    return flat_trial_tree


def read_nanoaod_by_pair(path,
                         cert_path: Path,
                         treepath: str = 'Events',
                         name: str = 'rpcTnP',
):
    tree = uproot.open(f'{path}:{treepath}')

    pair_keys = [
        'tag_pt', 'tag_eta', 'tag_phi',
        'probe_pt', 'probe_eta', 'probe_phi',
        'probe_time',
        'dimuon_pt', 'dimuon_mass',
    ]

    optional_event_keys = [
        key for key in ('bunchCrossing', 'orbitNumber')
        if key in tree.keys()
    ]

    aliases = {
        key.removeprefix(f'{name}_'): key
        for key in tree.keys()
        if key.startswith(name) and key.removeprefix(f'{name}_') in pair_keys
    }
    aliases['size'] = f'n{name}'

    expressions = list(aliases.keys()) + ['run', 'luminosityBlock', 'event'] + optional_event_keys
    cut = f'(n{name} > 0)'

    pair_tree: dict[str, np.ndarray] = tree.arrays(
        expressions=expressions,
        aliases=aliases,
        cut=cut,
        library='np'
    )

    run = np.asarray(pair_tree.pop('run'), dtype=np.uint32)
    lumi_block = np.asarray(pair_tree.pop('luminosityBlock'), dtype=np.uint32)
    event = np.asarray(pair_tree.pop('event'), dtype=np.uint64)
    size = np.asarray(pair_tree.pop('size'), dtype=np.int32)

    optional_event_arrays = {
        key: np.asarray(pair_tree.pop(key))
        for key in optional_event_keys
    }

    lumi_block_checker = LumiBlockChecker.from_json(cert_path)
    lumi_mask = lumi_block_checker.get_lumi_mask(run, lumi_block)

    run = run[lumi_mask]
    lumi_block = lumi_block[lumi_mask]
    event = event[lumi_mask]
    size = size[lumi_mask]

    optional_event_arrays = {
        key: value[lumi_mask]
        for key, value in optional_event_arrays.items()
    }

    filtered_pair_tree = {
        key: value[lumi_mask]
        for key, value in pair_tree.items()
    }

    flat_pair_tree = {}
    for key in pair_keys:
        arr = filtered_pair_tree[key]
        flat_pair_tree[key] = (
            np.asarray([x[0] for x in arr], dtype=np.float64)
            if len(arr) > 0 else np.array([], dtype=np.float64)
        )

    flat_pair_tree['run'] = np.asarray(run, dtype=np.uint32)
    flat_pair_tree['luminosityBlock'] = np.asarray(lumi_block, dtype=np.uint32)
    flat_pair_tree['event'] = np.asarray(event, dtype=np.uint64)

    for key, value in optional_event_arrays.items():
        flat_pair_tree[key] = np.asarray(value, dtype=value.dtype)

    flat_pair_tree['pair_index'] = np.zeros(len(run), dtype=np.int32)
    flat_pair_tree['nrpcTnP'] = np.asarray(size, dtype=np.int32)

    return flat_pair_tree


def flatten_nanoaod(input_path: Path,
                    cert_path: Path,
                    output_path: Path,
                    name: str = 'rpcTnP',
):
    trial_tree = read_nanoaod_by_trial(
        path=input_path,
        cert_path=cert_path,
        treepath='Events',
        name=name,
    )

    pair_tree = read_nanoaod_by_pair(
        path=input_path,
        cert_path=cert_path,
        treepath='Events',
        name=name,
    )

    trial_branches = {
        key: np.asarray(value).dtype
        for key, value in trial_tree.items()
    }
    pair_branches = {
        key: np.asarray(value).dtype
        for key, value in pair_tree.items()
    }

    with uproot.writing.create(output_path) as output_file:
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
