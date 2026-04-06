#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
import uproot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="rechits.root")
    args = parser.parse_args()

    branches = [
        "run",
        "lumi",
        "event",
        "roll_name",
        "local_x",
        "local_y",
        "local_z",
        "global_x",
        "global_y",
        "global_z",
    ]

    tree_info = {
        "rpcRecHitTree": "RPCRecHit",
        "rpcRecHitPhase2Tree": "RPCRecHitPhase2",
    }

    data = {}

    with uproot.open(args.input) as f:
        for tree_name in tree_info:
            tree = f["rpcRecHitDumper/" + tree_name]
            arr = tree.arrays(branches, library="np")

            events = defaultdict(list)
            n = len(arr["event"])

            for i in range(n):
                key = (
                    int(arr["run"][i]),
                    int(arr["lumi"][i]),
                    int(arr["event"][i]),
                )

                roll_name = arr["roll_name"][i]
                if isinstance(roll_name, bytes):
                    roll_name = roll_name.decode("utf-8")

                events[key].append({
                    "roll_name": roll_name,
                    "local_x": float(arr["local_x"][i]),
                    "local_y": float(arr["local_y"][i]),
                    "local_z": float(arr["local_z"][i]),
                    "global_x": float(arr["global_x"][i]),
                    "global_y": float(arr["global_y"][i]),
                    "global_z": float(arr["global_z"][i]),
                })

            data[tree_name] = events

    all_events = set()
    for tree_name in tree_info:
        all_events |= set(data[tree_name].keys())

    for run, lumi, event in sorted(all_events):
        print("=" * 120)
        print(f"Event: run={run}, lumi={lumi}, event={event}")

        for tree_name, label in tree_info.items():
            rows = data[tree_name].get((run, lumi, event), [])

            print(f"  [{label}] {len(rows)} objects")
            for i, row in enumerate(rows):
                print(
                    f"    {i:3d}  "
                    f"roll_name={row['roll_name']}  "
                    f"local=({row['local_x']:.3f}, {row['local_y']:.3f}, {row['local_z']:.3f})  "
                    f"global=({row['global_x']:.3f}, {row['global_y']:.3f}, {row['global_z']:.3f})"
                )


if __name__ == "__main__":
    main()