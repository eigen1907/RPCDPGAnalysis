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

RUN3_COLLECTION_TYPE = (
    "edm::RangeMap<RPCDetId,"
    "edm::OwnVector<RPCRecHit>,"
    "edm::ClonePolicy<RPCRecHit> >"
)

PHASE2_COLLECTION_TYPE = (
    "edm::RangeMap<RPCDetId,"
    "edm::OwnVector<RPCRecHitPhase2,edm::ClonePolicy<RPCRecHitPhase2> >,"
    "edm::ClonePolicy<RPCRecHitPhase2> >"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-i", "--input",
        dest="inputs",
        action="append",
        required=True,
        help="Input RECO ROOT file or directory. Repeat for multiple inputs.",
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
        "--run3-module-label",
        default="rpcRecHits",
        help="EDM module label for RPCRecHitCollection.",
    )
    parser.add_argument(
        "--phase2-module-label",
        default="rpcRecHitsPhase2",
        help="EDM module label for RPCRecHitPhase2 collection.",
    )

    parser.add_argument(
        "--phase2-header",
        default="DataFormats/RPCRecHit/interface/RPCRecHitPhase2.h",
        help="Header path for RPCRecHitPhase2 visible from CMSSW include path.",
    )
    parser.add_argument(
        "--phase2-lib",
        dest="phase2_libs",
        action="append",
        default=[],
        help="Optional ROOT library to load for RPCRecHitPhase2 dictionary. Repeat if needed.",
    )
    parser.add_argument(
        "--skip-phase2",
        action="store_true",
        help="Skip plotting RPCRecHitPhase2.",
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
        "--hide-irpc",
        action="store_true",
        help="Hide iRPC rolls.",
    )

    parser.add_argument(
        "--run3-marker-size",
        type=float,
        default=14.0,
        help="Base marker size for RPCRecHit.",
    )
    parser.add_argument(
        "--phase2-marker-size",
        type=float,
        default=14.0,
        help="Base marker size for RPCRecHitPhase2.",
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


def setup_root(phase2_header: str, phase2_libs: list[str], enable_phase2: bool) -> bool:
    ROOT.gROOT.SetBatch(True)

    ROOT.gSystem.Load("libFWCoreFWLite.so")
    ROOT.gSystem.Load("libDataFormatsFWLite.so")
    ROOT.gSystem.Load("libDataFormatsCommon.so")
    ROOT.gSystem.Load("libDataFormatsMuonDetId.so")
    ROOT.gSystem.Load("libDataFormatsRPCRecHit.so")
    ROOT.FWLiteEnabler.enable()

    for lib in phase2_libs:
        status = ROOT.gSystem.Load(lib)
        print(f"[info] load library {lib}: status={status}")

    run3_decl = ROOT.gInterpreter.Declare(r'''
        #include <cstdint>
        #include <vector>

        #include "DataFormats/Common/interface/RangeMap.h"
        #include "DataFormats/Common/interface/OwnVector.h"
        #include "DataFormats/Common/interface/ClonePolicy.h"
        #include "DataFormats/Common/interface/Wrapper.h"
        #include "DataFormats/MuonDetId/interface/RPCDetId.h"
        #include "DataFormats/RPCRecHit/interface/RPCRecHit.h"
        #include "DataFormats/RPCRecHit/interface/RPCRecHitCollection.h"

        std::vector<uint32_t> rpcRecHitRawIds(const RPCRecHitCollection& coll) {
            std::vector<uint32_t> out;
            out.reserve(coll.size());
            for (const auto& hit : coll) {
                out.push_back(hit.rpcId().rawId());
            }
            return out;
        }
    ''')
    if not run3_decl:
        raise RuntimeError("Failed to declare C++ helper for RPCRecHit.")

    if not enable_phase2:
        return False

    phase2_code = f'''
        #include <cstdint>
        #include <vector>

        #include "DataFormats/Common/interface/RangeMap.h"
        #include "DataFormats/Common/interface/OwnVector.h"
        #include "DataFormats/Common/interface/ClonePolicy.h"
        #include "DataFormats/Common/interface/Wrapper.h"
        #include "DataFormats/MuonDetId/interface/RPCDetId.h"
        #include "{phase2_header}"

        std::vector<uint32_t> rpcRecHitPhase2RawIds(
            const edm::RangeMap<
                RPCDetId,
                edm::OwnVector<RPCRecHitPhase2, edm::ClonePolicy<RPCRecHitPhase2>>,
                edm::ClonePolicy<RPCRecHitPhase2>
            >& coll
        ) {{
            std::vector<uint32_t> out;
            out.reserve(coll.size());
            for (const auto& hit : coll) {{
                out.push_back(hit.rpcId().rawId());
            }}
            return out;
        }}
    '''

    try:
        phase2_decl = ROOT.gInterpreter.Declare(phase2_code)
    except Exception as exc:
        print(f"[warn] failed to declare RPCRecHitPhase2 helper: {exc}")
        return False

    if not phase2_decl:
        print("[warn] failed to declare RPCRecHitPhase2 helper.")
        return False

    return True


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

    n_events = 0
    n_valid = 0
    n_hits_total = 0

    helper = getattr(ROOT, helper_name)

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
            n_hits_total += 1

        if n_events % 100 == 0:
            print(
                f"[info] {tag}: processed={n_events}, valid={n_valid}, accumulated_hits={n_hits_total}"
            )

    print(f"[done] {tag}: processed events = {n_events}")
    print(f"[done] {tag}: valid events with product = {n_valid}")
    print(f"[done] {tag}: accumulated hits = {n_hits_total}")
    print(f"[done] {tag}: active rolls with >=1 hit = {len(counts_by_roll)}")

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
    n_total_hits = int(np.sum(counts))
    return n_active_rolls, n_total_hits


def plot_rechit_roll_points(
    run3_counts_by_roll: pd.Series,
    phase2_counts_by_roll: Optional[pd.Series],
    detector_unit: str,
    roll_list: list[RPCRoll],
    label: str,
    year: Union[int, str],
    com: float,
    lumi: Optional[float],
    output_path: Path,
    run3_marker_size: float = 14.0,
    phase2_marker_size: float = 14.0,
    marker_size_scale: float = 5.0,
    alpha: float = 0.85,
    draw_phase2: bool = True,
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
    if len(x_all) > 0:
        x_range = max(x_all) - min(x_all)
    else:
        x_range = 1.0

    offset = 0.005 * x_range

    run3_active, run3_hits = scatter_roll_counts(
        ax=ax,
        roll_list=roll_list,
        counts_by_roll=run3_counts_by_roll,
        marker="o",
        color="royalblue",
        base_size=run3_marker_size,
        size_scale=marker_size_scale,
        alpha=alpha,
        x_offset=(-offset if draw_phase2 else 0.0),
    )

    phase2_active = 0
    phase2_hits = 0
    if draw_phase2 and phase2_counts_by_roll is not None:
        phase2_active, phase2_hits = scatter_roll_counts(
            ax=ax,
            roll_list=roll_list,
            counts_by_roll=phase2_counts_by_roll,
            marker="s",
            color="crimson",
            base_size=phase2_marker_size,
            size_scale=marker_size_scale,
            alpha=alpha,
            x_offset=offset,
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

    legend_handles = [
        Line2D(
            [0], [0],
            marker="o",
            linestyle="None",
            markersize=6,
            color="royalblue",
            label=f"RPCRecHit: rolls {run3_active}, hits {run3_hits}",
        )
    ]

    if draw_phase2 and phase2_counts_by_roll is not None:
        legend_handles.append(
            Line2D(
                [0], [0],
                marker="s",
                linestyle="None",
                markersize=6,
                color="crimson",
                label=f"RPCRecHitPhase2: rolls {phase2_active}, hits {phase2_hits}",
            )
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


def plot_rechit_detector(
    input_files: list[Path],
    geom_path: Path,
    output_dir: Path,
    run3_module_label: str,
    phase2_module_label: str,
    phase2_enabled: bool,
    year: Union[int, str],
    com: float,
    label: str,
    lumi: Optional[float],
    max_events: Optional[int],
    hide_irpc: bool,
    run3_marker_size: float,
    phase2_marker_size: float,
    marker_size_scale: float,
    alpha: float,
) -> None:
    geom = pd.read_csv(geom_path)

    run3_counts_by_roll = load_counts_generic(
        input_files=input_files,
        geom=geom,
        module_label=run3_module_label,
        collection_type=RUN3_COLLECTION_TYPE,
        helper_name="rpcRecHitRawIds",
        max_events=max_events,
        tag="RPCRecHit",
    )

    phase2_counts_by_roll: Optional[pd.Series] = None
    if phase2_enabled:
        try:
            phase2_counts_by_roll = load_counts_generic(
                input_files=input_files,
                geom=geom,
                module_label=phase2_module_label,
                collection_type=PHASE2_COLLECTION_TYPE,
                helper_name="rpcRecHitPhase2RawIds",
                max_events=max_events,
                tag="RPCRecHitPhase2",
            )
        except Exception as exc:
            print(f"[warn] failed to load RPCRecHitPhase2, will skip overlay: {exc}")
            phase2_counts_by_roll = None

    roll_list = [RPCRoll.from_row(row) for _, row in geom.iterrows()]

    if hide_irpc:
        roll_list = [roll for roll in roll_list if not is_irpc_roll(roll)]

    unit_to_rolls: dict[str, list[RPCRoll]] = defaultdict(list)
    for roll in roll_list:
        unit_to_rolls[roll.id.detector_unit].append(roll)

    output_dir.mkdir(parents=True, exist_ok=True)

    for detector_unit, unit_roll_list in unit_to_rolls.items():
        print(f"[plot] {detector_unit}")
        output_path = output_dir / detector_unit
        plot_rechit_roll_points(
            run3_counts_by_roll=run3_counts_by_roll,
            phase2_counts_by_roll=phase2_counts_by_roll,
            detector_unit=detector_unit,
            roll_list=unit_roll_list,
            label=label,
            year=year,
            com=com,
            lumi=lumi,
            output_path=output_path,
            run3_marker_size=run3_marker_size,
            phase2_marker_size=phase2_marker_size,
            marker_size_scale=marker_size_scale,
            alpha=alpha,
            draw_phase2=(phase2_enabled and phase2_counts_by_roll is not None),
        )


def main() -> None:
    args = parse_args()

    phase2_enabled = not args.skip_phase2
    phase2_ready = setup_root(
        phase2_header=args.phase2_header,
        phase2_libs=args.phase2_libs,
        enable_phase2=phase2_enabled,
    )
    if phase2_enabled and not phase2_ready:
        print("[warn] RPCRecHitPhase2 helper/dictionary is not ready. Phase2 overlay will be skipped.")
        phase2_enabled = False

    input_files = resolve_all_inputs(args.inputs)
    print(f"[info] number of input ROOT files: {len(input_files)}")

    plot_rechit_detector(
        input_files=input_files,
        geom_path=Path(args.geom_path),
        output_dir=Path(args.output_dir),
        run3_module_label=args.run3_module_label,
        phase2_module_label=args.phase2_module_label,
        phase2_enabled=phase2_enabled,
        year=args.year,
        com=args.com,
        label=args.label,
        lumi=args.lumi,
        max_events=args.max_events,
        hide_irpc=args.hide_irpc,
        run3_marker_size=args.run3_marker_size,
        phase2_marker_size=args.phase2_marker_size,
        marker_size_scale=args.marker_size_scale,
        alpha=args.alpha,
    )


if __name__ == "__main__":
    main()