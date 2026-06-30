from __future__ import annotations

from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.HistBuild import write_histogram_shard  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.TreeBuild import build_pair_tree, build_rpc_tree, read_nanoaod_base  # type: ignore


def analyze(
    input_path: Path,
    cert_path: Path,
    output_path: Path,
    roll_blacklist_path: Path,
) -> None:
    base_tree = read_nanoaod_base(input_path, cert_path)
    rpc_tree = build_rpc_tree(base_tree)
    pair_tree = build_pair_tree(base_tree)
    write_histogram_shard(
        output_path,
        pair_tree,
        rpc_tree,
        roll_blacklist_path=roll_blacklist_path,
    )
