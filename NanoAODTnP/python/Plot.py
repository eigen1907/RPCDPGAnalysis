from __future__ import annotations

from pathlib import Path
from typing import Sequence

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_histograms  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotEfficiency import plot_efficiency  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotPair import plot_pair  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotRPC import plot_rpc  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotUtils import build_dataset_specs  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadGeoMeta import load_roll_geometry  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.ReadRunMeta import read_run_meta  # type: ignore


def plot_all(
    input_groups: Sequence[Sequence[Path]],
    years: Sequence[int],
    output: Path,
    lumis: Sequence[float],
    geom_path: Path | None,
    run_meta_path: Path,
    com: float = 13.6,
    label: str = "Preliminary",
    ext: str = "png",
    yearly_2d: bool = False,
    efficiency_maps: bool = False,
    roll_maps: bool = False,
    show_excluded_rolls: bool = True,
    probe_pt_gt15: bool = True,
) -> list[Path]:
    specs = build_dataset_specs(input_groups, years, lumis)
    histograms_by_spec = {spec: load_histograms(spec) for spec in specs}
    needs_geom = efficiency_maps or roll_maps
    if needs_geom and geom_path is None:
        raise RuntimeError("Roll maps require --geom-path")
    geom = load_roll_geometry(geom_path) if needs_geom and geom_path is not None else None
    run_meta = read_run_meta(run_meta_path)

    common = {
        "specs": specs,
        "histograms_by_spec": histograms_by_spec,
        "output": output,
        "com": com,
        "label": label,
        "ext": ext,
        "probe_pt_minimum": 15.0 if probe_pt_gt15 else None,
    }
    paths: list[Path] = []

    print("=" * 60, flush=True)
    print("[plot] rpc", flush=True)
    paths.extend(
        plot_rpc(
            **common,
            geom=geom,
            run_meta=run_meta,
            draw_yearly_2d=yearly_2d,
            draw_roll_maps=roll_maps,
            show_excluded_rolls=show_excluded_rolls,
        )
    )

    print("=" * 60, flush=True)
    print("[plot] efficiency", flush=True)
    paths.extend(
        plot_efficiency(
            **common,
            geom=geom,
            run_meta=run_meta,
            draw_yearly_2d=yearly_2d,
            draw_roll_maps=efficiency_maps,
            show_excluded_rolls=show_excluded_rolls,
        )
    )

    print("=" * 60, flush=True)
    print("[plot] pair", flush=True)
    paths.extend(plot_pair(**common))
    return paths
