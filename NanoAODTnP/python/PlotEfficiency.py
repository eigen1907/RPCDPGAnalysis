from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

from RPCDPGAnalysis.NanoAODTnP.HistIO import (  # type: ignore
    has_kinematic_2d_histograms,
    load_efficiency_2d_results,
    load_efficiency_results,
    merge_category_efficiencies,
)
from RPCDPGAnalysis.NanoAODTnP.BuildUtils import (  # type: ignore
    clopper_pearson_efficiency_yerr,
    efficiency_series,
    efficiency_stats,
)
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import (  # type: ignore
    DEFAULT_COLORS,
    add_cms_label,
    add_legend,
    add_panel_label,
    add_tag_and_probe_label,
    bin_centers,
    bin_half_widths,
    build_year_label,
    cms_year_label,
    combine_dataset_specs,
    comparison_output_dir,
    configure_elapsed_week_axis,
    configure_run_axis,
    configure_run_index_axis,
    draw_color_swatch,
    draw_errorbar_series,
    draw_point_series,
    elapsed_weeks_since_run3_start,
    new_figure,
    plot_group_label,
    plot_output_dir,
    plot_spec_color,
    plot_spec_label,
    add_plot_spec_legend,
    save_binned_value_map,
    save_figure,
    save_roll_value_map,
    variant_output_label,
    variant_output_target,
    year_color,
)
from RPCDPGAnalysis.NanoAODTnP.PlotConfig import (  # type: ignore
    PLOT_GROUPS,
    efficiency_1d_plots,
    prefixed_2d_plots,
    trend_plots,
    with_probe_pt_minimum,
)
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import RollMapSpec, build_roll_maps, roll_mask_names  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.HistBuild import (  # type: ignore
    regular_edges,
)


DEFAULT_EFF_THRESHOLD = 70.0
EFFICIENCY_ROLL_EDGES = regular_edges(DEFAULT_EFF_THRESHOLD, 100.0, 30)


def draw_efficiency_roll_summary(ax, rows: list[tuple[str, str, float, float]]) -> None:
    header_font = FontProperties(size=16)
    label_font = FontProperties(size=16)
    value_font = FontProperties(size=16)
    x_line0, x_line1 = 0.04, 0.08
    x_year, x_mean, x_bad = 0.10, 0.40, 0.55
    y_header, y_first, dy = 0.850, 0.800, 0.050

    ax.text(x_year, y_header, "Year", transform=ax.transAxes, ha="left", va="center", fontproperties=header_font)
    ax.text(
        x_mean,
        y_header,
        f"Mean (>{DEFAULT_EFF_THRESHOLD:.0f}%)",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontproperties=header_font,
    )
    ax.text(
        x_bad,
        y_header,
        f"% (<{DEFAULT_EFF_THRESHOLD:.0f}%)",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontproperties=header_font,
    )

    for row_index, (color, year_label, mean_good, frac_bad) in enumerate(rows):
        y = y_first - row_index * dy
        draw_color_swatch(ax, x_line0, x_line1, y, color)
        ax.text(x_year, y, year_label, transform=ax.transAxes, ha="left", va="center", fontproperties=label_font)
        ax.text(x_mean, y, f"{mean_good:.2f}", transform=ax.transAxes, ha="center", va="center", fontproperties=value_font)
        ax.text(x_bad, y, f"{frac_bad:.2f}", transform=ax.transAxes, ha="center", va="center", fontproperties=value_font)


KINEMATIC_2D_PLOTS = prefixed_2d_plots("eff")
EFF_1D_PLOTS = efficiency_1d_plots()
EFFICIENCY_ROLL_MAP = {
    "name": "efficiency",
    "label": "Efficiency [%]",
    "cmap": "RdYlGn",
    "vmin": 0.0,
    "vmax": 100.0,
}
PV_EFFICIENCY_OUTPUTS = {"eff-n-pv"}
Q_OVER_P_EFFICIENCY_OUTPUT = "eff-probe-q-over-p"
PROBE_EFFICIENCY_YLIM = (70.0, 100.0)
HIGH_EFFICIENCY_OUTPUTS = {
    *PV_EFFICIENCY_OUTPUTS,
    "eff-probe-pt",
    "eff-probe-eta",
}
ENDCAP_Q_OVER_P_XLIM = (-0.07, 0.07)
TREND_EFFICIENCY_YLIM = (70.0, 104.0)
TREND_EFFICIENCY_LEGEND_ANCHOR = (0.50, 0.12)

ELAPSED_TIME_EFFICIENCY_PLOTS = trend_plots("eff-elapsed-time", DEFAULT_COLORS[0])
RUN_EFFICIENCY_PLOTS = trend_plots("eff-run", DEFAULT_COLORS[0])
RUN_INDEX_EFFICIENCY_PLOTS = trend_plots("eff-run-index", DEFAULT_COLORS[0])
EFFICIENCY_TREND_KEYS = tuple(dict.fromkeys(
    key
    for plot in ELAPSED_TIME_EFFICIENCY_PLOTS
    for key, _ in plot["series"]
))
EFFICIENCY_RUN_KEYS = tuple(dict.fromkeys((*EFFICIENCY_TREND_KEYS, "all")))


def report_efficiency(passed: float, total: float) -> str:
    if total <= 0.0:
        return ""
    return f"{100.0 * passed / total:.6f}"


def save_roll_efficiency_report(spec, roll_result, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    output_path = output / f"eff_roll_{spec.year}.csv"
    print(f"[info] writing {output_path}", flush=True)
    roll_names = sorted(set(roll_result.total_by_roll) | set(roll_result.passed_by_roll))
    with output_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("year", "roll_name", "total", "passed", "efficiency"))
        for roll_name in roll_names:
            total = int(roll_result.total_by_roll.get(roll_name, 0))
            passed = int(roll_result.passed_by_roll.get(roll_name, 0))
            writer.writerow((spec.year, roll_name, total, passed, report_efficiency(passed, total)))
    return output_path


def save_run_efficiency_report(specs, run_results, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    output_path = output / "eff_run.csv"
    print(f"[info] writing {output_path}", flush=True)
    with output_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("year", "run", "total", "passed", "efficiency"))
        for spec in specs:
            result = run_results[spec]["all"]
            for run, total, passed in zip(result.labels, result.total, result.passed):
                total = int(total)
                if total <= 0:
                    continue
                passed = int(passed)
                writer.writerow((spec.year, int(run), total, passed, report_efficiency(passed, total)))
    return output_path


def save_efficiency_reports(specs, roll_results, run_results, output: Path) -> list[Path]:
    report_output = output / "reports"
    paths = [save_roll_efficiency_report(spec, roll_results[spec], report_output) for spec in specs]
    paths.append(save_run_efficiency_report(specs, run_results, report_output))
    return paths


def draw_efficiency_1d(results, plot: dict, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}", flush=True)
    combined_spec = combine_dataset_specs([spec for spec, _ in results])
    fig, ax = new_figure(label, com, year=cms_year_label(combined_spec.year))
    add_panel_label(ax, plot["panel_label"])
    add_tag_and_probe_label(ax)
    ax.set_xlabel(plot["xlabel"], fontsize=22)
    ax.set_ylabel("RPC Efficiency [%]", fontsize=22)
    if output_name == Q_OVER_P_EFFICIENCY_OUTPUT and (plot["region"] == "endcap" or plot["region"].startswith("RE")):
        ax.set_xlim(*ENDCAP_Q_OVER_P_XLIM)
    else:
        ax.set_xlim(float(plot["edges"][0]), float(plot["edges"][-1]))
    if output_name.startswith("eff-probe-"):
        ax.set_ylim(*PROBE_EFFICIENCY_YLIM)
    elif output_name in HIGH_EFFICIENCY_OUTPUTS:
        ax.set_ylim(70.0, 100.0)
    else:
        ax.set_ylim(0.0, 105.0)
    for idx, (spec, profile) in enumerate(results):
        mask, eff, yerr = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if np.any(mask):
            draw_errorbar_series(
                ax,
                bin_centers(profile.edges)[mask],
                eff,
                year_color(spec.year, idx),
                build_year_label(spec.year, spec.lumi),
                xerr=bin_half_widths(profile.edges)[mask],
                yerr=yerr,
                marker_size=6
            )
    if output_name == Q_OVER_P_EFFICIENCY_OUTPUT:
        add_legend(ax, loc="lower center", bbox_to_anchor=(0.50, 0.12))
    elif output_name in HIGH_EFFICIENCY_OUTPUTS:
        add_legend(ax, loc="lower right", bbox_to_anchor=(0.98, 0.12))
    else:
        add_legend(ax, bbox_to_anchor=(0.98, 0.88))
    if variant is not None:
        return save_figure(fig, output / output_name, variant, ext)
    return save_figure(fig, output, output_name, ext)


def draw_elapsed_time_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
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
        mask, efficiency, _ = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if not np.any(mask):
            continue
        timestamps = np.asarray(profile.labels[mask], dtype="datetime64[s]")
        weeks = elapsed_weeks_since_run3_start(timestamps)
        elapsed_x.append(weeks)
        draw_point_series(
            ax,
            weeks,
            efficiency,
            plot_spec_color(plot, idx),
            plot_spec_label(plot, series_label),
            marker_size=5,
        )
    configure_elapsed_week_axis(
        ax,
        np.concatenate(elapsed_x) if elapsed_x else np.empty(0, dtype=np.float64),
        "RPC Efficiency [%]",
        y_limits=TREND_EFFICIENCY_YLIM,
    )
    add_plot_spec_legend(ax, plot, loc="lower center", bbox_to_anchor=TREND_EFFICIENCY_LEGEND_ANCHOR)
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_run_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
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
        mask, efficiency, _ = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if not np.any(mask):
            continue
        runs = np.asarray(profile.labels[mask], dtype=np.float64)
        run_x.append(runs)
        draw_point_series(
            ax,
            runs,
            efficiency,
            plot_spec_color(plot, idx),
            plot_spec_label(plot, series_label),
            marker_size=5,
        )
    configure_run_axis(
        ax,
        np.concatenate(run_x) if run_x else np.empty(0, dtype=np.float64),
        "RPC Efficiency [%]",
        y_limits=TREND_EFFICIENCY_YLIM,
    )
    add_plot_spec_legend(ax, plot, loc="lower center", bbox_to_anchor=TREND_EFFICIENCY_LEGEND_ANCHOR)
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_run_index_efficiency(result_by_key, plot: dict, spec, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = plot["output"]
    variant = plot.get("variant")
    print(f"[info] plotting {variant_output_label(output_name, variant)}-Run{spec.year}", flush=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    add_cms_label(ax, label, com, lumi=spec.lumi, year=cms_year_label(spec.year))
    add_tag_and_probe_label(ax)
    add_panel_label(ax, plot.get("panel_label"))

    all_runs = result_by_key["all"]
    active_runs = np.asarray(all_runs.total) > 0
    run_indices = np.full(len(active_runs), np.nan, dtype=np.float64)
    run_indices[active_runs] = np.arange(np.count_nonzero(active_runs), dtype=np.float64)

    for idx, (key, series_label) in enumerate(plot["series"]):
        profile = result_by_key[key]
        mask, efficiency, _ = clopper_pearson_efficiency_yerr(profile.passed, profile.total)
        if not np.any(mask):
            continue
        draw_point_series(
            ax,
            run_indices[mask],
            efficiency,
            plot_spec_color(plot, idx),
            plot_spec_label(plot, series_label),
            marker_size=5,
        )
    configure_run_index_axis(
        ax,
        int(np.count_nonzero(active_runs)),
        "RPC Efficiency [%]",
        y_limits=TREND_EFFICIENCY_YLIM,
    )
    add_plot_spec_legend(ax, plot, loc="lower center", bbox_to_anchor=TREND_EFFICIENCY_LEGEND_ANCHOR)
    fig.tight_layout()
    output_dir, file_name = variant_output_target(output, output_name, variant)
    return save_figure(fig, output_dir, file_name, ext)


def draw_nrolls_efficiency(results, region: str, output: Path, label: str, com: float, ext: str) -> Path:
    output_name = "nrolls-eff"
    print(f"[info] plotting {variant_output_label(output_name, region)}", flush=True)
    combined_spec = combine_dataset_specs([spec for spec, _ in results])
    fig, ax = new_figure(label, com, year=cms_year_label(combined_spec.year))
    add_panel_label(ax, plot_group_label(region))
    add_tag_and_probe_label(ax)
    ax.set_xlabel("Efficiency [%]", fontsize=22)
    ax.set_ylabel("Number of Rolls", fontsize=22)
    ax.set_xlim(DEFAULT_EFF_THRESHOLD, 100.0)
    summary_rows: list[tuple[str, str, float, float]] = []
    max_count = 0.0
    edges = EFFICIENCY_ROLL_EDGES
    for idx, (spec, roll_result) in enumerate(results):
        values = roll_result.efficiency_by_region[region]
        counts, _ = np.histogram(values[np.isfinite(values)], bins=edges)
        counts = counts.astype(np.float64, copy=False)
        max_count = max(max_count, float(np.max(counts)) if len(counts) else 0.0)
        color = year_color(spec.year, idx)
        ax.stairs(counts, edges, color=color, linewidth=3.0)
        mean_good, frac_bad = efficiency_stats(values, DEFAULT_EFF_THRESHOLD)
        summary_rows.append((color, build_year_label(spec.year, spec.lumi), mean_good, frac_bad))
    if max_count > 0.0:
        ax.set_ylim(0.0, 1.2 * max_count)
    draw_efficiency_roll_summary(ax, summary_rows)
    output_dir, file_name = variant_output_target(output, output_name, region)
    return save_figure(fig, output_dir, file_name, ext)


def save_efficiency_2d(
    total: np.ndarray,
    passed: np.ndarray,
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
    efficiency = np.divide(100.0 * passed, total, out=np.full_like(total, np.nan, dtype=np.float64), where=total > 0)
    return save_binned_value_map(
        efficiency,
        x_edges,
        y_edges,
        xlabel,
        ylabel,
        "RPC Efficiency [%]",
        output / output_name,
        group,
        label,
        com,
        spec.lumi,
        spec.year,
        ext,
        "RdYlGn",
        70.0,
        100.0,
    )


def save_efficiency_2d_count(
    values: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    output_name: str,
    group: str,
    xlabel: str,
    ylabel: str,
    value_label: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> Path:
    finite = values[np.isfinite(values) & (values > 0.0)]
    vmax = max(float(np.max(finite)) if len(finite) else 0.0, 1.0)
    return save_binned_value_map(
        values,
        x_edges,
        y_edges,
        xlabel,
        ylabel,
        value_label,
        output / output_name,
        group,
        label,
        com,
        spec.lumi,
        spec.year,
        ext,
        "viridis",
        0.0,
        vmax,
        mask_zero=True,
    )


def save_efficiency_2d_components(
    total: np.ndarray,
    passed: np.ndarray,
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
) -> list[Path]:
    denominator_name = output_name.replace("eff-", "denom-", 1)
    numerator_name = output_name.replace("eff-", "numer-", 1)
    return [
        save_efficiency_2d_count(
            total, x_edges, y_edges, output, denominator_name, group, xlabel, ylabel,
            "Denominator Events / bin", spec, label, com, ext,
        ),
        save_efficiency_2d_count(
            passed, x_edges, y_edges, output, numerator_name, group, xlabel, ylabel,
            "Numerator Events / bin", spec, label, com, ext,
        ),
    ]


def save_efficiency_2d_outputs(
    total: np.ndarray,
    passed: np.ndarray,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
    output: Path,
    plot: dict,
    group: str,
    spec,
    label: str,
    com: float,
    ext: str,
) -> list[Path]:
    output_name = plot["output"]
    xlabel = plot["xlabel"]
    ylabel = plot["ylabel"]
    return [
        save_efficiency_2d(
            total,
            passed,
            x_edges,
            y_edges,
            output,
            output_name,
            group,
            xlabel,
            ylabel,
            spec,
            label,
            com,
            ext,
        ),
        *save_efficiency_2d_components(
            total,
            passed,
            x_edges,
            y_edges,
            output,
            output_name,
            group,
            xlabel,
            ylabel,
            spec,
            label,
            com,
            ext,
        ),
    ]


def draw_efficiency_2d_for_spec(
    histograms,
    spec,
    output: Path,
    label: str,
    com: float,
    ext: str,
    plots_2d=KINEMATIC_2D_PLOTS,
) -> list[Path]:
    if not has_kinematic_2d_histograms(histograms):
        print(f"[warning] skipping efficiency 2D plots for Run{spec.year}: reanalysis with the current histogram schema is required", flush=True)
        return []
    paths: list[Path] = []
    output_2d = plot_output_dir(output, "efficiency/2d", spec.year)
    for group in PLOT_GROUPS:
        results_2d = load_efficiency_2d_results(histograms, plots_2d, group)
        for plot in plots_2d:
            result = results_2d[plot["name"]]
            paths.extend(
                save_efficiency_2d_outputs(
                    result.total,
                    result.passed,
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


def draw_run3_efficiency_2d(
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
        print(f"[warning] skipping Run 3 efficiency 2D plots: {years} need reanalysis with the current histogram schema", flush=True)
        return []

    spec = combine_dataset_specs(specs)
    if str(spec.year) != "3":
        return []

    paths: list[Path] = []
    output_2d = plot_output_dir(output, "efficiency/2d", spec.year)
    for group in PLOT_GROUPS:
        results_by_spec = [
            load_efficiency_2d_results(histograms_by_spec[each_spec], plots_2d, group)
            for each_spec in specs
        ]
        for plot in plots_2d:
            name = plot["name"]
            first = results_by_spec[0][name]
            total = np.sum([results[name].total for results in results_by_spec], axis=0)
            passed = np.sum([results[name].passed for results in results_by_spec], axis=0)
            paths.extend(
                save_efficiency_2d_outputs(
                    total,
                    passed,
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


def plot_efficiency(
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
    plots_1d = with_probe_pt_minimum(EFF_1D_PLOTS, probe_pt_minimum)
    plots_2d = with_probe_pt_minimum(KINEMATIC_2D_PLOTS, probe_pt_minimum)
    results_1d = {}
    roll_results = {}
    elapsed_results = {}
    run_results = {}
    for spec in specs:
        results_1d[spec], roll_results[spec], elapsed_results[spec], run_results[spec] = load_efficiency_results(
            histograms_by_spec[spec],
            plots_1d,
            run_meta,
            EFFICIENCY_RUN_KEYS,
        )

    paths: list[Path] = []
    paths.extend(save_efficiency_reports(specs, roll_results, run_results, output))
    comparison_output = comparison_output_dir(output, "efficiency/1d", specs)
    for plot in plots_1d:
        series = [
            (spec, results_1d[spec][plot["name"]])
            for spec in specs
            if plot["name"] in results_1d[spec]
        ]
        if series:
            paths.append(draw_efficiency_1d(series, plot, comparison_output, label, com, ext))
    for region in ("barrel", "endcap"):
        paths.append(draw_nrolls_efficiency([(spec, roll_results[spec]) for spec in specs], region, comparison_output, label, com, ext))
    paths.extend(draw_run3_efficiency_2d(specs, histograms_by_spec, output, label, com, ext, plots_2d))
    if draw_yearly_2d:
        for spec in specs:
            paths.extend(draw_efficiency_2d_for_spec(histograms_by_spec[spec], spec, output, label, com, ext, plots_2d))

    combined_spec = combine_dataset_specs(specs)
    run3_elapsed = {
        key: merge_category_efficiencies([elapsed_results[spec][key] for spec in specs])
        for key in EFFICIENCY_TREND_KEYS
    }
    run3_run = {
        key: merge_category_efficiencies([run_results[spec][key] for spec in specs])
        for key in EFFICIENCY_RUN_KEYS
    }
    output_1d = plot_output_dir(output, "efficiency/1d", combined_spec.year)
    for plot in RUN_EFFICIENCY_PLOTS:
        paths.append(draw_run_efficiency(run3_run, plot, combined_spec, output_1d, label, com, ext))
    for plot in RUN_INDEX_EFFICIENCY_PLOTS:
        paths.append(draw_run_index_efficiency(run3_run, plot, combined_spec, output_1d, label, com, ext))
    for plot in ELAPSED_TIME_EFFICIENCY_PLOTS:
        paths.append(draw_elapsed_time_efficiency(run3_elapsed, plot, combined_spec, output_1d, label, com, ext))

    if draw_roll_maps:
        if geom is None:
            raise RuntimeError("Efficiency roll maps require RPC geometry")
        for spec in specs:
            roll_result = roll_results[spec]
            masked = roll_mask_names(spec.year) if show_excluded_rolls else set()
            eff = efficiency_series(roll_result.total_by_roll, roll_result.passed_by_roll)
            roll_map_specs = [
                RollMapSpec(
                    EFFICIENCY_ROLL_MAP["name"],
                    eff,
                    EFFICIENCY_ROLL_MAP["label"],
                    EFFICIENCY_ROLL_MAP["cmap"],
                    EFFICIENCY_ROLL_MAP["vmin"],
                    EFFICIENCY_ROLL_MAP["vmax"],
                    excluded_rolls=masked,
                )
            ]
            for roll_map in build_roll_maps(geom, roll_map_specs):
                paths.append(save_roll_value_map(roll_map, plot_output_dir(output, "efficiency/map", spec.year), spec.year, label, com, spec.lumi, ext))
    return paths
