from __future__ import annotations

import argparse
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
from matplotlib.patches import Patch, Polygon
from matplotlib.ticker import LogLocator, NullFormatter
from mpl_toolkits.axes_grid1 import make_axes_locatable

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import poisson_yerr  # type: ignore


DEFAULT_COLORS = tuple(mpl.rcParams["axes.prop_cycle"].by_key()["color"])


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


def dataset_specs_with_combined(specs: Sequence[DatasetSpec]) -> list[DatasetSpec]:
    combined = combine_dataset_specs(specs)
    return [*specs, combined] if str(combined.year) == "3" else list(specs)


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


def plot_output_dir(output: Path, category: str, year: int | str = "3", plot_type: str | None = None) -> Path:
    path = output / f"Run{year}" / category
    return path / plot_type if plot_type else path


def comparison_output_dir(output: Path, category: str, specs: Sequence[DatasetSpec], plot_type: str = "1d") -> Path:
    years = tuple(dict.fromkeys(spec.year for spec in specs))
    return plot_output_dir(output, category, years[0] if len(years) == 1 else "3", plot_type)


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
) -> ErrorbarContainer:
    mask = values > 0.0 if log_scale else np.ones_like(values, dtype=bool)
    if yerr is None:
        yerr = poisson_yerr(values, log_scale=log_scale)
    yerr_scaled = yerr[:, mask] / scale if yerr.ndim == 2 else yerr[mask] / scale

    return draw_errorbar_series(
        ax=ax,
        x=bin_centers(edges)[mask],
        y=values[mask] / scale,
        xerr=bin_half_widths(edges)[mask],
        yerr=yerr_scaled,
        color=color,
        label=label,
    )

def draw_colormesh(
    fig: plt.Figure,
    ax: plt.Axes,
    values: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    z_label: str,
    cmap_name: str = "viridis",
    mask_nonpositive: bool = True,
    min_visible_value: float | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad("white")
    mesh_values = np.ma.masked_invalid(np.ma.asarray(values, dtype=np.float64).T)
    if mask_nonpositive:
        mesh_values = np.ma.masked_where(mesh_values <= 0.0, mesh_values)
    if min_visible_value is not None:
        mesh_values = np.ma.masked_where(mesh_values < min_visible_value, mesh_values)
    mesh = ax.pcolormesh(x_edges, y_edges, mesh_values, shading="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    fig.colorbar(mesh, ax=ax, pad=0.02).set_label(z_label, fontsize=18)


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
        collection.set_facecolor(np.array([0.20, 0.20, 0.20, 1.0], dtype=np.float64))
        collection.set_edgecolor("black")
        collection.set_linewidth(lw)
        collection.set_hatch("////")
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
    return save_figure(fig, output / result.variable_name, result.detector_unit, ext)


def style_log_y_axis(ax: plt.Axes, positive_counts: np.ndarray) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10.0))
    ax.yaxis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1))
    ax.yaxis.set_minor_formatter(NullFormatter())
    if len(positive_counts) > 0:
        ax.set_ylim(max(np.min(positive_counts) * 0.8, 0.8), np.max(positive_counts) * 1.8)


def add_rpc_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--input", dest="inputs", action="append", nargs="+", required=True, type=Path,
                        help="Input merged histogram ROOT file(s), directory, or glob for one year. Repeat for multiple years.")
    parser.add_argument("-y", "--year", dest="years", action="append", required=True, type=int,
                        help="Year label matched to each --input group.")
    parser.add_argument("--lumi", dest="lumis", action="append", required=True, type=float,
                        help="Integrated luminosity matched to each --input group.")
    parser.add_argument("-s", "--com", type=float, help="Center-of-mass energy in TeV.")
    parser.add_argument("-o", "--output", required=True, type=Path,
                        help="Common plot output root; Run3/RunYYYY, category, and plot-type directories are created automatically.")
    parser.add_argument("-l", "--label", help="CMS extra label.")
    parser.add_argument("--ext", choices=["png", "pdf"], help="Output file extension.")


def validate_rpc_dataset_args(args: argparse.Namespace) -> None:
    if len(args.inputs) != len(args.years):
        raise RuntimeError(f"Number of --input ({len(args.inputs)}) and --year ({len(args.years)}) must match")
    if len(args.lumis) != len(args.inputs):
        raise RuntimeError(f"Number of --lumi ({len(args.lumis)}) must match --input ({len(args.inputs)})")


def rpc_plot_kwargs(args: argparse.Namespace) -> dict:
    kwargs = {key: value for key, value in vars(args).items() if value is not None}
    kwargs["input_groups"] = kwargs.pop("inputs")
    return kwargs
