#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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

ROLL_KEY_DTYPE = np.dtype([
    ("region", np.int16),
    ("ring", np.int16),
    ("station", np.int16),
    ("sector", np.int16),
    ("layer", np.int16),
    ("subsector", np.int16),
    ("roll", np.int16),
])


@dataclass(frozen=True)
class DatasetSpec:
    year: int
    lumi: float | None
    input_path: Path
    exclude_json: Path


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
        "--exclude-json",
        dest="exclude_jsons",
        action="append",
        required=True,
        type=Path,
        help="Excluded-roll JSON path matched to each input/year."
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

    if len(args.exclude_jsons) != len(args.inputs):
        raise RuntimeError(
            f"Number of --exclude-json ({len(args.exclude_jsons)}) must match --input ({len(args.inputs)})"
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


def make_roll_key_array_from_columns(
    region: np.ndarray,
    ring: np.ndarray,
    station: np.ndarray,
    sector: np.ndarray,
    layer: np.ndarray,
    subsector: np.ndarray,
    roll: np.ndarray,
) -> np.ndarray:
    out = np.empty(len(region), dtype=ROLL_KEY_DTYPE)
    out["region"] = region.astype(np.int16, copy=False)
    out["ring"] = ring.astype(np.int16, copy=False)
    out["station"] = station.astype(np.int16, copy=False)
    out["sector"] = sector.astype(np.int16, copy=False)
    out["layer"] = layer.astype(np.int16, copy=False)
    out["subsector"] = subsector.astype(np.int16, copy=False)
    out["roll"] = roll.astype(np.int16, copy=False)
    return out


def make_roll_key_array(arrays: dict[str, np.ndarray]) -> np.ndarray:
    return make_roll_key_array_from_columns(
        region=arrays["region"],
        ring=arrays["ring"],
        station=arrays["station"],
        sector=arrays["sector"],
        layer=arrays["layer"],
        subsector=arrays["subsector"],
        roll=arrays["roll"],
    )


def load_arrays(
    path: Path,
    tree_name: str,
    branches: Sequence[str],
) -> dict[str, np.ndarray]:
    with uproot.open(path) as root_file:
        if tree_name not in root_file:
            raise RuntimeError(f"Missing tree '{tree_name}' in {path}")

        tree = root_file[tree_name]
        keys = set(tree.keys())

        missing = [branch for branch in branches if branch not in keys]
        if missing:
            raise RuntimeError(
                f"Missing branches in {path}:{tree_name}: {', '.join(missing)}"
            )

        arrays = tree.arrays(list(branches), library="np")

    out: dict[str, np.ndarray] = {}
    for branch in branches:
        value = np.asarray(arrays[branch])
        if branch == "is_matched":
            out[branch] = value.astype(bool, copy=False)
        else:
            out[branch] = value
    return out


def load_excluded_roll_keys(json_path: Path) -> np.ndarray:
    with open(json_path, "r", encoding="utf-8") as fin:
        payload = json.load(fin)

    if "excluded_roll_details_excluding_irpc" in payload:
        rows = payload["excluded_roll_details_excluding_irpc"]
    elif "excluded_roll_details_including_irpc" in payload:
        rows = [
            row for row in payload["excluded_roll_details_including_irpc"]
            if not bool(row.get("is_irpc", False))
        ]
    elif "excluded_roll_details" in payload:
        rows = [
            row for row in payload["excluded_roll_details"]
            if not (
                int(row["region"]) != 0
                and int(row["ring"]) == 1
                and int(row["station"]) in (3, 4)
            )
        ]
    else:
        raise RuntimeError(
            f"Missing excluded-roll details in {json_path}. "
            "Expected excluded_roll_details_excluding_irpc or equivalent."
        )

    if len(rows) == 0:
        return np.empty(0, dtype=ROLL_KEY_DTYPE)

    keys = make_roll_key_array_from_columns(
        region=np.asarray([row["region"] for row in rows], dtype=np.int16),
        ring=np.asarray([row["ring"] for row in rows], dtype=np.int16),
        station=np.asarray([row["station"] for row in rows], dtype=np.int16),
        sector=np.asarray([row["sector"] for row in rows], dtype=np.int16),
        layer=np.asarray([row["layer"] for row in rows], dtype=np.int16),
        subsector=np.asarray([row["subsector"] for row in rows], dtype=np.int16),
        roll=np.asarray([row["roll"] for row in rows], dtype=np.int16),
    )
    return np.unique(keys)


def get_region_title(region_name: str) -> str:
    if region_name == "barrel":
        return "RPC Barrel"
    if region_name == "endcap":
        return "RPC Endcap"
    raise RuntimeError(f"Unknown region_name: {region_name}")


def get_region_mask_from_arrays(
    arrays: dict[str, np.ndarray],
    region_name: str,
) -> np.ndarray:
    region = arrays["region"]
    ring = arrays["ring"]
    station = arrays["station"]

    if region_name == "barrel":
        return region == 0

    if region_name == "endcap":
        return (region != 0) & (~is_irpc(region, ring, station))

    raise RuntimeError(f"Unknown region_name: {region_name}")


def get_region_mask_from_roll_table(
    roll_table: dict[str, np.ndarray],
    region_name: str,
) -> np.ndarray:
    if region_name == "barrel":
        return roll_table["region"] == 0

    if region_name == "endcap":
        return (roll_table["region"] != 0) & (~roll_table["is_irpc"])

    raise RuntimeError(f"Unknown region_name: {region_name}")


def build_roll_efficiency_table(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    roll_keys = make_roll_key_array(arrays)
    unique_keys, inverse = np.unique(roll_keys, return_inverse=True)

    total_counts = np.bincount(inverse)
    pass_counts = np.bincount(
        inverse,
        weights=arrays["is_matched"].astype(np.int64),
    ).astype(np.int64)
    efficiency = 100.0 * pass_counts / total_counts

    region = unique_keys["region"].astype(np.int16, copy=False)
    ring = unique_keys["ring"].astype(np.int16, copy=False)
    station = unique_keys["station"].astype(np.int16, copy=False)
    irpc_mask = is_irpc(region, ring, station)

    return {
        "roll_keys": unique_keys,
        "region": region,
        "ring": ring,
        "station": station,
        "total": total_counts.astype(np.int64),
        "passed": pass_counts.astype(np.int64),
        "efficiency": efficiency.astype(np.float64),
        "is_irpc": irpc_mask.astype(bool),
    }


def select_roll_efficiencies_from_table(
    roll_table: dict[str, np.ndarray],
    excluded_roll_keys: np.ndarray,
    region_name: str,
) -> np.ndarray:
    mask = get_region_mask_from_roll_table(roll_table, region_name)

    roll_keys = roll_table["roll_keys"][mask]
    eff = roll_table["efficiency"][mask]

    if len(excluded_roll_keys) > 0:
        keep = ~np.isin(roll_keys, excluded_roll_keys)
        eff = eff[keep]

    return eff[np.isfinite(eff)]


def select_observable_values(
    arrays: dict[str, np.ndarray],
    excluded_roll_keys: np.ndarray,
    region_name: str,
    branch_name: str,
    min_value: float,
    max_value: float,
) -> np.ndarray:
    mask = get_region_mask_from_arrays(arrays, region_name)
    mask &= arrays["is_matched"]

    if len(excluded_roll_keys) > 0:
        roll_keys = make_roll_key_array(arrays)
        mask &= ~np.isin(roll_keys, excluded_roll_keys)

    values = np.asarray(arrays[branch_name][mask], dtype=np.float64)
    values = values[np.isfinite(values)]
    values = values[(values >= min_value) & (values <= max_value)]
    return values


def compute_mean(values: np.ndarray) -> float:
    if len(values) == 0:
        return np.nan
    return float(np.mean(values))


def compute_histogram(values: np.ndarray, edges: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    counts, hist_edges = np.histogram(values, bins=edges)
    return counts.astype(np.float64), hist_edges.astype(np.float64)


def compute_efficiency_summary_from_table(
    roll_table: dict[str, np.ndarray],
    excluded_roll_keys: np.ndarray,
    region_name: str,
) -> tuple[float, float]:
    eff = select_roll_efficiencies_from_table(
        roll_table=roll_table,
        excluded_roll_keys=excluded_roll_keys,
        region_name=region_name,
    )

    if len(eff) == 0:
        return np.nan, np.nan

    good_eff = eff[eff > 70.0]
    mean_good = float(np.mean(good_eff)) if len(good_eff) > 0 else np.nan
    frac_bad = float(100.0 * np.mean(eff <= 70.0))

    return mean_good, frac_bad


def build_efficiency_legend_row(
    year: int,
    lumi: float | None,
    roll_table: dict[str, np.ndarray],
    excluded_roll_keys: np.ndarray,
    region_name: str,
) -> str:
    year_text = build_year_label_unicode(year, lumi)
    mean_good, frac_bad = compute_efficiency_summary_from_table(
        roll_table=roll_table,
        excluded_roll_keys=excluded_roll_keys,
        region_name=region_name,
    )

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


def plot_roll_efficiency_distribution(
    dataset_specs: Sequence[DatasetSpec],
    tree_name: str,
    output_dir: Path,
    cms_label: str,
    com_energy: float,
    x_min: float,
    x_max: float,
    n_bins: int,
    region_name: str,
    output_name: str,
    output_ext: str,
) -> Path:
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
    header_label = f"{'':<18}{'Mean (>70%)':>10}{'% (≤70%)':>10}"
    legend_handles.append(header_handle)
    legend_labels.append(header_label)

    branches = list(ROLL_KEY_FIELDS) + ["is_matched"]

    for idx, spec in enumerate(dataset_specs):
        arrays = load_arrays(
            path=spec.input_path,
            tree_name=tree_name,
            branches=branches,
        )
        excluded_roll_keys = load_excluded_roll_keys(spec.exclude_json)
        roll_table = build_roll_efficiency_table(arrays)
        eff = select_roll_efficiencies_from_table(
            roll_table=roll_table,
            excluded_roll_keys=excluded_roll_keys,
            region_name=region_name,
        )
        counts, hist_edges = compute_histogram(eff, edges)

        if len(counts) > 0:
            max_count = max(max_count, float(np.max(counts)))

        color = DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]

        ax.stairs(
            counts,
            hist_edges,
            color=color,
            linewidth=2,
        )

        legend_handles.append(Line2D([], [], color=color, linewidth=2))
        legend_labels.append(
            build_efficiency_legend_row(
                year=spec.year,
                lumi=spec.lumi,
                roll_table=roll_table,
                excluded_roll_keys=excluded_roll_keys,
                region_name=region_name,
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
    return output_path


def plot_trial_observable_distribution(
    dataset_specs: Sequence[DatasetSpec],
    tree_name: str,
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

    all_hists = []
    max_count = 0.0

    branches = list(ROLL_KEY_FIELDS) + ["is_matched", branch_name]

    for spec in dataset_specs:
        arrays = load_arrays(
            path=spec.input_path,
            tree_name=tree_name,
            branches=branches,
        )
        excluded_roll_keys = load_excluded_roll_keys(spec.exclude_json)

        values = select_observable_values(
            arrays=arrays,
            excluded_roll_keys=excluded_roll_keys,
            region_name=region_name,
            branch_name=branch_name,
            min_value=float(edges[0]),
            max_value=float(edges[-1]),
        )

        mean_value = compute_mean(values)
        counts, hist_edges = compute_histogram(values, edges)

        if len(counts) > 0:
            max_count = max(max_count, float(np.max(counts)))

        label = build_stats_label(spec.year, spec.lumi, mean_value)
        all_hists.append((label, counts, hist_edges))

    if log_scale:
        positive_counts = []

        for idx, (label, counts, hist_edges) in enumerate(all_hists):
            draw_stairs_hist(
                ax=ax,
                counts=counts,
                edges=hist_edges,
                color=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)],
                label=label,
            )
            positive_counts.extend(counts[counts > 0.0])

        style_log_y_axis(ax, np.asarray(positive_counts, dtype=np.float64))

    else:
        if max_count > 0.0:
            scale_exp = int(np.floor(np.log10(max_count)))
        else:
            scale_exp = 0
        scale = 10.0 ** scale_exp

        for idx, (label, counts, hist_edges) in enumerate(all_hists):
            draw_stairs_hist(
                ax=ax,
                counts=counts / scale,
                edges=hist_edges,
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
    return output_path


def build_dataset_specs(
    input_paths: Sequence[Path],
    years: Sequence[int],
    lumis: Sequence[float] | None,
    exclude_jsons: Sequence[Path],
) -> list[DatasetSpec]:
    specs = []

    for idx, input_path in enumerate(input_paths):
        lumi = None if lumis is None or len(lumis) == 0 else lumis[idx]
        specs.append(
            DatasetSpec(
                year=years[idx],
                lumi=lumi,
                input_path=input_path,
                exclude_json=exclude_jsons[idx],
            )
        )

    return specs


def main() -> None:
    args = parse_args()

    input_paths = list(args.inputs)
    years = list(args.years)
    lumis = None if args.lumis is None else list(args.lumis)
    exclude_jsons = list(args.exclude_jsons)

    dataset_specs = build_dataset_specs(
        input_paths=input_paths,
        years=years,
        lumis=lumis,
        exclude_jsons=exclude_jsons,
    )

    cls_edges = np.arange(0.5, 10.5 + 1.0, 1.0)
    bx_edges = np.arange(-4.5, 4.5 + 1.0, 1.0)

    output_paths = []

    for region_name in ("barrel", "endcap"):
        output_paths.append(
            plot_roll_efficiency_distribution(
                dataset_specs=dataset_specs,
                tree_name=args.tree_name,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                x_min=args.eff_xmin,
                x_max=args.eff_xmax,
                n_bins=args.eff_nbins,
                region_name=region_name,
                output_name=f"{args.name_prefix}-roll-efficiency-{region_name}",
                output_ext=args.ext,
            )
        )

        output_paths.append(
            plot_trial_observable_distribution(
                dataset_specs=dataset_specs,
                tree_name=args.tree_name,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                region_name=region_name,
                branch_name="cls",
                edges=cls_edges,
                x_label="Cluster Size",
                y_label="# Matched Trials",
                output_name=f"{args.name_prefix}-cluster-size-{region_name}",
                output_ext=args.ext,
                x_ticks=np.arange(1, 11, 1),
                log_scale=False,
            )
        )

        output_paths.append(
            plot_trial_observable_distribution(
                dataset_specs=dataset_specs,
                tree_name=args.tree_name,
                output_dir=args.output,
                cms_label=args.label,
                com_energy=args.com,
                region_name=region_name,
                branch_name="bx",
                edges=bx_edges,
                x_label="Bunch Crossing",
                y_label="# Matched Trials",
                output_name=f"{args.name_prefix}-bx-{region_name}",
                output_ext=args.ext,
                x_ticks=np.arange(-4, 5, 1),
                log_scale=True,
            )
        )

    for output_path in output_paths:
        print(f"[done] saved: {output_path}", flush=True)


if __name__ == "__main__":
    main()