#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Sequence


PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GEOM_PATH = PACKAGE_DIR / "data/geometry/run3.csv"
DEFAULT_BLACKLIST_DIR = PACKAGE_DIR / "data/blacklist/roll"
DEFAULT_OUTPUT = DEFAULT_BLACKLIST_DIR / "run3.csv"
DEFAULT_YEARS = ("2022", "2023", "2024", "2025", "2026")
IRPC_ROLL_PREFIXES = ("RE+3_R1_", "RE-3_R1_", "RE+4_R1_", "RE-4_R1_")


def is_irpc_roll_name(roll_name: str) -> bool:
    return roll_name.startswith(IRPC_ROLL_PREFIXES)


def load_roll_blacklist(path: Path) -> set[str]:
    names: set[str] = set()
    with path.open() as stream:
        for raw_line in stream:
            columns = raw_line.split("#", 1)[0].split()
            if columns:
                names.add(columns[1] if len(columns) > 1 else columns[0])
    return names


def load_roll_names(path: Path, include_irpc: bool) -> set[str]:
    with path.open(newline="") as stream:
        names = {
            row["roll_name"].strip()
            for row in csv.DictReader(stream)
            if row.get("roll_name", "").strip()
        }
    if include_irpc:
        return names
    return {name for name in names if not is_irpc_roll_name(name)}


def parse_years(values: Sequence[str]) -> list[str]:
    years: list[str] = []
    for value in values:
        for token in value.replace(",", " ").split():
            if token.startswith("Run"):
                token = token[3:]
            if token:
                years.append(token)
    return years


def summarize_blacklists(
    geom_path: Path,
    blacklist_dir: Path,
    years: Sequence[str],
    include_irpc: bool = False,
) -> list[list[int | str]]:
    roll_names = load_roll_names(geom_path, include_irpc)
    barrel_rolls = {name for name in roll_names if name.startswith("W")}
    endcap_rolls = {name for name in roll_names if name.startswith("RE")}

    rows: list[list[int | str]] = []
    for year in years:
        blacklist_path = blacklist_dir / f"blackList{year}.txt"
        if not blacklist_path.is_file():
            raise FileNotFoundError(f"missing blacklist file: {blacklist_path}")

        blacklist = load_roll_blacklist(blacklist_path)
        if not include_irpc:
            blacklist = {name for name in blacklist if not is_irpc_roll_name(name)}

        matched_blacklist = blacklist & roll_names
        unknown_blacklist = sorted(blacklist - roll_names)
        if unknown_blacklist:
            print(
                f"[warn] Run{year}: ignored {len(unknown_blacklist)} blacklist entries not in geometry",
                file=sys.stderr,
            )

        rows.append([
            year,
            len(roll_names),
            len(matched_blacklist),
            len(barrel_rolls),
            len(matched_blacklist & barrel_rolls),
            len(endcap_rolls),
            len(matched_blacklist & endcap_rolls),
        ])
    return rows


def write_summary(path: Path, rows: Sequence[Sequence[int | str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    with temporary_path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([
            "year",
            "total_rolls",
            "blacklist_rolls",
            "total_barrel_rolls",
            "blacklist_barrel_rolls",
            "n_endcap_rolls",
            "n_endcap_blacklist",
        ])
        writer.writerows(rows)
    temporary_path.replace(path)
    return path


def parse_args() -> argparse.Namespace:
    default_years = parse_years([os.environ.get("RUN3_YEARS", " ".join(DEFAULT_YEARS))])
    default_include_irpc = os.environ.get("INCLUDE_IRPC", "0") == "1"

    parser = argparse.ArgumentParser(description="Build yearly RPC roll blacklist summary metadata.")
    parser.add_argument("-g", "--geom-path", type=Path, default=Path(os.environ.get("GEOM_PATH", DEFAULT_GEOM_PATH)),
                        help=f"RPC roll geometry CSV. Default: {DEFAULT_GEOM_PATH}")
    parser.add_argument("-b", "--blacklist-dir", type=Path,
                        default=Path(os.environ.get("BLACKLIST_DIR", DEFAULT_BLACKLIST_DIR)),
                        help=f"Directory containing blackListYYYY.txt files. Default: {DEFAULT_BLACKLIST_DIR}")
    parser.add_argument("-o", "--output", type=Path, default=Path(os.environ.get("OUT_PATH", DEFAULT_OUTPUT)),
                        help=f"Blacklist summary CSV. Default: {DEFAULT_OUTPUT}")
    parser.add_argument("-y", "--years", nargs="+", default=default_years,
                        help=f"Years to summarize. Default: {' '.join(DEFAULT_YEARS)}")
    parser.add_argument("--include-irpc", action="store_true", default=default_include_irpc,
                        help="Include iRPC rolls. Default excludes them to match the analysis histogram policy.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = parse_years(args.years)
    if not years:
        raise ValueError("No years were provided")
    if not args.geom_path.is_file():
        raise FileNotFoundError(f"missing geometry CSV: {args.geom_path}")
    if not args.blacklist_dir.is_dir():
        raise FileNotFoundError(f"missing blacklist directory: {args.blacklist_dir}")

    rows = summarize_blacklists(args.geom_path, args.blacklist_dir, years, args.include_irpc)
    output_path = write_summary(args.output, rows)
    print(f"[done] summarized {len(rows)} years: {output_path}", flush=True)
    if not args.include_irpc:
        print("[info] iRPC rolls excluded; pass --include-irpc or set INCLUDE_IRPC=1 to include them", flush=True)


if __name__ == "__main__":
    main()
