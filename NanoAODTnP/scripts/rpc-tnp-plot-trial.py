#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import uproot
import matplotlib as mpl
mpl.use("agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import LogLocator, NullFormatter
import mplhep as mh

mh.style.use(mh.styles.CMS)


DEFAULT_COLORS = [
    "firebrick",
    "mediumblue",
    "darkgreen",
    "darkorange",
]

ROLL_KEY_FIELDS = (
    "region",
    "ring",
    "station",
    "sector",
    "layer",
    "subsector",
    "roll",
)

CLS_MIN = 1
CLS_MAX = 10
CLS_NBINS = CLS_MAX - CLS_MIN + 1

BX_MIN = -4
BX_MAX = 4
BX_NBINS = BX_MAX - BX_MIN + 1


@dataclass(frozen=True)
class DatasetSpec:
    year: int
    lumi: float | None
    input_path: Path


@dataclass(frozen=True)
class RegionObservableSummary:
    hist_counts: np.ndarray
    mean_value: float


@dataclass(frozen=True)
class DatasetSummary:
    spec: DatasetSpec
    roll_eff_by_region: dict[str, np.ndarray]
    eff_summary_by_region: dict[str, tuple[float, float]]
    observable_summary_by_region: dict[str, dict[str, RegionObservableSummary]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        dest="inputs",
        action="append",
        required=True,
        type=Path,
        help="Input ROOT file path. Repeat this option for multiple years."
    )
    parser.add_argument(
        "-y", "--year",
        dest="years",
        action="append",
        required=True,
        type=int,
        help="Year label matched to each input. Repeat in the same order as --input."
    )
    parser.add_argument(
        "--lumi",
        dest="lumis",
        action="append",
        type=float,
        default=None,
        help="Integrated luminosity matched to each input/year. Repeat in the same order as --input."
    )
    parser.add_argument(
        "-s", "--com",
        type=float,
        default=13.6,
        help="Center-of-mass energy in TeV."
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output directory."
    )
    parser.add_argument(
        "-l", "--label",
        default="Preliminary",
        help="CMS extra label."
    )
    parser.add_argument(
        "--tree-name",
        default="trial_tree",
        help="Input tree name."
    )
    parser.add_argument(
        "--eff-threshold",
        type=float,
        default=70.0,
        help="Remove rolls with efficiency <= threshold."
    )
    parser.add_argument(
        "--eff-xmin",
        type=float,
        default=70.0,
        help="Efficiency histogram x minimum."
    )
    parser.add_argument(
        "--eff-xmax",
        type=float,
        default=100.0,
        help="Efficiency histogram x maximum."
    )
    parser.add_argument(
        "--eff-nbins",
        type=int,
        default=60,
        help="Number of bins for roll efficiency."
    )
    parser.add_argument(
        "--name-prefix",
        default="rpc-tnp",
        help="Output filename prefix."
    )
    parser.add_argument(
        "--ext",
        default="png",
        choices=["png", "pdf"],
        help="Output file extension."
    )

    args = parser.parse_args()

    if len(args.inputs) != len(args.years):
        raise RuntimeError(
            f"Number of --input ({len(args.inputs)}) and --year ({len(args.years)}) must match"
        )

    if args.lumis is not None and len(args.lumis) not in (0, len(args.inputs)):
        raise RuntimeError(
            f"Number of --lumi ({len(args.lumis)}) must be either 0 or match --input ({len(args.inputs)})"
        )

    return args


def build_year_label(year: int, lumi: float | None) -> str:
    if lumi is None:
        return f"{year}"
    return rf"{year} ({lumi:.1f} fb$^{{-1}}$)"


def build_year_label_unicode(year: int, lumi: float | None) -> str:
    if lumi is None:
        return f"{year}"
    return f"{year} ({lumi:.1f} fb⁻¹)"


def build_stats_label(year: int, lumi: float | None, mean_value: float) -> str:
    base = build_year_label(year, lumi)
    return rf"{base}, $\mu$={mean_value:.2f}"


def is_irpc(region: np.ndarray, ring: np.ndarray, station: np.ndarray) -> np.ndarray:
    return (region != 0) & (ring == 1) & np.isin(station, [3, 4])


def get_region_title(region_name: str) -> str:
    if region_name == "barrel":
        return "RPC Barrel"
    if region_name == "endcap":
        return "RPC Endcap"
    raise RuntimeError(f"Unknown region_name: {region_name}")


def compute_efficiency_summary_from_efficiencies(
    eff: np.ndarray,
    eff_threshold: float,
) -> tuple[float, float]:
    if len(eff) == 0:
        return np.nan, np.nan

    good_eff = eff[eff > eff_threshold]
    mean_good = float(np.mean(good_eff)) if len(good_eff) > 0 else np.nan
    frac_bad = float(100.0 * np.mean(eff <= eff_threshold))
    return mean_good, frac_bad


def build_efficiency_legend_row(
    year: int,
    lumi: float | None,
    mean_good: float,
    frac_bad: float,
) -> str:
    year_text = build_year_label_unicode(year, lumi)
    mean_text = f"{mean_good:.1f} %" if np.isfinite(mean_good) else "nan"
    frac_text = f"{frac_bad:.1f} %" if np.isfinite(frac_bad) else "nan"
    return f"{year_text:<18}{mean_text:>10}{frac_text:>10}"


def draw_stairs_hist(
    ax: plt.Axes,
    counts: np.ndarray,
    edges: np.ndarray,
    color: str,
    label: str,
) -> None:
    ax.stairs(
        counts,
        edges,
        label=label,
        color=color,
        linewidth=2,
    )


def add_common_style(
    ax: plt.Axes,
    cms_label: str,
    com_energy: float,
) -> None:
    mh.cms.label(
        ax=ax,
        data=True,
        llabel=cms_label,
        year="Run 3",
        com=com_energy,
        loc=0,
        fontsize=24,
    )


def style_log_y_axis(ax: plt.Axes, positive_counts: np.ndarray) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1))
    ax.yaxis.set_minor_formatter(NullFormatter())

    if len(positive_counts) > 0:
        ymin = max(np.min(positive_counts) * 0.8, 0.8)
        ymax = np.max(positive_counts) * 1.8
        ax.set_ylim(ymin, ymax)


def build_dataset_specs(
    input_paths: Sequence[Path],
    years: Sequence[int],
    lumis: Sequence[float] | None,
) -> list[DatasetSpec]:
    specs: list[DatasetSpec] = []

    for idx, input_path in enumerate(input_paths):
        lumi = None if lumis is None or len(lumis) == 0 else lumis[idx]
        specs.append(
            DatasetSpec(
                year=years[idx],
                lumi=lumi,
                input_path=input_path,
            )
        )

    return specs


def pack_roll_codes(
    region: np.ndarray,
    ring: np.ndarray,
    station: np.ndarray,
    sector: np.ndarray,
    layer: np.ndarray,
    subsector: np.ndarray,
    roll: np.ndarray,
) -> np.ndarray:
    region_u = region.astype(np.int64, copy=False) + 1
    ring_u = ring.astype(np.int64, copy=False) + 8
    station_u = station.astype(np.int64, copy=False)
    sector_u = sector.astype(np.int64, copy=False)
    layer_u = layer.astype(np.int64, copy=False)
    subsector_u = subsector.astype(np.int64, copy=False)
    roll_u = roll.astype(np.int64, copy=False)

    code = region_u
    code = (code << 5) | ring_u
    code = (code << 4) | station_u
    code = (code << 6) | sector_u
    code = (code << 3) | layer_u
    code = (code << 4) | subsector_u
    code = (code << 4) | roll_u
    return code


def unpack_roll_codes(codes: np.ndarray) -> tuple[np.ndarray, ...]:
    codes = codes.astype(np.int64, copy=False)

    roll = codes & 0xF
    codes = codes >> 4

    subsector = codes & 0xF
    codes = codes >> 4

    layer = codes & 0x7
    codes = codes >> 3

    sector = codes & 0x3F
    codes = codes >> 6

    station = codes & 0xF
    codes = codes >> 4

    ring = (codes & 0x1F) - 8
    codes = codes >> 5

    region = codes - 1

    return (
        region.astype(np.int16),
        ring.astype(np.int16),
        station.astype(np.int16),
        sector.astype(np.int16),
        layer.astype(np.int16),
        subsector.astype(np.int16),
        roll.astype(np.int16),
    )


def histogram_by_group(
    inverse: np.ndarray,
    values: np.ndarray,
    n_groups: int,
    value_min: int,
    value_max: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = (
        np.isfinite(values)
        & (values >= value_min)
        & (values <= value_max)
    )

    values_i = values[valid].astype(np.int64, copy=False) - value_min
    inverse_i = inverse[valid]
    n_bins = value_max - value_min + 1

    hist = np.bincount(
        inverse_i * n_bins + values_i,
        minlength=n_groups * n_bins,
    ).reshape(n_groups, n_bins).astype(np.float64)

    value_sum = np.bincount(
        inverse_i,
        weights=values[valid],
        minlength=n_groups,
    ).astype(np.float64)

    value_count = np.bincount(
        inverse_i,
        minlength=n_groups,
    ).astype(np.int64)

    return hist, value_sum, value_count


def make_empty_summary(spec: DatasetSpec) -> DatasetSummary:
    empty_eff = np.empty(0, dtype=np.float64)
    empty_cls = np.zeros(CLS_NBINS, dtype=np.float64)
    empty_bx = np.zeros(BX_NBINS, dtype=np.float64)

    return DatasetSummary(
        spec=spec,
        roll_eff_by_region={
            "barrel": empty_eff,
            "endcap": empty_eff,
        },
        eff_summary_by_region={
            "barrel": (np.nan, np.nan),
            "endcap": (np.nan, np.nan),
        },
        observable_summary_by_region={
            "barrel": {
                "cls": RegionObservableSummary(hist_counts=empty_cls, mean_value=np.nan),
                "bx": RegionObservableSummary(hist_counts=empty_bx, mean_value=np.nan),
            },
            "endcap": {
                "cls": RegionObservableSummary(hist_counts=empty_cls.copy(), mean_value=np.nan),
                "bx": RegionObservableSummary(hist_counts=empty_bx.copy(), mean_value=np.nan),
            },
        },
    )


def summarize_dataset(
    spec: DatasetSpec,
    tree_name: str,
    eff_threshold: float,
) -> DatasetSummary:
    print(f"[info] year={spec.year}: opening {spec.input_path}", flush=True)

    branches = list(ROLL_KEY_FIELDS) + ["is_fiducial", "is_matched", "cls", "bx"]

    with uproot.open(spec.input_path) as root_file:
        if tree_name not in root_file:
            raise RuntimeError(f"Missing tree '{tree_name}' in {spec.input_path}")

        tree = root_file[tree_name]
        print(
            f"[info] year={spec.year}: reading tree='{tree_name}' "
            f"with {tree.num_entries} entries",
            flush=True,
        )
        arrays = tree.arrays(branches, library="np")

    print(f"[info] year={spec.year}: finished reading arrays", flush=True)

    region = np.asarray(arrays["region"])
    ring = np.asarray(arrays["ring"])
    station = np.asarray(arrays["station"])
    sector = np.asarray(arrays["sector"])
    layer = np.asarray(arrays["layer"])
    subsector = np.asarray(arrays["subsector"])
    roll = np.asarray(arrays["roll"])
    is_fiducial = np.asarray(arrays["is_fiducial"]).astype(bool, copy=False)
    is_matched = np.asarray(arrays["is_matched"]).astype(bool, copy=False)
    cls_values = np.asarray(arrays["cls"], dtype=np.float64)
    bx_values = np.asarray(arrays["bx"], dtype=np.float64)

    print(
        f"[info] year={spec.year}: arrays loaded, n_trials={len(region)}",
        flush=True,
    )

    if len(region) == 0:
        print(f"[info] year={spec.year}: empty dataset", flush=True)
        return make_empty_summary(spec)

    print(f"[info] year={spec.year}: packing roll codes", flush=True)
    roll_codes = pack_roll_codes(
        region=region,
        ring=ring,
        station=station,
        sector=sector,
        layer=layer,
        subsector=subsector,
        roll=roll,
    )

    print(f"[info] year={spec.year}: grouping by roll", flush=True)
    unique_codes, inverse = np.unique(roll_codes, return_inverse=True)
    n_rolls = len(unique_codes)

    print(
        f"[info] year={spec.year}: found {n_rolls} unique rolls",
        flush=True,
    )

    valid_den = is_fiducial
    valid_num = is_fiducial & is_matched

    total_counts = np.bincount(
        inverse,
        weights=valid_den.astype(np.int64, copy=False),
        minlength=n_rolls,
    ).astype(np.int64)

    pass_counts = np.bincount(
        inverse,
        weights=valid_num.astype(np.int64, copy=False),
        minlength=n_rolls,
    ).astype(np.int64)

    efficiency = np.full(n_rolls, np.nan, dtype=np.float64)
    valid_roll_mask = total_counts > 0
    efficiency[valid_roll_mask] = 100.0 * pass_counts[valid_roll_mask] / total_counts[valid_roll_mask]

    print(f"[info] year={spec.year}: unpacking roll metadata", flush=True)
    u_region, u_ring, u_station, _, _, _, _ = unpack_roll_codes(unique_codes)
    irpc_mask = is_irpc(u_region, u_ring, u_station)
    bad_eff_mask = valid_roll_mask & (efficiency <= eff_threshold)

    barrel_keep = (u_region == 0) & valid_roll_mask & (~bad_eff_mask)
    endcap_keep = (u_region != 0) & valid_roll_mask & (~irpc_mask) & (~bad_eff_mask)

    n_bad = int(np.sum(bad_eff_mask))
    n_irpc = int(np.sum(irpc_mask))
    n_zero_den = int(np.sum(~valid_roll_mask))
    n_barrel_keep = int(np.sum(barrel_keep))
    n_endcap_keep = int(np.sum(endcap_keep))

    print(
        f"[info] year={spec.year}: zero-denominator rolls={n_zero_den}, "
        f"remove eff<={eff_threshold:.1f}% rolls={n_bad}, "
        f"iRPC rolls={n_irpc}, keep barrel={n_barrel_keep}, keep endcap={n_endcap_keep}",
        flush=True,
    )

    roll_eff_by_region = {
        "barrel": efficiency[barrel_keep],
        "endcap": efficiency[endcap_keep],
    }
    eff_summary_by_region = {
        "barrel": compute_efficiency_summary_from_efficiencies(
            roll_eff_by_region["barrel"], eff_threshold
        ),
        "endcap": compute_efficiency_summary_from_efficiencies(
            roll_eff_by_region["endcap"], eff_threshold
        ),
    }

    print(f"[info] year={spec.year}: building fiducial+matched observable histograms", flush=True)

    obs_mask = is_fiducial & is_matched
    obs_inverse = inverse[obs_mask]
    obs_cls = cls_values[obs_mask]
    obs_bx = bx_values[obs_mask]

    cls_hist_all, cls_sum_all, cls_count_all = histogram_by_group(
        inverse=obs_inverse,
        values=obs_cls,
        n_groups=n_rolls,
        value_min=CLS_MIN,
        value_max=CLS_MAX,
    )
    bx_hist_all, bx_sum_all, bx_count_all = histogram_by_group(
        inverse=obs_inverse,
        values=obs_bx,
        n_groups=n_rolls,
        value_min=BX_MIN,
        value_max=BX_MAX,
    )

    barrel_cls_hist = (
        np.sum(cls_hist_all[barrel_keep], axis=0)
        if np.any(barrel_keep)
        else np.zeros(CLS_NBINS, dtype=np.float64)
    )
    endcap_cls_hist = (
        np.sum(cls_hist_all[endcap_keep], axis=0)
        if np.any(endcap_keep)
        else np.zeros(CLS_NBINS, dtype=np.float64)
    )

    barrel_bx_hist = (
        np.sum(bx_hist_all[barrel_keep], axis=0)
        if np.any(barrel_keep)
        else np.zeros(BX_NBINS, dtype=np.float64)
    )
    endcap_bx_hist = (
        np.sum(bx_hist_all[endcap_keep], axis=0)
        if np.any(endcap_keep)
        else np.zeros(BX_NBINS, dtype=np.float64)
    )

    barrel_cls_sum = float(np.sum(cls_sum_all[barrel_keep])) if np.any(barrel_keep) else 0.0
    endcap_cls_sum = float(np.sum(cls_sum_all[endcap_keep])) if np.any(endcap_keep) else 0.0

    barrel_bx_sum = float(np.sum(bx_sum_all[barrel_keep])) if np.any(barrel_keep) else 0.0
    endcap_bx_sum = float(np.sum(bx_sum_all[endcap_keep])) if np.any(endcap_keep) else 0.0

    barrel_cls_count = int(np.sum(cls_count_all[barrel_keep])) if np.any(barrel_keep) else 0
    endcap_cls_count = int(np.sum(cls_count_all[endcap_keep])) if np.any(endcap_keep) else 0

    barrel_bx_count = int(np.sum(bx_count_all[barrel_keep])) if np.any(barrel_keep) else 0
    endcap_bx_count = int(np.sum(bx_count_all[endcap_keep])) if np.any(endcap_keep) else 0

    observable_summary_by_region = {
        "barrel": {
            "cls": RegionObservableSummary(
                hist_counts=barrel_cls_hist,
                mean_value=(barrel_cls_sum / barrel_cls_count) if barrel_cls_count > 0 else np.nan,
            ),
            "bx": RegionObservableSummary(
                hist_counts=barrel_bx_hist,
                mean_value=(barrel_bx_sum / barrel_bx_count) if barrel_bx_count > 0 else np.nan,
            ),
        },
        "endcap": {
            "cls": RegionObservableSummary(
                hist_counts=endcap_cls_hist,
                mean_value=(endcap_cls_sum / endcap_cls_count) if endcap_cls_count > 0 else np.nan,
            ),
            "bx": RegionObservableSummary(
                hist_counts=endcap_bx_hist,
                mean_value=(endcap_bx_sum / endcap_bx_count) if endcap_bx_count > 0 else np.nan,
            ),
        },
    }

    print(f"[info] year={spec.year}: summary completed", flush=True)

    return DatasetSummary(
        spec=spec,
        roll_eff_by_region=roll_eff_by_region,
        eff_summary_by_region=eff_summary_by_region,
        observable_summary_by_region=observable_summary_by_region,
    )


def plot_roll_efficiency_distribution(
    dataset_summaries: Sequence[DatasetSummary],
    output_dir: Path,
    cms_label: str,
    com_energy: float,
    x_min: float,
    x_max: float,
    n_bins: int,
    region_name: str,
    output_name: str,
    output_ext: str,
    eff_threshold: float,
) -> Path:
    print(f"[info] plotting {output_name}", flush=True)

    fig, ax = plt.subplots(figsize=(12, 8))
    add_common_style(ax=ax, cms_label=cms_label, com_energy=com_energy)

    ax.text(
        0.04, 0.94,
        get_region_title(region_name),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=22,
    )

    ax.set_xlabel("Efficiency [%]", fontsize=22)
    ax.set_ylabel("Number of Rolls", fontsize=22)
    ax.set_xlim(x_min, x_max)

    edges = np.linspace(x_min, x_max, n_bins + 1)
    max_count = 0.0

    legend_handles: list[Line2D] = []
    legend_labels: list[str] = []

    header_handle = Line2D([], [], linestyle="none", color="none")
    header_label = f"{'':<18}{f'Mean (>{eff_threshold:.0f}%)':>10}{f'% (≤{eff_threshold:.0f}%)':>10}"
    legend_handles.append(header_handle)
    legend_labels.append(header_label)

    for idx, summary in enumerate(dataset_summaries):
        spec = summary.spec
        eff = summary.roll_eff_by_region[region_name]
        counts, hist_edges = np.histogram(eff, bins=edges)
        counts = counts.astype(np.float64)
        hist_edges = hist_edges.astype(np.float64)

        if len(counts) > 0:
            max_count = max(max_count, float(np.max(counts)))

        color = DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]
        ax.stairs(counts, hist_edges, color=color, linewidth=2)

        mean_good, frac_bad = summary.eff_summary_by_region[region_name]
        legend_handles.append(Line2D([], [], color=color, linewidth=2))
        legend_labels.append(
            build_efficiency_legend_row(
                year=spec.year,
                lumi=spec.lumi,
                mean_good=mean_good,
                frac_bad=frac_bad,
            )
        )

    if max_count > 0.0:
        ax.set_ylim(0.0, 1.25 * max_count)

    ax.legend(
        legend_handles,
        legend_labels,
        loc="upper left",
        bbox_to_anchor=(0.02, 0.90),
        frameon=False,
        handlelength=1.8,
        handleheight=1.2,
        labelspacing=0.35,
        borderpad=0.2,
        prop={"family": "monospace", "size": 16},
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_name}.{output_ext}"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    print(f"[done] saved: {output_path}", flush=True)
    return output_path


def plot_trial_observable_distribution(
    dataset_summaries: Sequence[DatasetSummary],
    output_dir: Path,
    cms_label: str,
    com_energy: float,
    region_name: str,
    branch_name: str,
    edges: np.ndarray,
    x_label: str,
    y_label: str,
    output_name: str,
    output_ext: str,
    x_ticks: Sequence[float] | None = None,
    log_scale: bool = False,
) -> Path:
    print(f"[info] plotting {output_name}", flush=True)

    fig, ax = plt.subplots(figsize=(12, 8))
    add_common_style(ax=ax, cms_label=cms_label, com_energy=com_energy)

    ax.text(
        0.04, 0.94,
        get_region_title(region_name),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=22,
    )

    ax.set_xlabel(x_label, fontsize=22)
    ax.set_ylabel(y_label, fontsize=22)
    ax.set_xlim(float(edges[0]), float(edges[-1]))

    if x_ticks is not None:
        ax.set_xticks(list(x_ticks))

    all_hists: list[tuple[str, np.ndarray]] = []
    max_count = 0.0

    for summary in dataset_summaries:
        spec = summary.spec
        obs = summary.observable_summary_by_region[region_name][branch_name]
        counts = obs.hist_counts
        mean_value = obs.mean_value

        if len(counts) > 0:
            max_count = max(max_count, float(np.max(counts)))

        label = build_stats_label(spec.year, spec.lumi, mean_value)
        all_hists.append((label, counts))

    if log_scale:
        positive_counts: list[np.ndarray] = []

        for idx, (label, counts) in enumerate(all_hists):
            draw_stairs_hist(
                ax=ax,
                counts=counts,
                edges=edges,
                color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)],
                label=label,
            )
            positive = counts[counts > 0.0]
            if len(positive) > 0:
                positive_counts.append(positive)

        merged_positive_counts = (
            np.concatenate(positive_counts)
            if len(positive_counts) > 0
            else np.empty(0, dtype=np.float64)
        )
        style_log_y_axis(ax, merged_positive_counts)

    else:
        scale_exp = int(np.floor(np.log10(max_count))) if max_count > 0.0 else 0
        scale = 10.0 ** scale_exp

        for idx, (label, counts) in enumerate(all_hists):
            draw_stairs_hist(
                ax=ax,
                counts=counts / scale,
                edges=edges,
                color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)],
                label=label,
            )

        if max_count > 0.0:
            ax.set_ylim(0.0, 1.25 * max_count / scale)

        if scale_exp != 0:
            ax.annotate(
                rf"$x10^{{{scale_exp}}}$",
                (-0.06, 1.0),
                xycoords="axes fraction",
                fontsize=18,
                horizontalalignment="left",
            )

    ax.legend(
        fontsize=18,
        loc="upper right",
        frameon=False,
        handlelength=1.6,
        handleheight=1.2,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_name}.{output_ext}"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)

    print(f"[done] saved: {output_path}", flush=True)
    return output_path


def main() -> None:
    args = parse_args()

    input_paths = list(args.inputs)
    years = list(args.years)
    lumis = None if args.lumis is None else list(args.lumis)

    dataset_specs = build_dataset_specs(
        input_paths=input_paths,
        years=years,
        lumis=lumis,
    )

    cls_edges = np.arange(0.5, 10.5 + 1.0, 1.0)
    bx_edges = np.arange(-4.5, 4.5 + 1.0, 1.0)

    print("[info] start processing datasets", flush=True)

    dataset_summaries: list[DatasetSummary] = []
    for spec in dataset_specs:
        print(f"[info] start year={spec.year}", flush=True)
        summary = summarize_dataset(
            spec=spec,
            tree_name=args.tree_name,
            eff_threshold=args.eff_threshold,
        )
        dataset_summaries.append(summary)
        print(f"[info] finished year={spec.year}", flush=True)

    print("[info] start plotting", flush=True)

    plot_jobs = [
        ("barrel", "roll_efficiency"),
        ("barrel", "cluster_size"),
        ("barrel", "bx"),
        ("endcap", "roll_efficiency"),
        ("endcap", "cluster_size"),
        ("endcap", "bx"),
    ]

    for region_name, plot_kind in plot_jobs:
        if plot_kind == "roll_efficiency":
            plot_roll_efficiency_distribution(
                dataset_summaries=dataset_summaries,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                x_min=args.eff_xmin,
                x_max=args.eff_xmax,
                n_bins=args.eff_nbins,
                region_name=region_name,
                output_name=f"{args.name_prefix}-roll-efficiency-{region_name}",
                output_ext=args.ext,
                eff_threshold=args.eff_threshold,
            )

        elif plot_kind == "cluster_size":
            plot_trial_observable_distribution(
                dataset_summaries=dataset_summaries,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                region_name=region_name,
                branch_name="cls",
                edges=cls_edges,
                x_label="Cluster Size",
                y_label="# Fiducial Matched Trials",
                output_name=f"{args.name_prefix}-cluster-size-{region_name}",
                output_ext=args.ext,
                x_ticks=np.arange(1, 11, 1),
                log_scale=False,
            )

        elif plot_kind == "bx":
            plot_trial_observable_distribution(
                dataset_summaries=dataset_summaries,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                region_name=region_name,
                branch_name="bx",
                edges=bx_edges,
                x_label="Bunch Crossing",
                y_label="# Fiducial Matched Trials",
                output_name=f"{args.name_prefix}-bx-{region_name}",
                output_ext=args.ext,
                x_ticks=np.arange(-4, 5, 1),
                log_scale=True,
            )

        else:
            raise RuntimeError(f"Unknown plot kind: {plot_kind}")

    print("[done] all plots completed", flush=True)


if __name__ == "__main__":
    main()