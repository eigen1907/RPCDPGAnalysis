from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from RPCDPGAnalysis.NanoAODTnP.BuildUtils import mean_and_error, rms_and_error  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistIO import (  # type: ignore
    has_kinematic_2d_histograms,
    load_cls_2d_results,
    load_rpc_rms_results,
    load_rpc_results,
    merge_category_profiles,
)
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import (  # type: ignore
    DEFAULT_COLORS,
    add_cms_label,
    add_legend,
    add_panel_label,
    add_tag_and_probe_label,
    annotate_count_scale,
    bin_centers,
    bin_half_widths,
    build_year_label,
    cms_year_label,
    combine_dataset_specs,
    comparison_output_dir,
    configure_elapsed_week_axis,
    configure_run_axis,
    count_scale,
    draw_binned_stairs,
    draw_errorbar_series,
    draw_point_series,
    draw_year_mean_summary,
    draw_year_rms_summary,
    draw_year_summary,
    elapsed_weeks_since_run3_start,
    histogram_y_label,
    new_figure,
    plot_group_label,
    plot_output_dir,
    plot_spec_color,
    plot_spec_label,
    add_plot_spec_legend,
    save_binned_value_map,
    save_figure,
    save_roll_value_map,
    style_log_y_axis,
    variant_output_label,
    variant_output_target,
    year_color,
)
from RPCDPGAnalysis.NanoAODTnP.PlotConfig import (  # type: ignore
    PLOT_GROUPS,
    PT_EDGES,
    mean_cls_1d_plots,
    prefixed_2d_plots,
    trend_plots,
    with_probe_pt_minimum,
)
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_names  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import RPC_BX_EDGES, regular_edges  # type: ignore


CLS_EDGES = np.arange(-0.5, 10.6, 1.0, dtype=np.float64)
BX_EDGES = RPC_BX_EDGES
RESIDUAL_X_EDGES = regular_edges(-20.0, 20.0, 80)
KINEMATIC_2D_PLOTS = prefixed_2d_plots("mean-cls")

COUNT_PLOTS: list[dict] = []
RMS_PLOTS: list[dict] = []
for group in PLOT_GROUPS:
    panel_label = plot_group_label(group)
    COUNT_PLOTS.append({
        "name": f"residual_x_{group}",
        "output": "rpc-residual-x",
        "variant": group,
        "branch": "residual_x",
        "edges": RESIDUAL_X_EDGES,
        "xlabel": r"Residual $x$ [cm]",
        "ylabel": "Normalized",
        "unit": r"$\mathrm{cm}$",
        "region": group,
        "selection": "match",
        "log_scale": False,
        "panel_label": panel_label,
        "normalize": True,
    })
    COUNT_PLOTS.append({
        "name": f"cls_{group}",
        "output": "rpc-cls",
        "variant": group,
        "branch": "cls",
        "edges": CLS_EDGES,
        "xlabel": "Cluster Size",
        "ylabel": "Normalized",
        "region": group,
        "selection": "match",
        "log_scale": False,
        "x_ticks": np.arange(1, 11),
        "xlim": (0.5, 10.5),
        "panel_label": panel_label,
        "normalize": True,
    })
    COUNT_PLOTS.append({
        "name": f"bx_{group}",
        "output": "rpc-bx",
        "variant": group,
        "branch": "bx",
        "edges": BX_EDGES,
        "xlabel": "Bunch Crossing",
        "ylabel": "Normalized",
        "region": group,
        "selection": "match",
        "log_scale": False,
        "x_ticks": np.arange(-4, 5),
        "panel_label": panel_label,
        "normalize": True,
    })
    COUNT_PLOTS.append({
        "name": f"bx_{group}",
        "output": "rpc-bx-log",
        "variant": group,
        "branch": "bx",
        "edges": BX_EDGES,
        "xlabel": "Bunch Crossing",
        "ylabel": "Normalized",
        "region": group,
        "selection": "match",
        "log_scale": True,
        "ylim": (None, 10 ** 0.8),
        "x_ticks": np.arange(-4, 5),
        "panel_label": panel_label,
        "normalize": True,
    })
    RMS_PLOTS.append({
        "name": f"rms_residual_x_probe_pt_{group}",
        "output": "rms-residual-x-probe-pt",
        "variant": group,
        "value_branch": "residual_x",
        "x_branch": "probe_pt",
        "edges": PT_EDGES,
        "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
        "ylabel": r"RMS residual $x$ [cm]",
        "region": group,
        "panel_label": panel_label,
    })
MEAN_PLOTS = mean_cls_1d_plots()

ELAPSED_TIME_CLS_PLOTS = trend_plots("mean-cls-elapsed-time", DEFAULT_COLORS[1])
RUN_CLS_PLOTS = trend_plots("mean-cls-run", DEFAULT_COLORS[1])
CLS_TREND_KEYS = tuple(dict.fromkeys(
    key
    for plot in ELAPSED_TIME_CLS_PLOTS
    for key, _ in plot["series"]
))


RPC_ROLL_MAP = {"name": "cls", "label": "Average Cluster Size", "cmap": "viridis", "vmin": 0.5, "vmax": 4.5}


def _draw_normalized_counts(ax, results, plot: dict) -> None:
    max_value = 0.0
    positive_values: list[np.ndarray] = []
    for idx, (spec, result) in enumerate(results):
        total = float(np.sum(result.counts))
        if total > 0.0:
            values = result.counts / total
            positive = values[values > 0.0]
            if len(positive):
                positive_values.append(positive)
            max_value = max(max_value, float(np.max(values)))
        else:
            values = np.zeros_like(result.counts, dtype=np.float64)
        draw_binned_stairs(
            ax,
            values,
            result.edges,
            color=year_color(spec.year, idx),
            label="_nolegend_",
            log_scale=plot["log_scale"],
        )
    if plot["log_scale"]:
        style_log_y_axis(
            ax,
            np.concatenate(positive_values) if positive_values else np.empty(0, dtype=np.float64),
            min_floor=None,
        )
    elif max_value > 0.0:
        ax.set_ylim(0.0, 1.35 * max_value)


def _draw_raw_counts(ax, results, plot: dict) -> None:
    if plot["log_scale"]:
        positive_counts: list[np.ndarray] = []
        for idx, (spec, result) in enumerate(results):
            draw_binned_stairs(
                ax,
                result.counts,
                result.edges,
                color=year_color(spec.year, idx),
                label="_nolegend_",
                log_scale=True,
            )
            positive = result.counts[result.counts > 0]
            if len(positive):
                positive_counts.append(positive)
        style_log_y_axis(ax, np.concatenate(positive_counts) if positive_counts else np.empty(0, dtype=np.float64))
        return

    max_count = max((float(np.max(result.counts)) for _, result in results if len(result.counts)), default=0.0)
    scale_exp, scale = count_scale(max_count)
    for idx, (spec, result) in enumerate(results):
        draw_binned_stairs(ax, result.counts, result.edges, color=year_color(spec.year, idx), label="_nolegend_", scale=scale)
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.35 * max_count / scale)
    annotate_count_scale(ax, scale_exp)


def _hist1d_rms(result) -> float:
    total = float(np.sum(result.counts))
    if total <= 0.0:
        return np.nan
    centers = bin_centers(result.edges)
    mean = result.mean if np.isfinite(result.mean) else float(np.sum(result.counts * centers) / total)
    variance = float(np.sum(result.counts * np.square(centers - mean)) / total)
    return float(np.sqrt(max(variance, 0.0)))


def draw_count_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    combined_spec = combine_dataset_specs([spec for spec, _ in results])
    fig, ax = new_figure(label, com, year=cms_year_label(combined_spec.year))
    if "panel_label" in plot:
        add_panel_label(ax, plot["panel_label"])
    add_tag_and_probe_label(ax)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    normalized = plot.get("normalize", False)
    ylabel = (
        plot["ylabel"]
        if normalized
        else histogram_y_label(plot["ylabel"], plot["edges"], plot.get("unit"))
    )
    ax.set_ylabel(ylabel, fontsize=22)
    xlim = plot.get("xlim", (float(plot["edges"][0]), float(plot["edges"][-1])))
    ax.set_xlim(*xlim)
    if "x_ticks" in plot:
        ax.set_xticks(plot["x_ticks"])
    if normalized:
        _draw_normalized_counts(ax, results, plot)
    else:
        _draw_raw_counts(ax, results, plot)
    if "ylim" in plot:
        ax.set_ylim(*plot["ylim"])
    if output_name in {"rpc-bx", "rpc-bx-log"}:
        draw_year_summary(ax, [
            (year_color(spec.year, idx), build_year_label(spec.year, spec.lumi))
            for idx, (spec, result) in enumerate(results)
        ])
    elif output_name == "rpc-residual-x":
        draw_year_rms_summary(ax, [
            (
                year_color(spec.year, idx),
                build_year_label(spec.year, spec.lumi),
                _hist1d_rms(result),
            )
            for idx, (spec, result) in enumerate(results)
        ])
    elif output_name == "rpc-cls":
        draw_year_mean_summary(ax, [
            (
                year_color(spec.year, idx),
                build_year_label(spec.year, spec.lumi),
                result.mean,
            )
            for idx, (spec, result) in enumerate(results)
        ])
    else:
        draw_year_mean_summary(ax, [
            (year_color(spec.year, idx), build_year_label(spec.year, spec.lumi), result.mean)
            for idx, (spec, result) in enumerate(results)
        ])
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_mean_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    combined_spec = combine_dataset_specs([spec for spec, _ in results])
    fig, ax = new_figure(label, com, year=cms_year_label(combined_spec.year))
    add_panel_label(ax, plot["panel_label"])
    add_tag_and_probe_label(ax)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    ax.set_ylim(1.0, 3.0)
    for idx, (spec, profile) in enumerate(results):
        mask, mean, yerr = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if np.any(mask):
            draw_errorbar_series(
                ax,
                bin_centers(profile.edges)[mask],
                mean,
                year_color(spec.year, idx),
                build_year_label(spec.year, spec.lumi),
                xerr=bin_half_widths(profile.edges)[mask],
                yerr=yerr,
            )
    add_legend(ax, bbox_to_anchor=(0.98, 0.88))
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_rms_plot(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    combined_spec = combine_dataset_specs([spec for spec, _ in results])
    fig, ax = new_figure(label, com, year=cms_year_label(combined_spec.year))
    add_panel_label(ax, plot["panel_label"])
    add_tag_and_probe_label(ax)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel(plot["ylabel"], fontsize=22)
    ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    plotted_values: list[np.ndarray] = []
    for idx, (spec, profile) in enumerate(results):
        mask, rms, yerr = rms_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if np.any(mask):
            plotted_values.append(rms[np.isfinite(rms)])
            draw_errorbar_series(
                ax,
                bin_centers(profile.edges)[mask],
                rms,
                year_color(spec.year, idx),
                build_year_label(spec.year, spec.lumi),
                xerr=bin_half_widths(profile.edges)[mask],
                yerr=yerr,
            )
    finite_values = np.concatenate(plotted_values) if plotted_values else np.empty(0, dtype=np.float64)
    finite_values = finite_values[np.isfinite(finite_values)]
    if len(finite_values):
        ax.set_ylim(0.0, 1.35 * float(np.max(finite_values)))
    add_legend(ax, bbox_to_anchor=(0.98, 0.88))
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def save_cls_2d(
    value_sum: np.ndarray,
    counts: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    output_name: str,
    group: str,
    xlabel: str,
    ylabel: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> Path:
    mean = np.divide(value_sum, counts, out=np.full_like(value_sum, np.nan, dtype=np.float64), where=counts > 0)
    return save_binned_value_map(
        mean,
        x_edges,
        y_edges,
        xlabel,
        ylabel,
        "Average Cluster Size",
        output / output_name,
        group,
        label,
        com,
        spec.lumi,
        spec.year,
        ext,
        "viridis",
        1.0,
        3.0,
    )


def save_cls_2d_output(
    value_sum: np.ndarray,
    counts: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    plot: dict,
    group: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> Path:
    return save_cls_2d(
        value_sum,
        counts,
        x_edges,
        y_edges,
        output,
        plot["output"],
        group,
        plot["xlabel"],
        plot["ylabel"],
        spec,
        label,
        com,
        ext,
    )


def draw_cls_2d_for_spec(
    histograms,
    spec,
    output: Path,
    label: str,
    com: float,
    ext: str,
    plots_2d=KINEMATIC_2D_PLOTS,
) -> list[Path]:
    if not has_kinematic_2d_histograms(histograms):
        print(f"[warning] skipping mean CLS 2D plots for Run{spec.year}: reanalysis with the current histogram schema is required", flush=True)
        return []
    paths: list[Path] = []
    output_2d = plot_output_dir(output, "rpc/2d", spec.year)
    for group in PLOT_GROUPS:
        results_2d = load_cls_2d_results(histograms, plots_2d, group)
        for plot in plots_2d:
            result = results_2d[plot["name"]]
            paths.append(
                save_cls_2d_output(
                    result.value_sum,
                    result.counts,
                    result.x_edges,
                    result.y_edges,
                    output_2d,
                    plot,
                    group,
                    spec,
                    label,
                    com,
                    ext,
                )
            )
    return paths


def draw_run3_cls_2d(
    specs,
    histograms_by_spec,
    output: Path,
    label: str,
    com: float,
    ext: str,
    plots_2d=KINEMATIC_2D_PLOTS,
) -> list[Path]:
    missing = [spec for spec in specs if not has_kinematic_2d_histograms(histograms_by_spec[spec])]
    if missing:
        years = ", ".join(f"Run{spec.year}" for spec in missing)
        print(f"[warning] skipping Run 3 mean CLS 2D plots: {years} need reanalysis with the current histogram schema", flush=True)
        return []

    spec = combine_dataset_specs(specs)
    if str(spec.year) != "3":
        return []

    paths: list[Path] = []
    output_2d = plot_output_dir(output, "rpc/2d", spec.year)
    for group in PLOT_GROUPS:
        results_by_spec = [
            load_cls_2d_results(histograms_by_spec[each_spec], plots_2d, group)
            for each_spec in specs
        ]
        for plot in plots_2d:
            name = plot["name"]
            first = results_by_spec[0][name]
            value_sum = np.sum([results[name].value_sum for results in results_by_spec], axis=0)
            counts = np.sum([results[name].counts for results in results_by_spec], axis=0)
            paths.append(
                save_cls_2d_output(
                    value_sum,
                    counts,
                    first.x_edges,
                    first.y_edges,
                    output_2d,
                    plot,
                    group,
                    spec,
                    label,
                    com,
                    ext,
                )
            )
    return paths


def draw_elapsed_time_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    add_tag_and_probe_label(ax)
    add_panel_label(ax, plot.get("panel_label"))
    elapsed_x: list[np.ndarray] = []
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, _ = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if not np.any(mask):
            continue
        timestamps = np.asarray(profile.labels[mask], dtype="datetime64[s]")
        weeks = elapsed_weeks_since_run3_start(timestamps)
        elapsed_x.append(weeks)
        draw_point_series(
            ax,
            weeks,
            mean,
            plot_spec_color(plot, idx),
            plot_spec_label(plot, series_label),
            marker_size=5,
        )
    configure_elapsed_week_axis(
        ax,
        np.concatenate(elapsed_x) if elapsed_x else np.empty(0, dtype=np.float64),
        "Average Cluster Size",
        y_limits=(1.0, 3.0),
    )
    add_plot_spec_legend(ax, plot, bbox_to_anchor=(0.98, 0.88))
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_run_cls(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    add_tag_and_probe_label(ax)
    add_panel_label(ax, plot.get("panel_label"))
    run_x: list[np.ndarray] = []
    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, mean, _ = mean_and_error(profile.value_sum, profile.value_sumsq, profile.counts)
        if not np.any(mask):
            continue
        runs = np.asarray(profile.labels[mask], dtype=np.float64)
        run_x.append(runs)
        draw_point_series(
            ax,
            runs,
            mean,
            plot_spec_color(plot, idx),
            plot_spec_label(plot, series_label),
            marker_size=5,
        )
    configure_run_axis(
        ax,
        np.concatenate(run_x) if run_x else np.empty(0, dtype=np.float64),
        "Average Cluster Size",
        y_limits=(1.0, 3.0),
    )
    add_plot_spec_legend(ax, plot, bbox_to_anchor=(0.98, 0.88))
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def plot_rpc(
    specs,
    histograms_by_spec,
    output: Path,
    geom,
    run_meta,
    com: float = 13.6,
    label: str = "Preliminary",
    ext: str = "png",
    draw_yearly_2d: bool = False,
    draw_roll_maps: bool = False,
    show_excluded_rolls: bool = True,
    probe_pt_minimum: float | None = None,
) -> list[Path]:
    mean_plots = with_probe_pt_minimum(MEAN_PLOTS, probe_pt_minimum)
    rms_plots = with_probe_pt_minimum(RMS_PLOTS, probe_pt_minimum)
    plots_2d = with_probe_pt_minimum(KINEMATIC_2D_PLOTS, probe_pt_minimum)
    count_results = {}
    mean_results = {}
    rms_results = {}
    roll_results = {}
    elapsed_results = {}
    run_results = {}
    for spec in specs:
        count_results[spec], mean_results[spec], roll_results[spec], elapsed_results[spec], run_results[spec] = load_rpc_results(
            histograms_by_spec[spec],
            COUNT_PLOTS,
            mean_plots,
            run_meta,
            CLS_TREND_KEYS,
        )
        rms_results[spec] = load_rpc_rms_results(histograms_by_spec[spec], rms_plots)

    paths: list[Path] = []
    comparison_output = comparison_output_dir(output, "rpc/1d", specs)
    for plot in COUNT_PLOTS:
        paths.append(draw_count_plot([(spec, count_results[spec][plot["name"]]) for spec in specs], plot, comparison_output, label, com, ext))
    for plot in mean_plots:
        series = [
            (spec, mean_results[spec][plot["name"]])
            for spec in specs
            if plot["name"] in mean_results[spec]
        ]
        if series:
            paths.append(draw_mean_plot(series, plot, comparison_output, label, com, ext))
    for plot in rms_plots:
        series = [
            (spec, rms_results[spec][plot["name"]])
            for spec in specs
            if plot["name"] in rms_results[spec]
        ]
        if series:
            paths.append(draw_rms_plot(series, plot, comparison_output, label, com, ext))

    paths.extend(draw_run3_cls_2d(specs, histograms_by_spec, output, label, com, ext, plots_2d))
    if draw_yearly_2d:
        for spec in specs:
            paths.extend(draw_cls_2d_for_spec(histograms_by_spec[spec], spec, output, label, com, ext, plots_2d))

    combined_spec = combine_dataset_specs(specs)
    run3_elapsed = {
        key: merge_category_profiles([elapsed_results[spec][key] for spec in specs])
        for key in CLS_TREND_KEYS
    }
    run3_run = {
        key: merge_category_profiles([run_results[spec][key] for spec in specs])
        for key in CLS_TREND_KEYS
    }
    output_1d = plot_output_dir(output, "rpc/1d", combined_spec.year)
    for plot in RUN_CLS_PLOTS:
        paths.append(draw_run_cls(run3_run, plot, combined_spec, output_1d, label, com, ext))
    for plot in ELAPSED_TIME_CLS_PLOTS:
        paths.append(draw_elapsed_time_cls(run3_elapsed, plot, combined_spec, output_1d, label, com, ext))

    if draw_roll_maps:
        if geom is None:
            raise RuntimeError("RPC roll maps require RPC geometry")
        for spec in specs:
            roll_result = roll_results[spec]
            masked = roll_mask_names(spec.year) if show_excluded_rolls else set()
            roll_map_spec = RollMapSpec(
                RPC_ROLL_MAP["name"],
                roll_result.mean_by_roll,
                RPC_ROLL_MAP["label"],
                RPC_ROLL_MAP["cmap"],
                RPC_ROLL_MAP["vmin"],
                RPC_ROLL_MAP["vmax"],
                excluded_rolls=masked,
            )
            for roll_map in build_roll_maps(geom, [roll_map_spec]):
                paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "rpc/map", spec.year), spec.year, label, com, spec.lumi, ext))
    return paths
