from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import mplhep as mh
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import Colormap
from matplotlib.container import ErrorbarContainer
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Rectangle, StepPatch
from matplotlib.ticker import LogLocator, MaxNLocator, MultipleLocator, NullFormatter
from matplotlib.transforms import blended_transform_factory
from mpl_toolkits.axes_grid1 import make_axes_locatable

CMS_P6 = [
    "#E42536",
    "#F89C20",
    "#9C9CA1",
    "#964A8B",
    "#5790FC",
    "#7A21DD",
]
YEAR_COLORS = {
    str(year): CMS_P6[index]
    for index, year in enumerate(range(2022, 2027))
}
DEFAULT_COLORS = tuple(CMS_P6)
LINE_ALPHA = 1.0
BARREL_PHI_PADDING = 0.45
RUN3_ELAPSED_START = np.datetime64("2022-07-05T00:00:00")
RUN3_ELAPSED_START_LABEL = "July 05, 2022"
SECONDS_PER_WEEK = 7 * 24 * 60 * 60


mh.style.use("CMS")


@dataclass(frozen=True)
class DatasetSpec:
    input_paths: tuple[Path, ...]
    year: int | str
    lumi: float


def build_dataset_specs(input_groups: Sequence[Sequence[Path]], years: Sequence[int], lumis: Sequence[float]) -> list[DatasetSpec]:
    return [
        DatasetSpec(tuple(Path(path) for path in input_paths), years[idx], lumis[idx])
        for idx, input_paths in enumerate(input_groups)
    ]


def combine_dataset_specs(specs: Sequence[DatasetSpec]) -> DatasetSpec:
    years = tuple(dict.fromkeys(spec.year for spec in specs))
    scope = years[0] if len(years) == 1 else "3"
    return DatasetSpec(
        tuple(path for spec in specs for path in spec.input_paths),
        scope,
        sum(spec.lumi for spec in specs),
    )


def cms_year_label(year: int | str) -> int | str:
    return "Run 3" if str(year) == "3" else year


def add_cms_label(
    ax: plt.Axes,
    label: str,
    com: float,
    lumi: float | None = None,
    year: int | str | None = None,
    lumi_first: bool = False,
) -> None:
    if lumi is None:
        mh.cms.label(ax=ax, llabel=label, year=year, com=com)
        return
    if lumi_first:
        year_text = "" if year is None else f", {year}"
        right_label = rf"{float(lumi):.1f} fb$^{{-1}}${year_text} ({float(com):g} TeV)"
    else:
        year_text = "" if year is None else f"{year}, "
        right_label = rf"{year_text}{float(lumi):.1f} fb$^{{-1}}$ ({float(com):g} TeV)"
    mh.cms.label(ax=ax, llabel=label, rlabel=right_label)


def build_year_label(year: int | str, lumi: float) -> str:
    lumi_label = f"{float(lumi):.1f} fb$^{{-1}}$"
    return lumi_label if str(year) == "3" else f"{year} ({lumi_label})"


def year_color(year: int | str, fallback_index: int = 0) -> str:
    return YEAR_COLORS.get(str(year), DEFAULT_COLORS[fallback_index % len(DEFAULT_COLORS)])


def add_tag_and_probe_label(ax: plt.Axes) -> None:
    ax.text(0.96, 0.94, "Tag-and-Probe method", transform=ax.transAxes, ha="right", va="top", fontsize=22)


def add_panel_label(ax: plt.Axes, label: str | None) -> None:
    if label and label != "All RPC":
        ax.text(0.04, 0.94, label, transform=ax.transAxes, ha="left", va="top", fontsize=22)


def draw_color_swatch(ax: plt.Axes, x0: float, x1: float, y: float, color: str) -> None:
    center = 0.5 * (x0 + x1)
    width = 1.0 * (x1 - x0)
    height = 0.035
    ax.add_patch(Rectangle(
        (center - 0.5 * width, y - 0.5 * height),
        width,
        height,
        facecolor=color,
        edgecolor="none",
        transform=ax.transAxes,
        clip_on=False,
    ))


def draw_year_summary(
    ax: plt.Axes,
    rows: list[tuple[str, str]],
) -> None:
    x_line0, x_line1 = 0.70, 0.74
    x_year = 0.76
    y_first, dy = 0.850, 0.055
    fontsize = 16

    for row_index, (color, year_label) in enumerate(rows):
        y = y_first - row_index * dy
        draw_color_swatch(ax, x_line0, x_line1, y, color)
        ax.text(x_year, y, year_label, transform=ax.transAxes, ha="left", va="center", fontsize=fontsize)


def draw_year_mean_summary(
    ax: plt.Axes,
    rows: list[tuple[str, str, float]],
    precision: int = 2,
) -> None:
    x_line0, x_line1 = 0.62, 0.66
    x_year, x_mean = 0.68, 0.94
    y_header, y_first, dy = 0.850, 0.800, 0.055
    fontsize = 16

    ax.text(x_year, y_header, "Year", transform=ax.transAxes, ha="left", va="center", fontsize=fontsize)
    ax.text(x_mean, y_header, "Mean", transform=ax.transAxes, ha="right", va="center", fontsize=fontsize)

    for row_index, (color, year_label, mean) in enumerate(rows):
        y = y_first - row_index * dy
        mean_label = f"{float(mean):.{precision}f}" if np.isfinite(mean) else "n/a"
        draw_color_swatch(ax, x_line0, x_line1, y, color)
        ax.text(x_year, y, year_label, transform=ax.transAxes, ha="left", va="center", fontsize=fontsize)
        ax.text(x_mean, y, mean_label, transform=ax.transAxes, ha="right", va="center", fontsize=fontsize)


def draw_year_rms_summary(
    ax: plt.Axes,
    rows: list[tuple[str, str, float]],
    precision: int = 2,
) -> None:
    x_line0, x_line1 = 0.62, 0.66
    x_year, x_rms = 0.68, 0.94
    y_header, y_first, dy = 0.850, 0.800, 0.055
    fontsize = 16

    ax.text(x_year, y_header, "Year", transform=ax.transAxes, ha="left", va="center", fontsize=fontsize)
    ax.text(x_rms, y_header, "RMS", transform=ax.transAxes, ha="right", va="center", fontsize=fontsize)

    for row_index, (color, year_label, rms) in enumerate(rows):
        y = y_first - row_index * dy
        rms_label = f"{float(rms):.{precision}f}" if np.isfinite(rms) else "n/a"
        draw_color_swatch(ax, x_line0, x_line1, y, color)
        ax.text(x_year, y, year_label, transform=ax.transAxes, ha="left", va="center", fontsize=fontsize)
        ax.text(x_rms, y, rms_label, transform=ax.transAxes, ha="right", va="center", fontsize=fontsize)


def new_figure(
    cms_label: str,
    com_energy: float,
    figsize: tuple[float, float] = (12, 8),
    year: int | str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=figsize)
    add_cms_label(ax=ax, label=cms_label, com=com_energy, year=year)
    return fig, ax


def plot_output_dir(output: Path, category: str, year: int | str = "3") -> Path:
    return output / f"Run{year}" / category


def comparison_output_dir(output: Path, category: str, specs: Sequence[DatasetSpec]) -> Path:
    years = tuple(dict.fromkeys(spec.year for spec in specs))
    return plot_output_dir(output, category, years[0] if len(years) == 1 else "3")


def variant_output_target(output: Path, family: str, variant: str | None = None) -> tuple[Path, str]:
    if variant is None:
        return output, family
    return output / family, variant


def variant_output_label(family: str, variant: str | None = None) -> str:
    return family if variant is None else f"{family}-{variant}"


def plot_group_label(group: str) -> str:
    labels = {
        "all": "All RPC",
        "barrel": "RPC Barrel",
        "endcap": "RPC Endcap",
        "endcap-minus": "RPC Endcap-",
        "endcap-plus": "RPC Endcap+",
    }
    return labels.get(group, group)


def save_figure(
    fig: plt.Figure,
    output_dir: Path,
    output_name: str,
    output_ext: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_name}.{output_ext.lstrip('.')}"
    fig.savefig(output_path)
    plt.close(fig)
    print(f"[done] saved: {output_path}", flush=True)
    return output_path


def save_binned_value_map(
    values: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    xlabel: str,
    ylabel: str,
    value_label: str,
    output: Path,
    output_name: str,
    label: str,
    com: float,
    lumi: float,
    year: int | str,
    ext: str,
    cmap: Colormap | str,
    vmin: float,
    vmax: float,
    mask_zero: bool = False,
) -> Path:
    print(f"[info] plotting {output_name}-Run{year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    plot_values = np.asarray(values, dtype=np.float64)
    masked_values = np.ma.masked_invalid(plot_values.T)
    if mask_zero:
        masked_values = np.ma.masked_where(plot_values.T <= 0.0, masked_values)
    mesh = ax.pcolormesh(
        x_edges,
        y_edges,
        masked_values,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading="flat",
        edgecolors=(0.0, 0.0, 0.0, 0.22),
        linewidth=0.20,
    )
    ax.set_xlabel(xlabel, fontsize=22)
    ax.set_ylabel(ylabel, fontsize=22)
    cbar = fig.colorbar(mesh, ax=ax, pad=0.02)
    cbar.set_label(value_label, fontsize=20)
    add_cms_label(ax, label, com, lumi=lumi, year=cms_year_label(year), lumi_first=True)
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def bin_centers(edges: np.ndarray) -> np.ndarray:
    return 0.5 * (edges[:-1] + edges[1:])


def bin_half_widths(edges: np.ndarray) -> np.ndarray:
    return 0.5 * np.diff(edges)


def histogram_y_label(label: str, edges: np.ndarray, unit: str | None = None) -> str:
    widths = np.diff(np.asarray(edges, dtype=np.float64))
    if len(widths) == 0 or not np.allclose(widths, widths[0]):
        return f"{label} / bin"
    width = float(widths[0])
    if unit is None and np.isclose(width, 1.0):
        return f"{label} / bin"
    denominator = f"{width:.3g}"
    if unit:
        separator = "" if unit == "%" else " "
        denominator = f"{denominator}{separator}{unit}"
    return f"{label} / {denominator}"


def count_scale(max_count: float) -> tuple[int, float]:
    scale_exp = int(np.floor(np.log10(max_count))) if max_count > 0.0 else 0
    return scale_exp, 10.0 ** scale_exp


def annotate_count_scale(
    ax: plt.Axes,
    scale_exp: int,
    y: float = 1.0,
) -> None:
    if scale_exp != 0:
        ax.annotate(
            rf"$x10^{{{scale_exp}}}$",
            (-0.06, y),
            xycoords="axes fraction",
            fontsize=18,
            horizontalalignment="left",
        )


def add_legend(
    ax: plt.Axes,
    loc: str = "upper right",
    frameon: bool = False,
    fontsize: int = 18,
    bbox_to_anchor: tuple[float, float] | None = None,
) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        patch_handles = [
            Patch(facecolor=_legend_color(handle), edgecolor="none", label=label)
            for handle, label in zip(handles, labels)
        ]
        kwargs = {"bbox_to_anchor": bbox_to_anchor} if bbox_to_anchor is not None else {}
        ax.legend(
            patch_handles,
            labels,
            fontsize=fontsize,
            loc=loc,
            frameon=frameon,
            handlelength=1.3,
            handleheight=1.1,
            **kwargs,
        )


def _legend_color(handle) -> str:
    artist = handle.lines[0] if isinstance(handle, ErrorbarContainer) else handle
    if hasattr(artist, "get_color"):
        return artist.get_color()
    if hasattr(artist, "get_edgecolor"):
        return artist.get_edgecolor()
    if hasattr(artist, "get_facecolor"):
        return artist.get_facecolor()
    return "black"


def plot_spec_color(plot: dict, index: int) -> str:
    colors = plot.get("colors")
    if colors:
        return colors[index % len(colors)]
    return DEFAULT_COLORS[index % len(DEFAULT_COLORS)]


def plot_spec_label(plot: dict, label: str) -> str:
    return label if plot.get("show_legend", True) else "_nolegend_"


def add_plot_spec_legend(ax: plt.Axes, plot: dict, **kwargs) -> None:
    if plot.get("show_legend", True):
        add_legend(ax, **kwargs)


def draw_errorbar_series(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    color: str,
    label: str,
    xerr: np.ndarray | None = None,
    yerr: np.ndarray | None = None,
    marker_size: float = 0.0,
) -> ErrorbarContainer:
    return ax.errorbar(
        x,
        y,
        xerr=xerr,
        yerr=yerr,
        fmt="o",
        linestyle="none",
        color=color,
        markersize=marker_size,
        capsize=4.5,
        elinewidth=1.5,
        alpha=LINE_ALPHA,
        label=label,
    )


def draw_point_series(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    color: str,
    label: str,
    marker_size: float = 5.0,
) -> Line2D:
    return ax.plot(
        x,
        y,
        marker="o",
        linestyle="none",
        color=color,
        markersize=marker_size,
        alpha=LINE_ALPHA,
        label=label,
    )[0]


def elapsed_weeks_since_run3_start(timestamps: np.ndarray) -> np.ndarray:
    values = np.asarray(timestamps, dtype="datetime64[s]")
    elapsed_seconds = (values - RUN3_ELAPSED_START).astype("timedelta64[s]").astype(np.float64)
    return elapsed_seconds / float(SECONDS_PER_WEEK)


def _week_from_timestamp(timestamp: np.datetime64) -> float:
    return float((timestamp - RUN3_ELAPSED_START).astype("timedelta64[s]").astype(np.float64) / float(SECONDS_PER_WEEK))


def configure_elapsed_week_axis(
    ax: plt.Axes,
    x_values: np.ndarray,
    y_label: str,
    y_limits: tuple[float, float] | None = None,
) -> None:
    finite_x = np.asarray(x_values, dtype=np.float64)
    finite_x = finite_x[np.isfinite(finite_x)]
    xmax_data = float(np.max(finite_x)) if len(finite_x) else 220.0
    xmax = max(20.0, float(np.ceil((xmax_data + 5.0) / 20.0) * 20.0))
    ax.set_xlim(0.0, xmax)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    ax.set_xlabel(f"Elapsed time in weeks since {RUN3_ELAPSED_START_LABEL}", fontsize=22)
    ax.set_ylabel(y_label, fontsize=22)
    ax.xaxis.set_major_locator(MultipleLocator(20.0))
    ax.xaxis.set_minor_locator(MultipleLocator(5.0))
    ax.grid(True, which="major", axis="x", linestyle="--", color="black", linewidth=1.0)
    _draw_run3_year_labels(ax, xmax)


def configure_run_axis(
    ax: plt.Axes,
    runs: np.ndarray,
    y_label: str,
    y_limits: tuple[float, float] | None = None,
) -> None:
    run_values = np.asarray(runs, dtype=np.float64)
    run_values = run_values[np.isfinite(run_values)]
    if len(run_values):
        run_min = float(np.min(run_values))
        run_max = float(np.max(run_values))
        pad = max(1.0, 0.02 * max(run_max - run_min, 1.0))
        ax.set_xlim(run_min - pad, run_max + pad)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    ax.set_xlabel("Run", fontsize=22)
    ax.set_ylabel(y_label, fontsize=22)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
    ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    ax.tick_params(axis="x", labelrotation=30)
    ax.grid(True, which="major", axis="both", linestyle=(0, (1.2, 2.8)), color="black", linewidth=0.8)


def configure_run_index_axis(
    ax: plt.Axes,
    run_count: int,
    y_label: str,
    y_limits: tuple[float, float] | None = None,
) -> None:
    if run_count > 0:
        ax.set_xlim(-0.5, run_count - 0.5)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    ax.set_xlabel("Run Index", fontsize=22)
    ax.set_ylabel(y_label, fontsize=22)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
    ax.grid(True, which="major", axis="both", linestyle=(0, (1.2, 2.8)), color="black", linewidth=0.8)


def _draw_run3_year_labels(ax: plt.Axes, xmax: float) -> None:
    transform = blended_transform_factory(ax.transData, ax.transAxes)
    start_points = [
        RUN3_ELAPSED_START,
        np.datetime64("2023-01-01T00:00:00"),
        np.datetime64("2024-01-01T00:00:00"),
        np.datetime64("2025-01-01T00:00:00"),
        np.datetime64("2026-01-01T00:00:00"),
    ]
    labels = ("2022", "2023", "2024", "2025", "2026")
    end_points = [
        np.datetime64("2023-01-01T00:00:00"),
        np.datetime64("2024-01-01T00:00:00"),
        np.datetime64("2025-01-01T00:00:00"),
        np.datetime64("2026-01-01T00:00:00"),
        np.datetime64("2027-01-01T00:00:00"),
    ]
    for label, start, end in zip(labels, start_points, end_points):
        x0 = max(0.0, _week_from_timestamp(start))
        x1 = min(xmax, _week_from_timestamp(end))
        if x1 <= 0.0 or x0 >= xmax or x1 <= x0:
            continue
        ax.text(
            0.5 * (x0 + x1),
            0.86,
            label,
            transform=transform,
            ha="center",
            va="top",
            fontsize=22,
            fontweight="bold",
            color="black",
        )


def draw_binned_stairs(
    ax: plt.Axes,
    values: np.ndarray,
    edges: np.ndarray,
    color: str,
    label: str,
    scale: float = 1.0,
    log_scale: bool = False,
) -> StepPatch:
    step_values = values.astype(np.float64, copy=True) / scale
    if log_scale:
        step_values[step_values <= 0.0] = np.nan
    return ax.stairs(
        step_values,
        edges,
        color=color,
        alpha=LINE_ALPHA,
        label=label,
        linewidth=3.0,
    )


def draw_roll_map(
    ax: plt.Axes,
    patches: list[Polygon],
    values: np.ndarray,
    excluded_mask: np.ndarray,
    inactive_mask: np.ndarray,
    cmap: Colormap | str,
    vmin: float,
    vmax: float,
    edgecolor: str = "black",
    lw: float = 2,
) -> plt.Axes:
    excluded_mask = np.asarray(excluded_mask, dtype=bool)
    inactive_mask = np.asarray(inactive_mask, dtype=bool) & ~excluded_mask
    active_mask = ~excluded_mask & ~inactive_mask

    cmap = plt.get_cmap(cmap)
    denom = vmax - vmin
    normalized_values = np.zeros_like(values, dtype=np.float64) if denom == 0 else (values - vmin) / denom
    normalized_values = np.nan_to_num(np.clip(normalized_values, 0.0, 1.0), nan=0.0, posinf=1.0, neginf=0.0)

    for mask, facecolor, each_edgecolor in (
        (active_mask, cmap(normalized_values[active_mask]), edgecolor),
        (inactive_mask, np.array([0.85, 0.85, 0.85, 1.0], dtype=np.float64), edgecolor),
    ):
        if not np.any(mask):
            continue
        collection = PatchCollection([patches[i] for i in np.where(mask)[0]])
        collection.set_facecolor(facecolor)
        collection.set_edgecolor(each_edgecolor)
        collection.set_linewidth(lw)
        ax.add_collection(collection)

    if np.any(excluded_mask):
        collection = PatchCollection([patches[i] for i in np.where(excluded_mask)[0]])
        collection.set_facecolor(np.array([0.40, 0.40, 0.40, 1.0], dtype=np.float64))
        collection.set_edgecolor("black")
        collection.set_linewidth(lw)
        collection.set_hatch("//")
        ax.add_collection(collection)

    ax.autoscale_view()
    scalar_mappable = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    scalar_mappable.set_array([])
    cax = make_axes_locatable(ax).append_axes("right", size="5%", pad=0.2)
    cax.figure.colorbar(scalar_mappable, cax=cax, pad=0.1)
    return cax


def save_roll_value_map(result, output: Path, year: int | str, label: str, com: float, lumi: float, ext: str) -> Path:
    print(f"[info] plotting {result.detector_unit}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 9))
    is_barrel = result.rolls[0].id.barrel
    cax = draw_roll_map(
        ax,
        result.patches,
        result.values,
        excluded_mask=result.excluded_mask,
        inactive_mask=result.inactive_mask,
        cmap=result.cmap,
        vmin=result.vmin,
        vmax=result.vmax,
    )
    ax.set_xlabel(result.rolls[0].polygon_xlabel)
    ax.set_ylabel(result.rolls[0].polygon_ylabel)
    cax.set_ylabel(result.value_label)
    if is_barrel:
        ax.set_ylim(-np.pi - BARREL_PHI_PADDING, np.pi + BARREL_PHI_PADDING)
        ax.set_yticks(np.arange(-3.0, 3.1, 1.0))
        ax.set_yticklabels(["-3", "-2", "-1", "0", "1", "2", "3"])
    else:
        ax.set_ylim(None, result.rolls[0].polygon_ymax)
    ax.annotate(
        result.detector_unit,
        (0.05, 0.925),
        weight="bold",
        xycoords="axes fraction",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 1.0, "pad": 1.0},
        zorder=20,
    )
    if np.any(result.excluded_mask):
        ax.legend(
            handles=[Patch(facecolor="0.40", edgecolor="black", hatch="//", label="Excluded")],
            frameon=False,
            loc="best",
            handlelength=1.2,
            handletextpad=0.4,
            borderaxespad=0.5,
        )
    add_cms_label(ax, label, com, lumi=lumi, year=cms_year_label(year))
    return save_figure(fig, output, result.detector_unit, ext)


def style_log_y_axis(ax: plt.Axes, positive_counts: np.ndarray, min_floor: float | None = 0.8) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1))
    ax.yaxis.set_minor_formatter(NullFormatter())
    if len(positive_counts) > 0:
        lower = np.min(positive_counts) * 0.8
        if min_floor is not None:
            lower = max(lower, min_floor)
        ax.set_ylim(lower, np.max(positive_counts) * 1.8)
