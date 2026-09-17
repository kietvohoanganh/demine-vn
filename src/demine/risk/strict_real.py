"""Xếp hạng ưu tiên chỉ từ các lớp quan sát công khai.

Không dùng UXO ẩn, clearance giả lập hay vị trí tai nạn giả lập.
Kết quả là chỉ số xếp hạng bằng chứng, không phải xác suất còn vật nổ.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd





def gaussian_spread(field: np.ndarray, sigma_cells: float) -> np.ndarray:
    if sigma_cells <= 0:
        return np.asarray(field, float).copy()
    radius=max(1,int(3.0*sigma_cells)); offsets=np.arange(-radius,radius+1,dtype=float)
    kernel=np.exp(-0.5*(offsets/sigma_cells)**2); kernel/=kernel.sum()
    out=np.apply_along_axis(lambda m: np.convolve(m,kernel,mode="same"),0,np.asarray(field,float))
    return np.apply_along_axis(lambda m: np.convolve(m,kernel,mode="same"),1,out)

def neighbourhood_sum(field: np.ndarray, radius_cells: int) -> np.ndarray:
    if radius_cells <= 0:
        return np.asarray(field,float).copy()
    ones=np.ones(2*radius_cells+1,dtype=float)
    out=np.apply_along_axis(lambda m: np.convolve(m,ones,mode="same"),0,np.asarray(field,float))
    return np.apply_along_axis(lambda m: np.convolve(m,ones,mode="same"),1,out)

STRICT_FEATURE_NAMES = [
    "tai_trong_thor_lan_toa",
    "tai_trong_thor_lan_can_500m",
    "mat_do_mission_thor",
    "mat_do_ho_bom_kh9",
    "ho_bom_lan_can_300m",
    "do_cao_copernicus",
    "do_doc_copernicus",
    "clay_soilgrids",
    "sand_soilgrids",
    "dat_canh_tac_worldcover",
    "rung_worldcover",
    "dat_xay_dung_worldcover",
    "khoang_cach_song_osm",
    "khoang_cach_duong_osm",
    "khoang_cach_khu_dan_cu_osm",
    "dan_so_worldpop",
]


@dataclass
class StrictRealTable:
    X: np.ndarray
    names: list[str]
    score: np.ndarray
    weights: dict[str, float]
    components: dict[str, np.ndarray]


def _robust01(x):
    x = np.asarray(x, float)
    finite = np.isfinite(x)
    if not finite.any():
        raise ValueError("Feature không có giá trị hữu hạn.")
    lo, hi = np.nanpercentile(x[finite], [2, 98])
    if hi <= lo:
        out = np.zeros_like(x, dtype=float)
        out[finite] = 0.0
        return out
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def build_strict_real_table(
    grid,
    terrain,
    crater_map,
    missions_csv: str | Path,
    record_kernel_radius_m: float = 180.0,
):
    missions = pd.read_csv(missions_csv)
    required = {
        "record_x",
        "record_y",
        "recorded_tonnage_t",
    }
    missing = required - set(missions.columns)
    if missing:
        raise ValueError(f"THOR mission file thiếu {sorted(missing)}")

    sigma = record_kernel_radius_m / grid.cell
    tonnage = grid.accumulate(
        missions["record_x"].to_numpy(float),
        missions["record_y"].to_numpy(float),
        missions["recorded_tonnage_t"].to_numpy(float),
    )
    mission_count = grid.accumulate(
        missions["record_x"].to_numpy(float),
        missions["record_y"].to_numpy(float),
    )

    tonnage_spread = gaussian_spread(tonnage, sigma)
    tonnage_neigh = neighbourhood_sum(
        tonnage_spread, max(1, int(round(500.0 / grid.cell)))
    )
    mission_density = gaussian_spread(mission_count, sigma)

    crater = np.asarray(crater_map, float)
    crater_neigh = neighbourhood_sum(
        crater, max(1, int(round(300.0 / grid.cell)))
    )

    layers = [
        tonnage_spread,
        tonnage_neigh,
        mission_density,
        crater,
        crater_neigh,
        terrain.elevation_m,
        terrain.slope_deg,
        terrain.soil_clay_pct,
        terrain.soil_sand_pct,
        terrain.is_farmland.astype(float),
        terrain.is_forest.astype(float),
        terrain.is_builtup.astype(float),
        terrain.dist_river_m,
        terrain.dist_road_m,
        terrain.dist_village_m,
        terrain.population_count,
    ]

    X = np.stack([a.ravel() for a in layers], axis=1).astype(np.float32)

    # Trọng số chỉ dùng để xếp hạng. Các giá trị được công khai trong output.
    # Gần đường/khu dân cư làm tăng mức ưu tiên do phơi nhiễm; khoảng cách được đảo chiều.
    weights = {
        "tai_trong_thor_lan_toa": 0.20,
        "tai_trong_thor_lan_can_500m": 0.08,
        "mat_do_mission_thor": 0.08,
        "mat_do_ho_bom_kh9": 0.14,
        "ho_bom_lan_can_300m": 0.08,
        "clay_soilgrids": 0.04,
        "dat_canh_tac_worldcover": 0.05,
        "dat_xay_dung_worldcover": 0.05,
        "gan_song_osm": 0.03,
        "gan_duong_osm": 0.05,
        "gan_khu_dan_cu_osm": 0.08,
        "dan_so_worldpop": 0.12,
    }

    components = {
        "tai_trong_thor_lan_toa": _robust01(tonnage_spread),
        "tai_trong_thor_lan_can_500m": _robust01(tonnage_neigh),
        "mat_do_mission_thor": _robust01(mission_density),
        "mat_do_ho_bom_kh9": _robust01(crater),
        "ho_bom_lan_can_300m": _robust01(crater_neigh),
        "clay_soilgrids": _robust01(terrain.soil_clay_pct),
        "dat_canh_tac_worldcover": terrain.is_farmland.astype(float),
        "dat_xay_dung_worldcover": terrain.is_builtup.astype(float),
        "gan_song_osm": 1.0 - _robust01(terrain.dist_river_m),
        "gan_duong_osm": 1.0 - _robust01(terrain.dist_road_m),
        "gan_khu_dan_cu_osm": 1.0 - _robust01(terrain.dist_village_m),
        "dan_so_worldpop": _robust01(np.log1p(terrain.population_count)),
    }

    score = np.zeros(grid.shape, dtype=float)
    for name, weight in weights.items():
        score += weight * components[name]

    score /= sum(weights.values())
    score = np.clip(score, 0.0, 1.0)

    return StrictRealTable(
        X=X,
        names=list(STRICT_FEATURE_NAMES),
        score=score,
        weights=weights,
        components=components,
    )
