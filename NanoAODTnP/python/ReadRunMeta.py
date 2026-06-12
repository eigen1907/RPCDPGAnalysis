from __future__ import annotations

import csv
import glob
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


BRILCALC_FILENAME = "brilcalc_processed_golden.csv"
BRILCALC_TIME_FORMAT = "%m/%d/%y %H:%M:%S"


def _flatten_paths(paths: Sequence[Path | str | Sequence[Path | str]]) -> Iterable[Path]:
    for path in paths:
        if isinstance(path, (str, Path)):
            yield Path(path)
        else:
            yield from _flatten_paths(path)


def resolve_run_meta_files(paths: Sequence[Path | str | Sequence[Path | str]]) -> list[Path]:
    files: list[Path] = []
    for path in _flatten_paths(paths):
        text = str(path)
        if any(token in text for token in "*?[]"):
            files.extend(Path(each) for each in sorted(glob.glob(text, recursive=True)))
        elif path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob(BRILCALC_FILENAME)))
        else:
            raise FileNotFoundError(f"Run metadata path does not exist: {path}")

    unique_files = list(dict.fromkeys(path.resolve() for path in files if path.is_file()))
    if not unique_files:
        raise FileNotFoundError(f"No run metadata CSV files found in: {paths}")
    return unique_files


@dataclass(frozen=True)
class RunMeta:
    runs: np.ndarray
    months: np.ndarray
    integrated_lumis: np.ndarray

    def _indices(self, runs: np.ndarray) -> np.ndarray:
        values = np.asarray(runs, dtype=np.uint32)
        flat_values = values.reshape(-1)
        indices = np.searchsorted(self.runs, flat_values)
        found = indices < len(self.runs)
        found[found] &= self.runs[indices[found]] == flat_values[found]
        if not np.all(found):
            missing = np.unique(flat_values[~found])
            preview = ", ".join(str(int(run)) for run in missing[:10])
            suffix = " ..." if len(missing) > 10 else ""
            raise RuntimeError(f"Missing run metadata for run(s): {preview}{suffix}")
        return indices.reshape(values.shape)

    def lookup_months(self, runs: np.ndarray) -> np.ndarray:
        return self.months[self._indices(runs)]

    def lookup_integrated_lumis(self, runs: np.ndarray) -> np.ndarray:
        return self.integrated_lumis[self._indices(runs)]


def integrated_lumi_edges(run_meta: RunMeta) -> np.ndarray:
    high = np.ceil(np.max(run_meta.integrated_lumis))
    return np.arange(0.0, high + 1.0, 1.0, dtype=np.float64)


def _iter_run_meta_rows(path: Path):
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
                recorded = float(row[columns["recorded(/fb)"]]) if "recorded(/fb)" in columns else 0.0
                yield int(run_text), int(fill_text), int(timestamp.timestamp()), recorded
            except (IndexError, ValueError) as exc:
                raise RuntimeError(f"Malformed run metadata row in {path}: {row}") from exc


def read_run_meta(paths: Sequence[Path | str | Sequence[Path | str]]) -> RunMeta:
    by_run: dict[int, tuple[int, int, float]] = {}
    for path in resolve_run_meta_files(paths):
        for run, fill, timestamp, recorded in _iter_run_meta_rows(path):
            if run in by_run:
                previous_fill, previous_timestamp, previous_recorded = by_run[run]
                if fill != previous_fill:
                    raise RuntimeError(
                        f"Conflicting fill metadata for run {run}: {previous_fill} != {fill}"
                    )
                timestamp = min(timestamp, previous_timestamp)
                recorded = max(recorded, previous_recorded)
            by_run[run] = fill, timestamp, recorded

    runs = np.asarray(sorted(by_run), dtype=np.uint32)
    timestamps = np.asarray([by_run[int(run)][1] for run in runs], dtype=np.int64)
    recorded_lumis = np.asarray([by_run[int(run)][2] for run in runs], dtype=np.float64)
    # Preserve raw BRIL corrections while keeping the plotting coordinate monotonic.
    integrated_lumis = np.maximum.accumulate(np.cumsum(recorded_lumis))
    months = np.asarray([
        datetime.fromtimestamp(int(timestamp), timezone.utc).strftime("%Y-%m")
        for timestamp in timestamps
    ], dtype=str)
    return RunMeta(runs, months, integrated_lumis)
