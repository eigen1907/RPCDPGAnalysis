#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import glob
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Iterable, Sequence


PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PACKAGE_DIR / "logs/lumi"
DEFAULT_OUTPUT = PACKAGE_DIR / "data/lumi/run3.csv"
GOLDEN_JSON_FILENAME = "processedLumisGolden.json"
BRILCALC_TIME_FORMAT = "%m/%d/%y %H:%M:%S"
DEFAULT_NORMTAG = Path("/cvmfs/cms-bril.cern.ch/cms-lumi-pog/Normtags/normtag_BRIL.json")


def _flatten_paths(paths: Sequence[Path | str | Sequence[Path | str]]) -> Iterable[Path]:
    for path in paths:
        if isinstance(path, (str, Path)):
            yield Path(path)
        else:
            yield from _flatten_paths(path)


def resolve_golden_json_files(paths: Sequence[Path | str | Sequence[Path | str]]) -> list[Path]:
    files: list[Path] = []
    for path in _flatten_paths(paths):
        text = str(path)
        if any(token in text for token in "*?[]"):
            files.extend(Path(match) for match in sorted(glob.glob(text, recursive=True)))
        elif path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob(GOLDEN_JSON_FILENAME)))
        else:
            raise FileNotFoundError(f"Golden lumi JSON path does not exist: {path}")
    files = list(dict.fromkeys(path.resolve() for path in files if path.is_file()))
    if not files:
        raise FileNotFoundError(f"No {GOLDEN_JSON_FILENAME} files found in: {paths}")
    return files


def _merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def union_golden_lumis(paths: Sequence[Path | str | Sequence[Path | str]]) -> dict[str, list[list[int]]]:
    by_run: defaultdict[str, list[list[int]]] = defaultdict(list)
    for path in resolve_golden_json_files(paths):
        with path.open() as stream:
            payload = json.load(stream)
        for run, ranges in payload.items():
            by_run[str(run)].extend([[int(start), int(end)] for start, end in ranges])
    return {
        run: _merge_ranges(ranges)
        for run, ranges in sorted(by_run.items(), key=lambda item: int(item[0]))
    }


def _iter_brilcalc_rows(path: Path):
    columns: dict[str, int] = {}
    with path.open(newline="") as stream:
        for row in csv.reader(stream):
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                header = [column.lstrip("#").strip().lower() for column in row]
                if header[0] == "run:fill":
                    columns = {column: idx for idx, column in enumerate(header)}
                continue
            try:
                run_text, fill_text = row[0].split(":", 1)
                timestamp = datetime.strptime(row[1], BRILCALC_TIME_FORMAT).replace(tzinfo=timezone.utc)
                yield (
                    int(run_text),
                    int(fill_text),
                    int(timestamp.timestamp()),
                    float(row[columns["delivered(/fb)"]]),
                    float(row[columns["recorded(/fb)"]]),
                )
            except (IndexError, KeyError, ValueError) as exc:
                raise RuntimeError(f"Malformed brilcalc row in {path}: {row}") from exc


def read_run_meta(path: Path) -> list[tuple[int, int, int, float, float, float]]:
    by_run: dict[int, tuple[int, int, float, float]] = {}
    for run, fill, timestamp, delivered, recorded in _iter_brilcalc_rows(path):
        if run in by_run:
            previous_fill, previous_timestamp, previous_delivered, previous_recorded = by_run[run]
            if fill != previous_fill:
                raise RuntimeError(f"Conflicting fill metadata for run {run}: {previous_fill} != {fill}")
            timestamp = min(timestamp, previous_timestamp)
            delivered = max(delivered, previous_delivered)
            recorded = max(recorded, previous_recorded)
        by_run[run] = fill, timestamp, delivered, recorded

    rows = []
    cumulative = 0.0
    integrated = 0.0
    for run in sorted(by_run):
        fill, timestamp, delivered, recorded = by_run[run]
        cumulative += recorded
        integrated = max(integrated, cumulative)
        rows.append((run, fill, timestamp, delivered, recorded, integrated))
    return rows


def read_merged_run_meta(
    paths: Sequence[Path | str | Sequence[Path | str]],
    normtag: Path | str = DEFAULT_NORMTAG,
) -> list[tuple[int, int, int, float, float, float]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        json_path = tmpdir_path / "processedLumisGoldenUnion.json"
        csv_path = tmpdir_path / "brilcalc_processed_golden_union.csv"
        with json_path.open("w") as stream:
            json.dump(union_golden_lumis(paths), stream, sort_keys=True)
        command = [
            "brilcalc", "lumi", "-b", "STABLE BEAMS", "--normtag", str(normtag),
            "--output-style", "csv", "-u", "/fb", "-i", str(json_path), "-o", str(csv_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        if process.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\nstdout:\n{process.stdout}\nstderr:\n{process.stderr}"
            )
        return read_run_meta(csv_path)


def write_run_meta(path: Path | str, rows: Sequence[tuple[int, int, int, float, float, float]]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    with temporary_path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["# Merged run metadata for plotting. One row per run."])
        writer.writerow(["#run:fill", "time", "delivered(/fb)", "recorded(/fb)", "integrated_recorded(/fb)"])
        for run, fill, timestamp, delivered, recorded, integrated in rows:
            time_text = datetime.fromtimestamp(timestamp, timezone.utc).strftime(BRILCALC_TIME_FORMAT)
            writer.writerow([f"{run}:{fill}", time_text, f"{delivered:.9f}", f"{recorded:.9f}", f"{integrated:.9f}"])
    temporary_path.replace(output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build merged run-level luminosity metadata for later plotting.")
    parser.add_argument("inputs", nargs="*", type=Path, default=[DEFAULT_INPUT],
                        help=f"Input golden lumi JSON, directory, or glob. Default: {DEFAULT_INPUT}")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Merged run metadata CSV. Default: {DEFAULT_OUTPUT}")
    parser.add_argument("--normtag", type=Path, default=DEFAULT_NORMTAG,
                        help=f"brilcalc normtag JSON. Default: {DEFAULT_NORMTAG}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_merged_run_meta(args.inputs, args.normtag)
    output_path = write_run_meta(args.output, rows)
    print(f"[done] merged {len(rows)} runs: {output_path}", flush=True)


if __name__ == "__main__":
    main()
