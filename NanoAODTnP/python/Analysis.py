import json
from typing import Optional
from pathlib import Path
from functools import singledispatchmethod
import numpy as np
import numpy.typing as npt
from dataclasses import dataclass
import awkward as ak
import uproot
import pandas as pd
from hist.hist import Hist
from hist.axis import StrCategory, IntCategory
from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import get_roll_name


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


def get_roll_mask(roll_name: np.ndarray,
                  roll_mask_path: Path,
):
    if roll_mask_path is None:
        masked_rolls = set()
    with open(roll_mask_path) as stream:
        masked_rolls = set(json.load(stream))

    roll_mask = np.vectorize(lambda roll: roll not in masked_rolls)(roll_name)
    return roll_mask

def get_run_mask(runs: np.ndarray,
                 run_mask_path: Path,      
):
    if run_mask_path is None:
        masked_runs = set()
    with open(run_mask_path) as stream:
        masked_runs = set((json.load(stream)))

    run_mask = np.vectorize(lambda run: run not in masked_runs)(runs)
    return run_mask

def read_nanoaod_by_hit(path,
                        cert_path: Path,
                        treepath: str = 'Events',
                        name: str = 'rpcTnP',
):
    tree = uproot.open(f'{path}:{treepath}')

    aliases = {key.removeprefix(f'{name}_'): key
               for key in tree.keys()
               if key.startswith(name)}
    # number of measurements
    aliases['size'] = f'n{name}'
    expressions = list(aliases.keys()) + ['run', 'luminosityBlock', 'event']
    cut = f'(n{name} > 0)'

    hit_tree: dict[str, np.ndarray] = tree.arrays(
        expressions = expressions,
        aliases = aliases,
        cut = cut,
        library = 'np'
    )

    run = hit_tree.pop('run')
    lumi_block = hit_tree.pop('luminosityBlock')
    event = hit_tree.pop('event')
    size = hit_tree.pop('size')

    lumi_block_checker = LumiBlockChecker.from_json(cert_path)
    lumi_mask = lumi_block_checker.get_lumi_mask(run, lumi_block)
    hit_tree = {key: value[lumi_mask] for key, value in hit_tree.items()}
    hit_tree = {key: np.concatenate(value) for key, value in hit_tree.items()}

    hit_tree['run'] = np.repeat(run[lumi_mask], size[lumi_mask])
    hit_tree['luminosityBlock'] = np.repeat(lumi_block[lumi_mask], size[lumi_mask])
    hit_tree['event'] = np.repeat(event[lumi_mask], size[lumi_mask])
    return hit_tree

def read_nanoaod_by_muon(path,
                         cert_path: Path,
                         treepath: str = 'Events',
                         name: str = 'rpcTnP',
):
    tree = uproot.open(f'{path}:{treepath}')

    muon_keys = ['tag_pt', 'tag_eta', 'tag_phi', 
                 'probe_pt', 'probe_eta', 'probe_phi', 
                 'probe_time', 'probe_dxdz', 'probe_dydz', 
                 'dimuon_pt', 'dimuon_mass']
    
    aliases = {key.removeprefix(f'{name}_'): key
               for key in tree.keys()
               if (key.startswith(name) and key.removeprefix(f'{name}_') in muon_keys)}
    aliases['size'] = f'n{name}'
    expressions = list(aliases.keys()) + ['run', 'luminosityBlock', 'event']
    cut = f'(n{name} > 0)'
    
    muon_tree: dict[str, np.ndarray] = tree.arrays(
        expressions = expressions,
        aliases = aliases,
        cut = cut,
        library = 'np'        
    )
    
    run = muon_tree.pop('run')
    lumi_block = muon_tree.pop('luminosityBlock')
    event = muon_tree.pop('event')
    size = muon_tree.pop('size')

    lumi_block_checker = LumiBlockChecker.from_json(cert_path)
    lumi_mask = lumi_block_checker.get_lumi_mask(run, lumi_block)
    muon_tree = {key: value[lumi_mask] for key, value in muon_tree.items()}
    for muon_key in muon_keys:
        muon_var = []
        for i_event in range(len(muon_tree[muon_key])):
            muon_var.append(muon_tree[muon_key][i_event][0])
        muon_tree[muon_key] = muon_var
    
    return muon_tree

def flatten_nanoaod(input_path: Path,
                    cert_path: Path,
                    geom_path: Path,
                    #run_path: Path,
                    output_path: Path,
                    roll_mask_path: Path = None,
                    run_mask_path: Path = None,
                    name: str = 'rpcTnP',
):
    hit_tree = read_nanoaod_by_hit(
        path = input_path,
        cert_path = cert_path,
        treepath = 'Events',
        name = name
    )

    hit_tree['roll_name'] = np.array([
        get_roll_name(hit_tree['region'][i], hit_tree['ring'][i], hit_tree['station'][i],
                      hit_tree['sector'][i], hit_tree['layer'][i], hit_tree['subsector'][i], 
                      hit_tree['roll'][i]) for i in range(len(hit_tree['region']))
    ])

    mask = np.vectorize(lambda roll: roll in {"RE+4_R1_CH15_A", "RE+4_R1_CH16_A", "RE+3_R1_CH15_A", "RE+3_R1_CH16_A"})(hit_tree['roll_name'])
    if run_mask_path is not None:
        mask = mask | get_run_mask(
            runs = hit_tree['run'],
            run_mask_path = run_mask_path,
        )
    if roll_mask_path is not None:
        mask = mask | get_roll_mask(
            roll_name = hit_tree['roll_name'],
            roll_mask_path = roll_mask_path,
        )

    hit_tree = {key: value[~mask] for key, value in hit_tree.items()}

    muon_tree = read_nanoaod_by_muon(
        path = input_path,
        cert_path = cert_path,
        treepath = 'Events',
        name = name
    )

    geom = pd.read_csv(geom_path)
    roll_axis = StrCategory(geom['roll_name'].tolist())

    run = np.unique(hit_tree['run'])
    run_axis = IntCategory(run.tolist())
    
    h_total_by_roll = Hist(roll_axis) # type: ignore
    h_passed_by_roll = h_total_by_roll.copy()
    h_total_by_roll.fill(hit_tree['roll_name'][hit_tree['is_fiducial']])
    h_passed_by_roll.fill(hit_tree['roll_name'][hit_tree['is_fiducial'] & hit_tree['is_matched']])

    h_total_by_run = Hist(run_axis)
    h_passed_by_run = h_total_by_run.copy()
    h_total_by_run.fill(hit_tree['run'][hit_tree['is_fiducial']])
    h_passed_by_run.fill(hit_tree['run'][hit_tree['is_fiducial'] & hit_tree['is_matched']])

    h_total_by_roll_run = Hist(roll_axis, run_axis)
    h_passed_by_roll_run = h_total_by_roll_run.copy()
    h_total_by_roll_run.fill(hit_tree['roll_name'][hit_tree['is_fiducial']], hit_tree['run'][hit_tree['is_fiducial']])
    h_passed_by_roll_run.fill(hit_tree['roll_name'][hit_tree['is_fiducial'] & hit_tree['is_matched']], 
                              hit_tree['run'][hit_tree['is_fiducial'] & hit_tree['is_matched']])

    roll_name = hit_tree.pop('roll_name')
    
    hit_tree = ak.Array(hit_tree)
    muon_tree = ak.Array(muon_tree)

    with uproot.writing.create(output_path) as output_file:
        output_file['hit_tree'] = hit_tree
        output_file['muon_tree'] = muon_tree
        output_file['total_by_roll'] = h_total_by_roll
        output_file['passed_by_roll'] = h_passed_by_roll
        output_file['total_by_run'] = h_total_by_run
        output_file['passed_by_run'] = h_passed_by_run
        output_file['total_by_roll_run'] = h_total_by_roll_run
        output_file['passed_by_roll_run'] = h_passed_by_roll_run

def merge_trees(tree_list):
    arrays = [tree.arrays(library="ak") for tree in tree_list]
    merged_tree = ak.concatenate(arrays, axis=0)
    return merged_tree

def merge_histograms(hist_list):
    n_axes = len(hist_list[0].axes)
    all_categories = [set() for _ in range(n_axes)]
    for hist in hist_list:
        for i in range(n_axes):
            all_categories[i].update(hist.axes[i])
    combined_axes = []
    for i in range(n_axes):
        if isinstance(hist_list[0].axes[i], StrCategory):
            combined_axes.append(StrCategory(list(all_categories[i])))
        elif isinstance(hist_list[0].axes[i], IntCategory):
            combined_axes.append(IntCategory(list(all_categories[i])))
        else:
            raise ValueError(f"Unsupported axis type.")
    
    combined_hist = Hist(*combined_axes)

    for hist in hist_list:
        if n_axes == 1:
            for cat, val in zip(hist.axes[0], hist.view()):
                combined_hist.fill([cat], weight=[val])
        elif n_axes == 2:
            for x_idx, x_cat in enumerate(hist.axes[0]):
                for y_idx, y_cat in enumerate(hist.axes[1]):
                    value = hist.view(flow=False)[x_idx, y_idx]
                    if value > 0:
                        combined_hist.fill([x_cat], [y_cat], weight=value)            
        else:
            raise ValueError("Only 1D and 2D histograms are supported.")
    return combined_hist

def merge_flat_nanoaod_files(input_paths: Path,
                             output_path: Path,
):
    hit_tree_list = []
    muon_tree_list = []
    h_total_by_roll_list = []
    h_passed_by_roll_list = []
    h_total_by_run_list = []
    h_passed_by_run_list = []
    h_total_by_roll_run_list = []
    h_passed_by_roll_run_list = []

    for input_path in input_paths:
        with uproot.open(input_path) as f:
            hit_tree_list.append(f["hit_tree"])
            muon_tree_list.append(f["muon_tree"])
            h_total_by_roll_list.append(f["total_by_roll"].to_hist())
            h_passed_by_roll_list.append(f["passed_by_roll"].to_hist())
            h_total_by_run_list.append(f["total_by_run"].to_hist())
            h_passed_by_run_list.append(f["passed_by_run"].to_hist())
            h_total_by_roll_run_list.append(f["total_by_roll_run"].to_hist())
            h_passed_by_roll_run_list.append(f["passed_by_roll_run"].to_hist())
    
    merged_hit_tree = merge_trees(hit_tree_list)
    merged_muon_tree = merge_trees(muon_tree_list)
    
    merged_h_total_by_roll = merge_histograms(h_total_by_roll_list)
    merged_h_passed_by_roll = merge_histograms(h_passed_by_roll_list)
    merged_h_total_by_run = merge_histograms(h_total_by_run_list)
    merged_h_passed_by_run = merge_histograms(h_passed_by_run_list)
    merged_h_total_by_roll_run = merge_histograms(h_total_by_roll_run_list)
    merged_h_passed_by_roll_run = merge_histograms(h_passed_by_roll_run_list)

    with uproot.recreate(output_path) as output_file:
        output_file["hit_tree"] = merged_hit_tree
        output_file["muon_tree"] = merged_muon_tree
        
        output_file["total_by_roll"] = merged_h_total_by_roll
        output_file["passed_by_roll"] = merged_h_passed_by_roll
        output_file["total_by_run"] = merged_h_total_by_run
        output_file["passed_by_run"] = merged_h_passed_by_run
        output_file["total_by_roll_run"] = merged_h_total_by_roll_run
        output_file["passed_by_roll_run"] = merged_h_passed_by_roll_run