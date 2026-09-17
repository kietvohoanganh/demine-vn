from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class Terrain:
    elevation_m: np.ndarray
    slope_deg: np.ndarray
    soil_softness: np.ndarray
    is_farmland: np.ndarray
    is_forest: np.ndarray
    dist_village_m: np.ndarray
    dist_road_m: np.ndarray
    dist_river_m: np.ndarray
    village_xy: np.ndarray
    exposure: np.ndarray
    population_count: np.ndarray
    worldcover_class: np.ndarray
    is_builtup: np.ndarray
    soil_clay_pct: np.ndarray
    soil_sand_pct: np.ndarray
    source_mode: str = "public_geospatial_data"

    @property
    def shape(self):
        return self.elevation_m.shape
