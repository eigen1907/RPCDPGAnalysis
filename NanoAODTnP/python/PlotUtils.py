from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import mplhep as mh
import numpy as np
from matplotlib.collections import PatchCollection
from matplotlib.colors import Colormap
from matplotlib.container import ErrorbarContainer
from matplotlib.patches import Patch, Polygon, StepPatch
from matplotlib.ticker import LogLocator, NullFormatter
from mpl_toolkits.axes_grid1 import make_axes_locatable

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import poisson_yerr  # type: ignore


DEFAULT_COLORS = tuple(mpl.rcParams["axes.prop_cycle"].by_key()["color"])
LINE_ALPHA = 0.7


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


def add_cms_label(ax: plt.Axes, label: str, com: float, lumi: float | None = None, year: int | str | None = None) -> None:
    mh.cms.label(ax=ax, llabel=label, lumi=lumi, year=year, com=com)


def build_year_label(year: int | str, lumi: float) -> str:
    year_label = "Run 3" if str(year) == "3" else str(year)
    return f"{year_label} ({lumi:g} fb$^{{-1}}$)"


def new_figure(
    cms_label: str,
    com_energy: float,
    figsize: tuple[float, float] = (12, 8),
) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=figsize)
    add_cms_label(ax=ax, label=cms_label, com=com_energy)
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
) -> Path:
    print(f"[info] plotting {output_name}-Run{year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    mesh = ax.pcolormesh(x_edges, y_edges, np.ma.masked_invalid(values.T), cmap=cmap, vmin=vmin, vmax=vmax, shading="flat")
    ax.set_xlabel(xlabel, fontsize=22)
    ax.set_ylabel(ylabel, fontsize=22)
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label(value_label, fontsize=20)
    add_cms_label(ax, label, com, lumi=lumi, year=cms_year_label(year))
    fig.tight_layout()
    return save_figure(fig, output, output_name, ext)


def bin_centers(edges: np.ndarray) -> np.ndarray:
    return 0.5 * (edges[:-1] + edges[1:])


def bin_half_widths(edges: np.ndarray) -> np.ndarray:
    return 0.5 * np.diff(edges)


def count_scale(max_count: float) -> tuple[int, float]:
    scale_exp = int(np.floor(np.log10(max_count))) if max_count > 0.0 else 0
    return scale_exp, 10.0 ** scale_exp


def annotate_count_scale(ax: plt.Axes, scale_exp: int) -> None:
    if scale_exp != 0:
        ax.annotate(
            rf"$x10^{{{scale_exp}}}$",
            (-0.06, 1.0),
            xycoords="axes fraction",
            fontsize=18,
            horizontalalignment="left",
        )


def add_legend(ax: plt.Axes, loc: str = "upper right", frameon: bool = False, fontsize: int = 18) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, fontsize=fontsize, loc=loc, frameon=frameon, handlelength=1.6, handleheight=1.2)


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
        capsize=3,
        elinewidth=1.8,
        alpha=LINE_ALPHA,
        label=label,
    )


def draw_binned_errorbar(
    ax: plt.Axes,
    values: np.ndarray,
    edges: np.ndarray,
    color: str,
    label: str,
    yerr: np.ndarray | None = None,
    scale: float = 1.0,
    log_scale: bool = False,
) -> StepPatch:
    positive = values > 0.0
    if yerr is None:
        yerr = poisson_yerr(values, log_scale=log_scale)
    yerr_scaled = yerr[:, positive] / scale if yerr.ndim == 2 else yerr[positive] / scale
    step_values = values.astype(np.float64, copy=True) / scale
    if log_scale:
        step_values[~positive] = np.nan
    handle = ax.stairs(step_values, edges, color=color, alpha=LINE_ALPHA, label=label)
    ax.errorbar(
        bin_centers(edges)[positive],
        values[positive] / scale,
        yerr=yerr_scaled,
        fmt="none",
        color=color,
        capsize=3,
        elinewidth=1.8,
        alpha=LINE_ALPHA,
        label="_nolegend_",
    )
    return handle


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
    cax = draw_roll_map(ax, result.patches, result.values, excluded_mask=result.excluded_mask, inactive_mask=result.inactive_mask, cmap=result.cmap, vmin=result.vmin, vmax=result.vmax)
    ax.set_xlabel(result.rolls[0].polygon_xlabel)
    ax.set_ylabel(result.rolls[0].polygon_ylabel)
    cax.set_ylabel(result.value_label)
    ax.set_ylim(None, result.rolls[0].polygon_ymax)
    ax.annotate(result.detector_unit, (0.05, 0.925), weight="bold", xycoords="axes fraction")
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


def style_log_y_axis(ax: plt.Axes, positive_counts: np.ndarray) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1))
    ax.yaxis.set_minor_formatter(NullFormatter())
    if len(positive_counts) > 0:
        ax.set_ylim(max(np.min(positive_counts) * 0.8, 0.8), np.max(positive_counts) * 1.8)

