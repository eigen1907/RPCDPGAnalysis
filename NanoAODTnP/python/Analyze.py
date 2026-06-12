from __future__ import annotations

from pathlib import Path

from RPCDPGAnalysis.NanoAODTnP.HistBuild import write_histogram_shard  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.TreeBuild import build_pair_tree, build_rpc_tree, read_nanoaod_base, write_flat_root  # type: ignore


def analyze(
    input_path: Path,
    cert_path: Path,
    output_path: Path,
    roll_blacklist_path: Path,
    tree_output_path: Path | None = None,
    name: str = "rpcTnP",
) -> None:
    if tree_output_path is not None and tree_output_path == output_path:
        raise ValueError(f"Histogram and tree outputs must be different files: {output_path}")

    base_tree, optional_event_keys = read_nanoaod_base(input_path, cert_path, name=name)
    rpc_tree = build_rpc_tree(base_tree, optional_event_keys)
    pair_tree = build_pair_tree(base_tree, optional_event_keys)
    write_histogram_shard(
        output_path,
        pair_tree,
        rpc_tree,
        roll_blacklist_path=roll_blacklist_path,
    )

    if tree_output_path is not None:
        tree_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_flat_root(tree_output_path, pair_tree, rpc_tree)
