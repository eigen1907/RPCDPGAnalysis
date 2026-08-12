from __future__ import annotations

from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.HistBuild import write_histogram_shard  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.TreeBuild import build_pair_tree, build_rpc_tree, read_nanoaod_base  # type: ignore


def analyze(
    input_path: Path,
    cert_path: Path,
    output_path: Path,
    roll_blacklist_path: Path | None,
    run_blacklist_path: Path | None = None,
    apply_roll_blacklist: bool = True,
    apply_run_blacklist: bool = True,
    tight_match: bool = False,
    probe_pt_gt15: bool = True,
    bx_zero: bool = False,
) -> None:
    base_tree = read_nanoaod_base(input_path, cert_path)
    rpc_tree = build_rpc_tree(base_tree)
    pair_tree = build_pair_tree(base_tree)
    write_histogram_shard(
        output_path,
        pair_tree,
        rpc_tree,
        roll_blacklist_path=roll_blacklist_path,
        run_blacklist_path=run_blacklist_path,
        apply_roll_blacklist=apply_roll_blacklist,
        apply_run_blacklist=apply_run_blacklist,
        tight_match=tight_match,
        probe_pt_gt15=probe_pt_gt15,
        bx_zero=bx_zero,
    )
