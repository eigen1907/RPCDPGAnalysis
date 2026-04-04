#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

import matplotlib as mpl
mpl.use("agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
import mplhep as mh

import ROOT

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCRoll  # type: ignore


mh.style.use(mh.styles.CMS)

RPC_DIGI_COLLECTION_TYPE = "MuonDigiCollection<RPCDetId,RPCDigi>"
RPC_DIGI_PHASE2_COLLECTION_TYPE = "MuonDigiCollection<RPCDetId,RPCDigiPhase2>"
IRPC_DIGI_COLLECTION_TYPE = "MuonDigiCollection<RPCDetId,IRPCDigi>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        dest="inputs",
        action="append",
        required=True,
        help="Input DIGI/RAW2DIGI ROOT file or directory. Repeat for multiple inputs.",
    )
    parser.add_argument(
        "-g", "--geom",
        dest="geom_path",
        required=True,
        help="Path to geometry csv file.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        required=True,
        help="Output directory for detector plots.",
    )

    parser.add_argument(
        "--rpcdigi-label",
        default="simMuonRPCDigis",
        help="EDM module label for RPCDigi collection.",
    )
    parser.add_argument(
        "--rpcdigi-phase2-label",
        default="simMuonRPCDigisPhase2",
        help="EDM module label for RPCDigiPhase2 collection.",
    )
    parser.add_argument(
        "--irpcdigi-label",
        default="simMuonIRPCDigis",
        help="EDM module label for IRPCDigi collection.",
    )

    parser.add_argument(
        "--phase2-header",
        default="DataFormats/RPCDigi/interface/RPCDigiPhase2.h",
        help="Header path for RPCDigiPhase2 visible from CMSSW include path.",
    )
    parser.add_argument(
        "--irpc-header",
        default="DataFormats/RPCDigi/interface/IRPCDigi.h",
        help="Header path for IRPCDigi visible from CMSSW include path.",
    )
    parser.add_argument(
        "--extra-lib",
        dest="extra_libs",
        action="append",
        default=[],
        help="Optional ROOT library to load. Repeat if needed.",
    )

    parser.add_argument(
        "--skip-rpcdigi-phase2",
        action="store_true",
        help="Skip plotting RPCDigiPhase2.",
    )
    parser.add_argument(
        "--skip-irpcdigi",
        action="store_true",
        help="Skip plotting IRPCDigi.",
    )

    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Maximum number of events to process.",
    )
    parser.add_argument(
        "--year",
        default="2024",
        help="Year label for mplhep CMS label.",
    )
    parser.add_argument(
        "--lumi",
        type=float,
        default=None,
        help="Luminosity in fb^-1.",
    )
    parser.add_argument(
        "--com",
        type=float,
        default=13.6,
        help="Center-of-mass energy in TeV.",
    )
    parser.add_argument(
        "--label",
        default="Private Work",
        help="Left label for mplhep CMS label.",
    )
    parser.add_argument(
        "--hide-irpc-rolls",
        action="store_true",
        help="Hide iRPC rolls from detector layout itself.",
    )

    parser.add_argument(
        "--rpcdigi-marker-size",
        type=float,
        default=14.0,
        help="Base marker size for RPCDigi.",
    )
    parser.add_argument(
        "--rpcdigi-phase2-marker-size",
        type=float,
        default=14.0,
        help="Base marker size for RPCDigiPhase2.",
    )
    parser.add_argument(
        "--irpcdigi-marker-size",
        type=float,
        default=14.0,
        help="Base marker size for IRPCDigi.",
    )
    parser.add_argument(
        "--marker-size-scale",
        type=float,
        default=5.0,
        help="Additional marker size scale using sqrt(hit_count).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.85,
        help="Marker alpha.",
    )

    return parser.parse_args()


def setup_root(
    phase2_header: str,
    irpc_header: str,
    extra_libs: list[str],
    enable_phase2: bool,
    enable_irpc: bool,
) -> tuple[bool, bool]:
    ROOT.gROOT.SetBatch(True)

    ROOT.gSystem.Load("libFWCoreFWLite.so")
    ROOT.gSystem.Load("libDataFormatsFWLite.so")
    ROOT.gSystem.Load("libDataFormatsMuonDetId.so")
    ROOT.gSystem.Load("libDataFormatsRPCDigi.so")
    ROOT.FWLiteEnabler.enable()

    for lib in extra_libs:
        status = ROOT.gSystem.Load(lib)
        print(f"[info] load library {lib}: status={status}")

    base_decl = ROOT.gInterpreter.Declare(r'''
        #include <cstdint>
        #include <vector>

        #include "DataFormats/MuonData/interface/MuonDigiCollection.h"
        #include "DataFormats/MuonDetId/interface/RPCDetId.h"
        #include "DataFormats/RPCDigi/interface/RPCDigi.h"
        #include "DataFormats/RPCDigi/interface/RPCDigiCollection.h"

        std::vector<uint32_t> rpcDigiRawIds(const RPCDigiCollection& coll) {
            std::vector<uint32_t> out;
            for (auto it = coll.begin(); it != coll.end(); ++it) {
                auto item = *it;
                const auto& detId = item.first;
                auto begin = item.second.first;
                auto end = item.second.second;
                for (auto digiIt = begin; digiIt != end; ++digiIt) {
                    out.push_back(detId.rawId());
                }
            }
            return out;
        }
    ''')
    if not base_decl:
        raise RuntimeError("Failed to declare C++ helper for RPCDigi.")

    phase2_ready = False
    if enable_phase2:
        phase2_code = f'''
            #include <cstdint>
            #include <vector>

            #include "DataFormats/MuonData/interface/MuonDigiCollection.h"
            #include "DataFormats/MuonDetId/interface/RPCDetId.h"
            #include "{phase2_header}"

            std::vector<uint32_t> rpcDigiPhase2RawIds(
                const MuonDigiCollection<RPCDetId, RPCDigiPhase2>& coll
            ) {{
                std::vector<uint32_t> out;
                for (auto it = coll.begin(); it != coll.end(); ++it) {{
                    auto item = *it;
                    const auto& detId = item.first;
                    auto begin = item.second.first;
                    auto end = item.second.second;
                    for (auto digiIt = begin; digiIt != end; ++digiIt) {{
                        out.push_back(detId.rawId());
                    }}
                }}
                return out;
            }}
        '''
        try:
            phase2_ready = bool(ROOT.gInterpreter.Declare(phase2_code))
        except Exception as exc:
            print(f"[warn] failed to declare RPCDigiPhase2 helper: {exc}")
            phase2_ready = False

        if not phase2_ready:
            print("[warn] RPCDigiPhase2 helper is not ready. RPCDigiPhase2 overlay will be skipped.")

    irpc_ready = False
    if enable_irpc:
        irpc_code = f'''
            #include <cstdint>
            #include <vector>

            #include "DataFormats/MuonData/interface/MuonDigiCollection.h"
            #include "DataFormats/MuonDetId/interface/RPCDetId.h"
            #include "{irpc_header}"

            std::vector<uint32_t> irpcDigiRawIds(
                const MuonDigiCollection<RPCDetId, IRPCDigi>& coll
            ) {{
                std::vector<uint32_t> out;
                for (auto it = coll.begin(); it != coll.end(); ++it) {{
                    auto item = *it;
                    const auto& detId = item.first;
                    auto begin = item.second.first;
                    auto end = item.second.second;
                    for (auto digiIt = begin; digiIt != end; ++digiIt) {{
                        out.push_back(detId.rawId());
                    }}
                }}
                return out;
            }}
        '''
        try:
            irpc_ready = bool(ROOT.gInterpreter.Declare(irpc_code))
        except Exception as exc:
            print(f"[warn] failed to declare IRPCDigi helper: {exc}")
            irpc_ready = False

        if not irpc_ready:
            print("[warn] IRPCDigi helper is not ready. IRPCDigi overlay will be skipped.")

    return phase2_ready, irpc_ready


def _resolve_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix != ".root":
            raise ValueError(f"Expected a ROOT file, got: {input_path}")
        return [input_path]

    if input_path.is_dir():
        files = sorted(path for path in input_path.rglob("*.root") if path.is_file())
        if len(files) == 0:
            raise FileNotFoundError(f"No ROOT files found under: {input_path}")
        return files

    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def resolve_all_inputs(inputs: list[str]) -> list[Path]:
    all_files: list[Path] = []
    for each in inputs:
        all_files.extend(_resolve_input_files(Path(each)))
    return sorted(set(all_files))


def parse_module_label(label: str):
    parts = label.split(":")
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return (parts[0], parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid module label: {label}")


def polygon_centroid(polygon) -> tuple[float, float]:
    xy = polygon.get_xy()

    if len(xy) < 3:
        return float(np.mean(xy[:, 0])), float(np.mean(xy[:, 1]))

    x = xy[:, 0]
    y = xy[:, 1]

    x0 = x[:-1]
    y0 = y[:-1]
    x1 = x[1:]
    y1 = y[1:]

    cross = x0 * y1 - x1 * y0
    area2 = np.sum(cross)

    if np.isclose(area2, 0.0):
        return float(np.mean(x[:-1])), float(np.mean(y[:-1]))

    cx = np.sum((x0 + x1) * cross) / (3.0 * area2)
    cy = np.sum((y0 + y1) * cross) / (3.0 * area2)

    return float(cx), float(cy)


def build_geom_roll_name_map(
    geom: pd.DataFrame,
) -> dict[tuple[int, int, int, int, int, int, int], str]:
    key_cols = ["region", "ring", "station", "sector", "layer", "subsector", "roll"]
    geom_key = geom[key_cols + ["roll_name"]].drop_duplicates()

    out: dict[tuple[int, int, int, int, int, int, int], str] = {}
    for _, row in geom_key.iterrows():
        key = (
            int(row["region"]),
            int(row["ring"]),
            int(row["station"]),
            int(row["sector"]),
            int(row["layer"]),
            int(row["subsector"]),
            int(row["roll"]),
        )
        out[key] = str(row["roll_name"])
    return out


def is_irpc_roll(roll: RPCRoll) -> bool:
    return (
        abs(int(roll.id.region)) == 1
        and int(roll.id.ring) == 1
        and int(roll.id.station) in (3, 4)
    )


def load_counts_generic(
    input_files: list[Path],
    geom: pd.DataFrame,
    module_label: str,
    collection_type: str,
    helper_name: str,
    max_events: Optional[int] = None,
    tag: str = "collection",
) -> pd.Series:
    from DataFormats.FWLite import Events, Handle

    try:
        handle = Handle(collection_type)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to create Handle for {tag} with type:\n{collection_type}\n"
            f"Original error: {exc}"
        ) from exc

    label = parse_module_label(module_label)
    roll_name_map = build_geom_roll_name_map(geom)
    counts_by_roll: dict[str, int] = defaultdict(int)

    events = Events([str(path) for path in input_files])
    helper = getattr(ROOT, helper_name)

    n_events = 0
    n_valid = 0
    n_digis_total = 0

    for event in events:
        if max_events is not None and n_events >= max_events:
            break

        event.getByLabel(label, handle)
        n_events += 1

        if not handle.isValid():
            if n_events <= 3:
                print(f"[warn] invalid handle for {tag}, event={n_events}, label={module_label}")
            continue

        n_valid += 1
        product = handle.product()
        raw_ids = helper(product)

        for raw_id in raw_ids:
            rpc_id = ROOT.RPCDetId(int(raw_id))
            key = (
                int(rpc_id.region()),
                int(rpc_id.ring()),
                int(rpc_id.station()),
                int(rpc_id.sector()),
                int(rpc_id.layer()),
                int(rpc_id.subsector()),
                int(rpc_id.roll()),
            )

            roll_name = roll_name_map.get(key)
            if roll_name is None:
                continue

            counts_by_roll[roll_name] += 1
            n_digis_total += 1

        if n_events % 100 == 0:
            print(
                f"[info] {tag}: processed={n_events}, valid={n_valid}, accumulated_digis={n_digis_total}"
            )

    print(f"[done] {tag}: processed events = {n_events}")
    print(f"[done] {tag}: valid events with product = {n_valid}")
    print(f"[done] {tag}: accumulated digis = {n_digis_total}")
    print(f"[done] {tag}: active rolls with >=1 digi = {len(counts_by_roll)}")

    return pd.Series(counts_by_roll, dtype=np.int64)


def draw_roll_layout(
    roll_list: list[RPCRoll],
    ax: Optional[plt.Axes] = None,
    edgecolor: str = "black",
    linewidth: float = 1.0,
    facecolor: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 0.0),
) -> None:
    ax = ax or plt.gca()

    patches = [roll.polygon for roll in roll_list]
    collection = PatchCollection(patches)
    collection.set_facecolor(facecolor)
    collection.set_edgecolor(edgecolor)
    collection.set_linewidth(linewidth)

    ax.add_collection(collection)
    ax.autoscale_view()


def scatter_roll_counts(
    ax: plt.Axes,
    roll_list: list[RPCRoll],
    counts_by_roll: pd.Series,
    marker: str,
    color: str,
    base_size: float,
    size_scale: float,
    alpha: float,
    x_offset: float,
) -> tuple[int, int]:
    name_list = [roll.id.name for roll in roll_list]
    counts = counts_by_roll.reindex(name_list, fill_value=0).to_numpy(dtype=np.int64)

    x_points: list[float] = []
    y_points: list[float] = []
    sizes: list[float] = []

    for roll, count in zip(roll_list, counts):
        if count < 1:
            continue

        cx, cy = polygon_centroid(roll.polygon)
        x_points.append(cx + x_offset)
        y_points.append(cy)
        sizes.append(base_size + size_scale * np.sqrt(float(count)))

    if len(x_points) > 0:
        ax.scatter(
            x_points,
            y_points,
            s=np.asarray(sizes, dtype=np.float64),
            marker=marker,
            c=color,
            linewidths=0.0,
            alpha=alpha,
        )

    n_active_rolls = int(np.count_nonzero(counts > 0))
    n_total_digis = int(np.sum(counts))
    return n_active_rolls, n_total_digis


def plot_digi_roll_points(
    rpcdigi_counts_by_roll: pd.Series,
    rpcdigi_phase2_counts_by_roll: Optional[pd.Series],
    irpcdigi_counts_by_roll: Optional[pd.Series],
    detector_unit: str,
    roll_list: list[RPCRoll],
    label: str,
    year: Union[int, str],
    com: float,
    lumi: Optional[float],
    output_path: Path,
    rpcdigi_marker_size: float = 14.0,
    rpcdigi_phase2_marker_size: float = 14.0,
    irpcdigi_marker_size: float = 14.0,
    marker_size_scale: float = 5.0,
    alpha: float = 0.85,
    draw_phase2: bool = True,
    draw_irpc: bool = True,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 9))

    draw_roll_layout(
        roll_list=roll_list,
        ax=ax,
        edgecolor="black",
        linewidth=1.0,
    )

    x_all = []
    for roll in roll_list:
        xy = roll.polygon.get_xy()
        x_all.extend(xy[:, 0].tolist())

    x_range = (max(x_all) - min(x_all)) if len(x_all) > 0 else 1.0
    base_offset = 0.005 * x_range

    offsets = []
    if draw_phase2 and draw_irpc:
        offsets = [-base_offset, 0.0, base_offset]
    elif draw_phase2 and not draw_irpc:
        offsets = [-0.5 * base_offset, 0.5 * base_offset]
    elif (not draw_phase2) and draw_irpc:
        offsets = [-0.5 * base_offset, 0.5 * base_offset]
    else:
        offsets = [0.0]

    legend_handles = []

    if draw_phase2 and draw_irpc:
        rpc_offset, phase2_offset, irpc_offset = offsets

        rpc_active, rpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_counts_by_roll,
            marker="o",
            color="royalblue",
            base_size=rpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=rpc_offset,
        )
        phase2_active, phase2_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_phase2_counts_by_roll if rpcdigi_phase2_counts_by_roll is not None else pd.Series(dtype=np.int64),
            marker="s",
            color="crimson",
            base_size=rpcdigi_phase2_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=phase2_offset,
        )
        irpc_active, irpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=irpcdigi_counts_by_roll if irpcdigi_counts_by_roll is not None else pd.Series(dtype=np.int64),
            marker="^",
            color="darkgreen",
            base_size=irpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=irpc_offset,
        )

        legend_handles.extend([
            Line2D([0], [0], marker="o", linestyle="None", markersize=6, color="royalblue",
                   label=f"RPCDigi: rolls {rpc_active}, digis {rpc_total}"),
            Line2D([0], [0], marker="s", linestyle="None", markersize=6, color="crimson",
                   label=f"RPCDigiPhase2: rolls {phase2_active}, digis {phase2_total}"),
            Line2D([0], [0], marker="^", linestyle="None", markersize=6, color="darkgreen",
                   label=f"IRPCDigi: rolls {irpc_active}, digis {irpc_total}"),
        ])

    elif draw_phase2 and not draw_irpc:
        rpc_offset, phase2_offset = offsets

        rpc_active, rpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_counts_by_roll,
            marker="o",
            color="royalblue",
            base_size=rpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=rpc_offset,
        )
        phase2_active, phase2_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_phase2_counts_by_roll if rpcdigi_phase2_counts_by_roll is not None else pd.Series(dtype=np.int64),
            marker="s",
            color="crimson",
            base_size=rpcdigi_phase2_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=phase2_offset,
        )

        legend_handles.extend([
            Line2D([0], [0], marker="o", linestyle="None", markersize=6, color="royalblue",
                   label=f"RPCDigi: rolls {rpc_active}, digis {rpc_total}"),
            Line2D([0], [0], marker="s", linestyle="None", markersize=6, color="crimson",
                   label=f"RPCDigiPhase2: rolls {phase2_active}, digis {phase2_total}"),
        ])

    elif (not draw_phase2) and draw_irpc:
        rpc_offset, irpc_offset = offsets

        rpc_active, rpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_counts_by_roll,
            marker="o",
            color="royalblue",
            base_size=rpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=rpc_offset,
        )
        irpc_active, irpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=irpcdigi_counts_by_roll if irpcdigi_counts_by_roll is not None else pd.Series(dtype=np.int64),
            marker="^",
            color="darkgreen",
            base_size=irpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=irpc_offset,
        )

        legend_handles.extend([
            Line2D([0], [0], marker="o", linestyle="None", markersize=6, color="royalblue",
                   label=f"RPCDigi: rolls {rpc_active}, digis {rpc_total}"),
            Line2D([0], [0], marker="^", linestyle="None", markersize=6, color="darkgreen",
                   label=f"IRPCDigi: rolls {irpc_active}, digis {irpc_total}"),
        ])

    else:
        rpc_active, rpc_total = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=rpcdigi_counts_by_roll,
            marker="o",
            color="royalblue",
            base_size=rpcdigi_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=0.0,
        )

        legend_handles.append(
            Line2D([0], [0], marker="o", linestyle="None", markersize=6, color="royalblue",
                   label=f"RPCDigi: rolls {rpc_active}, digis {rpc_total}")
        )

    xlabel = roll_list[0].polygon_xlabel
    ylabel = roll_list[0].polygon_ylabel
    ymax = roll_list[0].polygon_ymax

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(None, ymax)

    ax.annotate(
        detector_unit,
        (0.05, 0.925),
        weight="bold",
        xycoords="axes fraction",
    )

    ax.legend(
        handles=legend_handles,
        frameon=False,
        loc="best",
        handlelength=1.0,
        handletextpad=0.4,
        borderaxespad=0.5,
    )

    mh.cms.label(
        ax=ax,
        llabel=label,
        lumi=lumi,
        year=year,
        com=com,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path.with_suffix(".png"))
    plt.close(fig)


def plot_digi_detector(
    input_files: list[Path],
    geom_path: Path,
    output_dir: Path,
    rpcdigi_label: str,
    rpcdigi_phase2_label: str,
    irpcdigi_label: str,
    draw_phase2: bool,
    draw_irpc: bool,
    year: Union[int, str],
    com: float,
    label: str,
    lumi: Optional[float],
    max_events: Optional[int],
    hide_irpc_rolls: bool,
    rpcdigi_marker_size: float,
    rpcdigi_phase2_marker_size: float,
    irpcdigi_marker_size: float,
    marker_size_scale: float,
    alpha: float,
) -> None:
    geom = pd.read_csv(geom_path)

    rpcdigi_counts_by_roll = load_counts_generic(
        input_files=input_files,
        geom=geom,
        module_label=rpcdigi_label,
        collection_type=RPC_DIGI_COLLECTION_TYPE,
        helper_name="rpcDigiRawIds",
        max_events=max_events,
        tag="RPCDigi",
    )

    rpcdigi_phase2_counts_by_roll: Optional[pd.Series] = None
    if draw_phase2:
        try:
            rpcdigi_phase2_counts_by_roll = load_counts_generic(
                input_files=input_files,
                geom=geom,
                module_label=rpcdigi_phase2_label,
                collection_type=RPC_DIGI_PHASE2_COLLECTION_TYPE,
                helper_name="rpcDigiPhase2RawIds",
                max_events=max_events,
                tag="RPCDigiPhase2",
            )
        except Exception as exc:
            print(f"[warn] failed to load RPCDigiPhase2, will skip overlay: {exc}")
            rpcdigi_phase2_counts_by_roll = None
            draw_phase2 = False

    irpcdigi_counts_by_roll: Optional[pd.Series] = None
    if draw_irpc:
        try:
            irpcdigi_counts_by_roll = load_counts_generic(
                input_files=input_files,
                geom=geom,
                module_label=irpcdigi_label,
                collection_type=IRPC_DIGI_COLLECTION_TYPE,
                helper_name="irpcDigiRawIds",
                max_events=max_events,
                tag="IRPCDigi",
            )
        except Exception as exc:
            print(f"[warn] failed to load IRPCDigi, will skip overlay: {exc}")
            irpcdigi_counts_by_roll = None
            draw_irpc = False

    roll_list = [RPCRoll.from_row(row) for _, row in geom.iterrows()]

    if hide_irpc_rolls:
        roll_list = [roll for roll in roll_list if not is_irpc_roll(roll)]

    unit_to_rolls: dict[str, list[RPCRoll]] = defaultdict(list)
    for roll in roll_list:
        unit_to_rolls[roll.id.detector_unit].append(roll)

    output_dir.mkdir(parents=True, exist_ok=True)

    for detector_unit, unit_roll_list in unit_to_rolls.items():
        print(f"[plot] {detector_unit}")
        output_path = output_dir / detector_unit
        plot_digi_roll_points(
            rpcdigi_counts_by_roll=rpcdigi_counts_by_roll,
            rpcdigi_phase2_counts_by_roll=rpcdigi_phase2_counts_by_roll,
            irpcdigi_counts_by_roll=irpcdigi_counts_by_roll,
            detector_unit=detector_unit,
            roll_list=unit_roll_list,
            label=label,
            year=year,
            com=com,
            lumi=lumi,
            output_path=output_path,
            rpcdigi_marker_size=rpcdigi_marker_size,
            rpcdigi_phase2_marker_size=rpcdigi_phase2_marker_size,
            irpcdigi_marker_size=irpcdigi_marker_size,
            marker_size_scale=marker_size_scale,
            alpha=alpha,
            draw_phase2=draw_phase2,
            draw_irpc=draw_irpc,
        )


def main() -> None:
    args = parse_args()

    enable_phase2 = not args.skip_rpcdigi_phase2
    enable_irpc = not args.skip_irpcdigi

    phase2_ready, irpc_ready = setup_root(
        phase2_header=args.phase2_header,
        irpc_header=args.irpc_header,
        extra_libs=args.extra_libs,
        enable_phase2=enable_phase2,
        enable_irpc=enable_irpc,
    )

    if enable_phase2 and not phase2_ready:
        enable_phase2 = False
    if enable_irpc and not irpc_ready:
        enable_irpc = False

    input_files = resolve_all_inputs(args.inputs)
    print(f"[info] number of input ROOT files: {len(input_files)}")

    plot_digi_detector(
        input_files=input_files,
        geom_path=Path(args.geom_path),
        output_dir=Path(args.output_dir),
        rpcdigi_label=args.rpcdigi_label,
        rpcdigi_phase2_label=args.rpcdigi_phase2_label,
        irpcdigi_label=args.irpcdigi_label,
        draw_phase2=enable_phase2,
        draw_irpc=enable_irpc,
        year=args.year,
        com=args.com,
        label=args.label,
        lumi=args.lumi,
        max_events=args.max_events,
        hide_irpc_rolls=args.hide_irpc_rolls,
        rpcdigi_marker_size=args.rpcdigi_marker_size,
        rpcdigi_phase2_marker_size=args.rpcdigi_phase2_marker_size,
        irpcdigi_marker_size=args.irpcdigi_marker_size,
        marker_size_scale=args.marker_size_scale,
        alpha=args.alpha,
    )


if __name__ == "__main__":
    main()