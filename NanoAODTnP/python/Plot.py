from __future__ import annotations

from pathlib import Path
from typing import Sequence

from RPCDPGAnalysis.NanoAODTnP.HistIO import load_histograms  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotEfficiency import plot_efficiency  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotPair import plot_pair  # type: ignore
from RPCDPGAnalysis.NanoAODTnP.PlotProbe import plot_probe  # type: ignore
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
    label: str = "Work in Progress",
    ext: str = "png",
    yearly_2d: bool = False,
    roll_maps: bool = False,
) -> list[Path]:
    specs = build_dataset_specs(input_groups, years, lumis)
    histograms_by_spec = {spec: load_histograms(spec) for spec in specs}
    if roll_maps and geom_path is None:
        raise RuntimeError("Roll maps require --geom-path")
    geom = load_roll_geometry(geom_path) if roll_maps and geom_path is not None else None
    run_meta = read_run_meta(run_meta_path)

    common = {
        "specs": specs,
        "histograms_by_spec": histograms_by_spec,
        "output": output,
        "com": com,
        "label": label,
        "ext": ext,
    }
    paths: list[Path] = []

    print("=" * 60, flush=True)
    print("[plot] rpc", flush=True)
    paths.extend(plot_rpc(**common, geom=geom, run_meta=run_meta, draw_yearly_2d=yearly_2d, draw_roll_maps=roll_maps))

    print("=" * 60, flush=True)
    print("[plot] efficiency", flush=True)
    paths.extend(plot_efficiency(**common, geom=geom, run_meta=run_meta, draw_yearly_2d=yearly_2d, draw_roll_maps=roll_maps))

    print("=" * 60, flush=True)
    print("[plot] pair", flush=True)
    paths.extend(plot_pair(**common))

    print("=" * 60, flush=True)
    print("[plot] probe", flush=True)
    paths.extend(plot_probe(**common))
    return paths
