"""Nạp các lớp nền địa lý đã lấy từ nguồn công khai.

Mô-đun này không tự sinh địa hình, đường, sông, khu dân cư hay lớp phủ.
Nếu thiếu một lớp bắt buộc, chương trình dừng thay vì tự tạo dữ liệu thay thế.
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np

from .strict_types import Terrain


REQUIRED_ARRAYS = (
    "elevation_m",
    "slope_deg",
    "soil_softness",
    "soil_clay_pct",
    "soil_sand_pct",
    "is_farmland",
    "is_forest",
    "is_builtup",
    "dist_settlement_m",
    "dist_road_m",
    "dist_river_m",
    "population_count",
    "exposure",
    "worldcover_class",
    "settlement_xy",
)


def load_real_terrain(npz_path: str | Path, provenance_path: str | Path | None = None):
    path = Path(npz_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có {path}. Chạy scripts/fetch_real_geospatial.py trước."
        )

    with np.load(path, allow_pickle=False) as data:
        missing = [name for name in REQUIRED_ARRAYS if name not in data.files]
        if missing:
            raise ValueError(
                "Gói địa lý thực thiếu lớp: " + ", ".join(missing)
            )

        arrays = {name: data[name] for name in REQUIRED_ARRAYS}

    shape = arrays["elevation_m"].shape
    for name, arr in arrays.items():
        if name == "settlement_xy":
            continue
        if arr.shape != shape:
            raise ValueError(
                f"Lớp {name} có shape {arr.shape}, khác shape chuẩn {shape}"
            )

    terrain = Terrain(
        elevation_m=arrays["elevation_m"].astype(float),
        slope_deg=arrays["slope_deg"].astype(float),
        soil_softness=arrays["soil_softness"].astype(float),
        is_farmland=arrays["is_farmland"].astype(bool),
        is_forest=arrays["is_forest"].astype(bool),
        dist_village_m=arrays["dist_settlement_m"].astype(float),
        dist_road_m=arrays["dist_road_m"].astype(float),
        dist_river_m=arrays["dist_river_m"].astype(float),
        village_xy=arrays["settlement_xy"].astype(float),
        exposure=arrays["exposure"].astype(float),
        population_count=arrays["population_count"].astype(float),
        worldcover_class=arrays["worldcover_class"].astype(np.int16),
        is_builtup=arrays["is_builtup"].astype(bool),
        soil_clay_pct=arrays["soil_clay_pct"].astype(float),
        soil_sand_pct=arrays["soil_sand_pct"].astype(float),
        source_mode="public_geospatial_data",
    )

    provenance = {}
    if provenance_path:
        p = Path(provenance_path)
        if p.exists():
            provenance = json.loads(p.read_text(encoding="utf-8"))

    return terrain, provenance
