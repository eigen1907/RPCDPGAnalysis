#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCDetId


ROLL_ID_KEYS = (
    "region",
    "ring",
    "station",
    "sector",
    "layer",
    "subsector",
    "roll",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        type=Path,
        help="Input ROOT file."
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output JSON path."
    )
    parser.add_argument(
        "--tree-name",
        default="trial_tree",
        help="Input tree name."
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="Exclude rolls with efficiency <= threshold (percent)."
    )
    parser.add_argument(
        "--min-total",
        type=int,
        default=1,
        help="Minimum number of total trials required to consider a roll."
    )
    parser.add_argument(
        "--sort-by",
        default="name",
        choices=["name", "efficiency", "total"],
        help="Sorting key for excluded rolls."
    )

    return parser.parse_args()


def load_arrays(path: Path, tree_name: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            raise RuntimeError(f"Missing tree '{tree_name}' in {path}")

        tree = root_file[tree_name]
        needed_keys = list(ROLL_ID_KEYS) + ["is_matched"]

        missing = [key for key in needed_keys if key not in tree.keys()]
        if missing:
            raise RuntimeError(
                f"Missing branches in {path}:{tree_name}: {', '.join(missing)}"
            )

        arrays = tree.arrays(needed_keys, library="ak")

    out: dict[str, np.ndarray] = {}
    for key in needed_keys:
        out[key] = np.asarray(ak.to_numpy(arrays[key]))

    return out


def make_roll_name(
    region: int,
    ring: int,
    station: int,
    sector: int,
    layer: int,
    subsector: int,
    roll: int,
) -> str:
    det_id = RPCDetId(
        region=int(region),
        ring=int(ring),
        station=int(station),
        sector=int(sector),
        layer=int(layer),
        subsector=int(subsector),
        roll=int(roll),
    )
    return det_id.name


def is_irpc_roll(
    region: int,
    ring: int,
    station: int,
) -> bool:
    return (region != 0) and (ring == 1) and (station in (3, 4))


def build_roll_table(arrays: dict[str, np.ndarray]) -> list[dict]:
    region = arrays["region"].astype(np.int32)
    ring = arrays["ring"].astype(np.int32)
    station = arrays["station"].astype(np.int32)
    sector = arrays["sector"].astype(np.int32)
    layer = arrays["layer"].astype(np.int32)
    subsector = arrays["subsector"].astype(np.int32)
    roll = arrays["roll"].astype(np.int32)
    is_matched = arrays["is_matched"].astype(bool)

    roll_map: dict[tuple[int, ...], dict[str, int]] = {}

    for values in zip(region, ring, station, sector, layer, subsector, roll, is_matched):
        key = tuple(int(v) for v in values[:-1])
        matched = bool(values[-1])

        if key not in roll_map:
            roll_map[key] = {
                "total": 0,
                "pass": 0,
            }

        roll_map[key]["total"] += 1
        if matched:
            roll_map[key]["pass"] += 1

    table = []
    for key, counts in roll_map.items():
        total = counts["total"]
        passed = counts["pass"]
        efficiency = 100.0 * passed / total if total > 0 else 0.0

        row = {
            "region": key[0],
            "ring": key[1],
            "station": key[2],
            "sector": key[3],
            "layer": key[4],
            "subsector": key[5],
            "roll": key[6],
            "total": total,
            "pass": passed,
            "efficiency_percent": efficiency,
            "name": make_roll_name(*key),
            "is_irpc": is_irpc_roll(
                region=key[0],
                ring=key[1],
                station=key[2],
            ),
        }
        table.append(row)

    return table


def sort_roll_table(rows: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "name":
        return sorted(rows, key=lambda row: row["name"])
    if sort_by == "efficiency":
        return sorted(rows, key=lambda row: (row["efficiency_percent"], row["name"]))
    if sort_by == "total":
        return sorted(rows, key=lambda row: (-row["total"], row["name"]))
    return rows


def main() -> None:
    args = parse_args()

    table = build_roll_table(load_arrays(args.input, args.tree_name))

    total_rolls_including_irpc = len(table)
    total_rolls_excluding_irpc = sum(1 for row in table if not row["is_irpc"])

    excluded = [
        row for row in table
        if row["total"] >= args.min_total and row["efficiency_percent"] <= args.threshold
    ]
    excluded = sort_roll_table(excluded, args.sort_by)

    excluded_no_irpc = [row for row in excluded if not row["is_irpc"]]

    payload = {
        "input": str(args.input),
        "tree_name": args.tree_name,
        "threshold_percent": args.threshold,
        "min_total": args.min_total,
        "n_total_rolls_including_irpc": total_rolls_including_irpc,
        "n_total_rolls_excluding_irpc": total_rolls_excluding_irpc,
        "n_excluded_rolls_including_irpc": len(excluded),
        "n_excluded_rolls_excluding_irpc": len(excluded_no_irpc),
        "excluded_rolls_including_irpc": [row["name"] for row in excluded],
        "excluded_rolls_excluding_irpc": [row["name"] for row in excluded_no_irpc],
        "excluded_roll_details_including_irpc": excluded,
        "excluded_roll_details_excluding_irpc": excluded_no_irpc,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fout:
        json.dump(payload, fout, indent=2, sort_keys=False)

    print(f"[done] saved: {args.output}", flush=True)
    print(f"[info] n_total_rolls_including_irpc = {total_rolls_including_irpc}", flush=True)
    print(f"[info] n_total_rolls_excluding_irpc = {total_rolls_excluding_irpc}", flush=True)
    print(f"[info] n_excluded_rolls_including_irpc = {len(excluded)}", flush=True)
    print(f"[info] n_excluded_rolls_excluding_irpc = {len(excluded_no_irpc)}", flush=True)


if __name__ == "__main__":
    main()