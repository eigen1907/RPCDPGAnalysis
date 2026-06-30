from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


BRILCALC_TIME_FORMAT = "%m/%d/%y %H:%M:%S"
TIME_BIN_LUMI_FB = 1.0


@dataclass(frozen=True)
class RunMeta:
    runs: np.ndarray
    fills: np.ndarray
    timestamps: np.ndarray
    recorded_lumis: np.ndarray
    integrated_lumis: np.ndarray
    time_bin_timestamps: np.ndarray

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

    def lookup_timestamps(self, runs: np.ndarray) -> np.ndarray:
        return self.timestamps[self._indices(runs)]

    def lookup_time_bin_timestamps(self, runs: np.ndarray) -> np.ndarray:
        return self.time_bin_timestamps[self._indices(runs)]

    def lookup_integrated_lumis(self, runs: np.ndarray) -> np.ndarray:
        return self.integrated_lumis[self._indices(runs)]


def integrated_lumi_edges(run_meta: RunMeta) -> np.ndarray:
    high = np.ceil(np.max(run_meta.integrated_lumis))
    return np.arange(0.0, high + 1.0, 1.0, dtype=np.float64)


def _time_bin_timestamps(
    fills: np.ndarray,
    timestamps: np.ndarray,
    recorded_lumis: np.ndarray,
    target_lumi: float = TIME_BIN_LUMI_FB,
) -> np.ndarray:
    fill_order = tuple(dict.fromkeys(int(fill) for fill in fills))
    lumi_by_fill = {
        fill: float(np.sum(recorded_lumis[fills == fill]))
        for fill in fill_order
    }
    year_by_fill = {
        fill: int(str(np.min(timestamps[fills == fill]).astype("datetime64[Y]"))[:4])
        for fill in fill_order
    }
    groups: list[tuple[int, ...]] = []
    group: list[int] = []
    group_lumi = 0.0
    group_year: int | None = None
    for fill in fill_order:
        if group and year_by_fill[fill] != group_year:
            groups.append(tuple(group))
            group = []
            group_lumi = 0.0
        group.append(fill)
        group_lumi += lumi_by_fill[fill]
        group_year = year_by_fill[fill]
        if group_lumi >= target_lumi:
            groups.append(tuple(group))
            group = []
            group_lumi = 0.0
            group_year = None
    if group:
        groups.append(tuple(group))

    balanced_groups: list[tuple[int, ...]] = []
    for grouped_fills in groups:
        group_lumi = sum(lumi_by_fill[fill] for fill in grouped_fills)
        group_year = year_by_fill[grouped_fills[0]]
        if (
            group_lumi < target_lumi
            and balanced_groups
            and year_by_fill[balanced_groups[-1][0]] == group_year
        ):
            balanced_groups[-1] = balanced_groups[-1] + grouped_fills
        else:
            balanced_groups.append(grouped_fills)

    seconds = timestamps.astype("datetime64[s]").astype(np.int64)
    labels = np.empty(len(fills), dtype="datetime64[s]")
    for grouped_fills in balanced_groups:
        selected = np.isin(fills, grouped_fills)
        weights = recorded_lumis[selected]
        if np.sum(weights) > 0.0:
            timestamp = int(np.rint(np.average(seconds[selected], weights=weights)))
        else:
            timestamp = int(np.rint(np.mean(seconds[selected])))
        labels[selected] = np.datetime64(timestamp, "s")
    return labels


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


def read_run_meta(path: Path) -> RunMeta:
    by_run: dict[int, tuple[int, int, float]] = {}
    for run, fill, timestamp, recorded in _iter_run_meta_rows(path):
        by_run[run] = fill, timestamp, recorded

    runs = np.asarray(sorted(by_run), dtype=np.uint32)
    fills = np.asarray([by_run[int(run)][0] for run in runs], dtype=np.uint32)
    timestamps = np.asarray([by_run[int(run)][1] for run in runs], dtype="datetime64[s]")
    recorded_lumis = np.asarray([by_run[int(run)][2] for run in runs], dtype=np.float64)
    # Preserve raw BRIL corrections while keeping the plotting coordinate monotonic.
    integrated_lumis = np.maximum.accumulate(np.cumsum(recorded_lumis))
    time_bin_timestamps = _time_bin_timestamps(fills, timestamps, recorded_lumis)
    return RunMeta(runs, fills, timestamps, recorded_lumis, integrated_lumis, time_bin_timestamps)
