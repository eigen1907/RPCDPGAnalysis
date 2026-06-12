from dataclasses import asdict, dataclass
from functools import cache, cached_property
import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.patches import Polygon


IRPC_ROLL_PREFIXES = ("RE+3_R1_", "RE-3_R1_", "RE+4_R1_", "RE-4_R1_")
RPC_GEOMETRY_KEYS = ("region", "ring", "station", "sector", "layer", "subsector", "roll")


@cache
def get_segment(ring: int, station: int, sector: int, subsector: int) -> int:
    """
    https://github.com/cms-sw/cmssw/blob/CMSSW_13_3_0_pre3/Geometry/RPCGeometry/src/RPCGeomServ.cc#L361-L368
    """
    nsub = 3 if ring == 1 and station > 1 else 6
    return subsector + nsub * (sector - 1)


@cache
def get_roll_name(region: int, ring: int, station: int, sector: int, layer: int,
                  subsector: int, roll: int
) -> str:
    """
    https://github.com/cms-sw/cmssw/blob/CMSSW_13_3_0_pre3/Geometry/RPCGeometry/src/RPCGeomServ.cc#L11-L87
    """
    if region == 0:
        name = f"W{ring:+d}_RB{station}"

        if station <= 2:
            name += "in" if layer == 1 else "out"
        else:
            if sector == 4 and station == 4:
                name += ["--", "-", "+", "++"][subsector - 1]
            elif (station == 3) or (station == 4 and sector not in (4, 9, 11)):
                name += "-" if subsector == 1 else "+"
        name += f"_S{sector:0>2d}_"
        name += ["Backward", "Middle", "Forward"][roll - 1]
    else:
        segment = get_segment(ring, station, sector, subsector)
        name = f"RE{station * region:+d}_R{ring}_CH{segment:0>2d}_"
        name += ["A", "B", "C", "D", "E"][roll - 1]
    return name


def is_irpc_roll_name(roll_name: str) -> bool:
    return roll_name.startswith(IRPC_ROLL_PREFIXES)


@cache
def get_detector_unit(region: int, station: int, layer: int) -> str:
    """
    adapted from https://gitlab.cern.ch/seyang/RPCDPGAnalysis/-/blob/3d71b88e/SegmentAndTrackOnRPC/python/RPCGeom.py#L113-114
    """
    if region == 0:
        suffix = ("in" if layer == 1 else "out") if station <= 2 else ""
        return f"RB{station:d}{suffix}"
    return f"RE{region * station:+d}"


@dataclass(frozen=True)
class RPCDetId:
    region: int
    ring: int
    station: int
    sector: int
    layer: int
    subsector: int
    roll: int

    @classmethod
    def from_obj(cls, obj):
        return cls(region=obj.region, ring=obj.ring, station=obj.station,
                   sector=obj.sector, layer=obj.layer, subsector=obj.subsector,
                   roll=obj.roll)

    @property
    def name(self):
        return get_roll_name(**asdict(self))

    @property
    def detector_unit(self):
        return get_detector_unit(region=self.region, station=self.station,
                                 layer=self.layer)

    @property
    def barrel(self):
        return self.region == 0


@dataclass
class RPCRoll:
    id: RPCDetId
    x: npt.NDArray[np.float64]
    y: npt.NDArray[np.float64]
    z: npt.NDArray[np.float64]

    @classmethod
    def from_row(cls, row: pd.Series):
        x = row[[f'x{idx}' for idx in range(1, 5)]].to_numpy(np.float64)
        y = row[[f'y{idx}' for idx in range(1, 5)]].to_numpy(np.float64)
        z = row[[f'z{idx}' for idx in range(1, 5)]].to_numpy(np.float64)
        det_id = RPCDetId.from_obj(row)
        return cls(det_id, x, y, z)

    @cached_property
    def phi(self) -> npt.NDArray[np.float64]:
        phi = np.arctan2(self.y, self.x)
        phi[phi < 0] += 2 * np.pi
        if abs(phi[0] - phi[2]) > np.pi:
            phi[phi > np.pi] -= 2 * np.pi
        return phi

    @property
    def polygon(self) -> Polygon:
        coordinates = (self.z, self.phi) if self.id.barrel else (self.x, self.y)
        return Polygon(np.stack(coordinates, axis=1), closed=True)

    @property
    def polygon_xlabel(self) -> str:
        return r"$z$ [cm]" if self.id.barrel else r"$x$ [cm]"

    @property
    def polygon_ylabel(self) -> str:
        return r"$\phi$ [radian]" if self.id.barrel else r"$y$ [cm]"

    @property
    def polygon_ymax(self):
        return 7 if self.id.barrel else None
