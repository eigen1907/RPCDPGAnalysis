from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from matplotlib.patches import Polygon

from RPCDPGAnalysis.NanoAODTnP.RPCGeomServ import RPCRoll, is_irpc_roll_name  # type: ignore


PACKAGE_DIR = Path(__file__).resolve().parents[1]
ROLL_BLACKLIST_DIR = PACKAGE_DIR / "data" / "blacklist" / "roll"


def load_roll_blacklist(path: Path | str) -> set[str]:
    names = set()
    with open(path) as stream:
        for raw_line in stream:
            columns = raw_line.split("#", 1)[0].split()
            if columns:
                names.add(columns[1] if len(columns) > 1 else columns[0])
    return names


def roll_mask_names(years: int | str | Sequence[int | str]) -> set[str]:
    if isinstance(years, (int, str)):
        years = (years,)
    masked_names: set[str] = set()
    for year in dict.fromkeys(years):
        path = ROLL_BLACKLIST_DIR / f"blackList{year}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"Roll mask does not exist: {path}")
        masked_names.update(load_roll_blacklist(path))
    return masked_names


def load_roll_geometry(path: Path) -> list[RPCRoll]:
    with path.open(newline="") as stream:
        return [RPCRoll.from_row(row) for row in csv.DictReader(stream)]


@dataclass(frozen=True)
class RollMapSpec:
    name: str
    values_by_roll: Mapping[str, float]
    value_label: str
    cmap: str
    vmin: float
    vmax: float
    excluded_rolls: set[str]


@dataclass(frozen=True)
class RollMap:
    variable_name: str
    detector_unit: str
    rolls: list[RPCRoll]
    values: np.ndarray
    inactive_mask: np.ndarray
    excluded_mask: np.ndarray
    value_label: str
    cmap: str
    vmin: float
    vmax: float

    @property
    def patches(self) -> list[Polygon]:
        return [roll.polygon for roll in self.rolls]


def build_roll_maps(
    geom: Sequence[RPCRoll],
    specs: Sequence[RollMapSpec],
) -> list[RollMap]:
    unit_to_rolls: dict[str, list[RPCRoll]] = {}
    for roll in geom:
        if not is_irpc_roll_name(roll.id.name):
            unit_to_rolls.setdefault(roll.id.detector_unit, []).append(roll)

    maps: list[RollMap] = []
    for detector_unit, rolls in unit_to_rolls.items():
        roll_names = [roll.id.name for roll in rolls]
        for spec in specs:
            values = np.asarray([spec.values_by_roll.get(roll_name, np.nan) for roll_name in roll_names], dtype=np.float64)
            inactive = ~np.isfinite(values)
            excluded = np.asarray([roll_name in spec.excluded_rolls for roll_name in roll_names], dtype=bool)
            maps.append(
                RollMap(
                    variable_name=spec.name,
                    detector_unit=detector_unit,
                    rolls=rolls,
                    values=values,
                    inactive_mask=inactive,
                    excluded_mask=excluded,
                    value_label=spec.value_label,
                    cmap=spec.cmap,
                    vmin=spec.vmin,
                    vmax=spec.vmax,
                )
            )
    return maps
