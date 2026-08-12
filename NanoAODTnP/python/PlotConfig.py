from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from RPCDPGAnalysis.NanoAODTnP.HistBuild import (  # type: ignore
    PLOT_ETA_EDGES,
    PLOT_PHI_EDGES,
    PLOT_PT_EDGES,
    PLOT_P_EDGES,
    PLOT_PV_EDGES,
    PLOT_Q_OVER_P_EDGES,
    STATION_NAMES,
)
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import plot_group_label  # type: ignore


PLOT_GROUPS = ("all", "barrel", "endcap", *STATION_NAMES)

PT_EDGES = PLOT_PT_EDGES
P_EDGES = PLOT_P_EDGES
ETA_EDGES = PLOT_ETA_EDGES
PHI_EDGES = PLOT_PHI_EDGES


def _edges_from_minimum(edges: np.ndarray, minimum: float) -> np.ndarray:
    values = np.asarray(edges, dtype=np.float64)
    trimmed = values[values >= minimum]
    if len(trimmed) == 0 or trimmed[-1] <= minimum:
        raise ValueError(f"plot axis does not extend above {minimum:g}")
    if not np.isclose(trimmed[0], minimum):
        trimmed = np.insert(trimmed, 0, minimum)
    return trimmed


def with_probe_pt_minimum(plots: Sequence[dict], minimum: float | None) -> list[dict]:
    if minimum is None:
        return [dict(plot) for plot in plots]

    adjusted: list[dict] = []
    for source in plots:
        plot = dict(source)
        if plot.get("branch") == "probe_pt" or plot.get("x_branch") == "probe_pt":
            plot["edges"] = _edges_from_minimum(plot["edges"], minimum)
        if plot.get("name") == "probe_pt_eta":
            plot["y_edges"] = _edges_from_minimum(plot["y_edges"], minimum)
        adjusted.append(plot)
    return adjusted

DIRECT_1D_VARIABLES = (
    {
        "key": "probe_pt",
        "mean_key": "pt",
        "output": "probe-pt",
        "branch": "probe_pt",
        "edges": PT_EDGES,
        "xlabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
    },
    {
        "key": "probe_p",
        "mean_key": "p",
        "output": "probe-p",
        "branch": "probe_p",
        "edges": P_EDGES,
        "xlabel": r"Probe Muon $p$ [$\mathrm{GeV}$]",
    },
    {
        "key": "n_pv",
        "mean_key": "n_pv",
        "output": "n-pv",
        "branch": "n_pv",
        "edges": PLOT_PV_EDGES,
        "xlabel": "Number of Primary Vertices",
    },
    {
        "key": "probe_q_over_p",
        "mean_key": "probe_q_over_p",
        "output": "probe-q-over-p",
        "branch": "probe_q_over_p",
        "edges": PLOT_Q_OVER_P_EDGES,
        "xlabel": r"Probe Muon $q/p$ [$\mathrm{GeV}^{-1}$]",
    },
)

PROJECTED_1D_VARIABLES = (
    {
        "key": "probe_eta",
        "mean_key": "eta",
        "output": "probe-eta",
        "source_2d": "probe_eta_phi",
        "axis": 0,
        "edges": ETA_EDGES,
        "xlabel": r"Probe Muon $\eta$",
    },
    {
        "key": "probe_phi",
        "mean_key": "phi",
        "output": "probe-phi",
        "source_2d": "probe_eta_phi",
        "axis": 1,
        "edges": PHI_EDGES,
        "xlabel": r"Probe Muon $\phi$",
    },
)

KINEMATIC_2D_VARIABLES = (
    {
        "name": "probe_pt_eta",
        "output": "probe-pt-eta",
        "xlabel": r"Probe Muon $\eta$",
        "ylabel": r"Probe Muon $p_{T}$ [$\mathrm{GeV}$]",
        "x_edges": ETA_EDGES,
        "y_edges": PT_EDGES,
    },
    {
        "name": "probe_eta_phi",
        "output": "probe-eta-phi",
        "xlabel": r"Probe Muon $\eta$",
        "ylabel": r"Probe Muon $\phi$",
        "x_edges": ETA_EDGES,
        "y_edges": PHI_EDGES,
    },
)

BARREL_STATION_SERIES = (
    ("RB1in", "RB1in"),
    ("RB1out", "RB1out"),
    ("RB2in", "RB2in"),
    ("RB2out", "RB2out"),
    ("RB3", "RB3"),
    ("RB4", "RB4"),
)


def prefixed_2d_plots(output_prefix: str) -> tuple[dict, ...]:
    return tuple(
        {**plot, "output": f"{output_prefix}-{plot['output']}"}
        for plot in KINEMATIC_2D_VARIABLES
    )


def _direct_1d_plot(
    name: str,
    output: str,
    group: str,
    panel_label: str,
    spec: dict,
    value_label: str | None = None,
) -> dict:
    plot = {
        "name": name,
        "output": output,
        "variant": group,
        "edges": spec["edges"],
        "xlabel": spec["xlabel"],
        "region": group,
        "panel_label": panel_label,
    }
    if value_label is None:
        plot["branch"] = spec["branch"]
    else:
        plot["x_branch"] = spec["branch"]
        plot["ylabel"] = value_label
    return plot


def _projected_1d_plot(
    name: str,
    output: str,
    group: str,
    panel_label: str,
    spec: dict,
    value_label: str | None = None,
) -> dict:
    plot = {
        "name": name,
        "output": output,
        "variant": group,
        "source_2d": spec["source_2d"],
        "axis": spec["axis"],
        "edges": spec["edges"],
        "xlabel": spec["xlabel"],
        "region": group,
        "panel_label": panel_label,
    }
    if value_label is not None:
        plot["ylabel"] = value_label
    return plot


def efficiency_1d_plots() -> list[dict]:
    plots: list[dict] = []
    for group in PLOT_GROUPS:
        panel_label = plot_group_label(group)
        for spec in DIRECT_1D_VARIABLES:
            plots.append(_direct_1d_plot(
                f"eff_{spec['key']}_{group}",
                f"eff-{spec['output']}",
                group,
                panel_label,
                spec,
            ))
        for spec in PROJECTED_1D_VARIABLES:
            plots.append(_projected_1d_plot(
                f"eff_{spec['key']}_{group}",
                f"eff-{spec['output']}",
                group,
                panel_label,
                spec,
            ))
    return plots


def mean_cls_1d_plots() -> list[dict]:
    plots: list[dict] = []
    for group in PLOT_GROUPS:
        panel_label = plot_group_label(group)
        for spec in DIRECT_1D_VARIABLES:
            plots.append(_direct_1d_plot(
                f"mean_cls_{spec['mean_key']}_{group}",
                f"mean-cls-{spec['output']}",
                group,
                panel_label,
                spec,
                value_label="Average Cluster Size",
            ))
        for spec in PROJECTED_1D_VARIABLES:
            plots.append(_projected_1d_plot(
                f"mean_cls_{spec['mean_key']}_{group}",
                f"mean-cls-{spec['output']}",
                group,
                panel_label,
                spec,
                value_label="Average Cluster Size",
            ))
    return plots


def trend_plots(output: str, single_region_color: str) -> list[dict]:
    return [
        {
            "output": output,
            "variant": "rb",
            "series": BARREL_STATION_SERIES,
        },
        {
            "output": output,
            "variant": "re-plus",
            "series": tuple((f"RE+{station}", f"RE+{station}") for station in range(1, 5)),
        },
        {
            "output": output,
            "variant": "re-minus",
            "series": tuple((f"RE-{station}", f"RE-{station}") for station in range(1, 5)),
        },
        {
            "output": output,
            "variant": "region",
            "series": (("barrel", "Barrel"), ("endcap", "Endcap")),
        },
        {
            "output": output,
            "variant": "barrel",
            "series": (("barrel", "Barrel"),),
            "panel_label": "Barrel",
            "colors": (single_region_color,),
            "show_legend": False,
        },
        {
            "output": output,
            "variant": "endcap",
            "series": (("endcap", "Endcap"),),
            "panel_label": "Endcap",
            "colors": (single_region_color,),
            "show_legend": False,
        },
    ]
