from __future__ import annotations

from dataclasses import dataclass

from hist.intervals import clopper_pearson_interval
import numpy as np
import pandas as pd


def poisson_yerr(counts: np.ndarray, log_scale: bool = False) -> np.ndarray:
    err = np.sqrt(np.clip(counts, 0.0, None))
    if log_scale:
        return np.vstack((np.minimum(err, 0.95 * counts), err))
    return err


def clopper_pearson_count_yerr(counts: np.ndarray) -> np.ndarray:
    total = int(np.sum(counts))
    if total <= 0:
        return np.zeros((2, len(counts)), dtype=np.float64)
    intervals = total * clopper_pearson_interval(
        counts.astype(np.float64),
        np.full_like(counts, total, dtype=np.float64),
    )
    return np.vstack((counts - intervals[0], intervals[1] - counts))


def clopper_pearson_efficiency_yerr(passed: np.ndarray, total: np.ndarray, min_total: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = total >= min_total
    efficiency = np.zeros_like(total, dtype=np.float64)
    efficiency[mask] = 100.0 * passed[mask] / total[mask]
    intervals = 100.0 * clopper_pearson_interval(passed[mask], total[mask])
    yerr = np.vstack((efficiency[mask] - intervals[0], intervals[1] - efficiency[mask]))
    return mask, efficiency[mask], yerr


def mean_and_error(value_sum: np.ndarray, value_sumsq: np.ndarray, counts: np.ndarray, min_count: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = counts >= min_count
    mean = np.zeros_like(value_sum, dtype=np.float64)
    mean[mask] = value_sum[mask] / counts[mask]
    variance = np.zeros_like(mean)
    variance[mask] = np.maximum(value_sumsq[mask] / counts[mask] - mean[mask] * mean[mask], 0.0)
    yerr = np.zeros_like(mean)
    yerr[mask] = np.sqrt(variance[mask] / counts[mask])
    return mask, mean[mask], yerr[mask]


def efficiency_series(total_by_roll: pd.Series, passed_by_roll: pd.Series) -> pd.Series:
    index = total_by_roll.index.union(passed_by_roll.index)
    total = total_by_roll.reindex(index, fill_value=0).astype(np.float64)
    passed = passed_by_roll.reindex(index, fill_value=0).astype(np.float64)
    return 100.0 * passed.divide(total).where(total > 0.0)


def efficiency_stats(efficiencies: np.ndarray, threshold: float) -> tuple[float, float]:
    valid = efficiencies[np.isfinite(efficiencies)]
    if len(valid) == 0:
        return np.nan, np.nan
    good = valid[valid > threshold]
    mean_good = float(np.mean(good)) if len(good) else np.nan
    frac_bad = 100.0 * float(np.sum(valid <= threshold)) / float(len(valid))
    return mean_good, frac_bad


@dataclass(frozen=True)
class RollMeanResult:
    mean_by_roll: dict[str, pd.Series]
    mean_count_by_roll: dict[str, pd.Series]


@dataclass(frozen=True)
class RollEfficiencyResult:
    total_by_roll: pd.Series
    passed_by_roll: pd.Series
    efficiency_by_region: dict[str, np.ndarray]
