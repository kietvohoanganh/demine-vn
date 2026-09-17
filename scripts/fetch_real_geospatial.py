#!/usr/bin/env python3
"""Tải và chuẩn hoá các lớp địa lý cho vùng nghiên cứu Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn.

Nguồn:
- Copernicus DEM GLO-30: cao độ
- ESA WorldCover 2021: lớp phủ bề mặt
- OpenStreetMap / Overpass: đường, sông và điểm dân cư
- WorldPop 2020: dân số 100 m
- SoilGrids: clay và sand tầng 0–5 cm

Không có fallback synthetic. Bất kỳ nguồn bắt buộc nào không tải được sẽ làm
script dừng với thông báo cụ thể.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demine.config import GridConfig
from demine.data.geo import Grid

EARTH_RADIUS_M = 6_371_000.0

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2015_2030/"
    "R2024B/2020/VNM/v1/100m/constrained/"
    "vnm_pop_2020_CN_100m_R2024B_v1.tif"
)
SOIL_CLAY_URL = (
    "https://files.isric.org/soilgrids/latest/data/clay/"
    "clay_0-5cm_mean.vrt"
)
SOIL_SAND_URL = (
    "https://files.isric.org/soilgrids/latest/data/sand/"
    "sand_0-5cm_mean.vrt"
)
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def _bbox(grid: Grid):
    lon0, lat0 = grid.xy_to_lonlat(0.0, 0.0)
    lon1, lat1 = grid.xy_to_lonlat(grid.width_m, grid.height_m)
    return [float(lon0), float(lat0), float(lon1), float(lat1)]


def _grid_points(grid: Grid):
    lon, lat = grid.cell_centers_lonlat()
    return np.asarray(lon, float), np.asarray(lat, float)


def _sample_one_raster(href, lons, lats):
    import rasterio
    from rasterio.warp import transform

    env_opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.vrt",
    }
    with rasterio.Env(**env_opts):
        with rasterio.open(href) as ds:
            xs, ys = transform("EPSG:4326", ds.crs, lons.tolist(), lats.tolist())
            vals = np.array(
                [v[0] for v in ds.sample(zip(xs, ys), masked=True)],
                dtype=float,
            )
            nodata = ds.nodata
            if nodata is not None:
                vals[np.isclose(vals, nodata, equal_nan=False)] = np.nan
            return vals


def _sample_assets(hrefs, lons, lats):
    out = np.full(lons.shape, np.nan, dtype=float)
    errors = []
    for href in hrefs:
        try:
            vals = _sample_one_raster(href, lons, lats)
            fill = np.isnan(out) & np.isfinite(vals)
            out[fill] = vals[fill]
            if np.isfinite(out).all():
                break
        except Exception as exc:
            errors.append(str(exc))
    if not np.isfinite(out).all():
        n = int((~np.isfinite(out)).sum())
        raise RuntimeError(
            f"Còn {n} ô không lấy được giá trị raster. "
            + (" | ".join(errors[-3:]) if errors else "")
        )
    return out


def _stac_assets(collection, asset_name, bbox):
    from pystac_client import Client
    import planetary_computer

    cat = Client.open(STAC_URL)
    search = cat.search(collections=[collection], bbox=bbox)
    items = list(search.items())
    if not items:
        raise RuntimeError(
            f"STAC không trả item nào cho {collection} trong bbox {bbox}"
        )

    signed = [planetary_computer.sign(item) for item in items]
    hrefs = []
    for item in signed:
        if asset_name not in item.assets:
            raise KeyError(
                f"{collection}/{item.id} không có asset {asset_name}; "
                f"assets={list(item.assets)}"
            )
        hrefs.append(item.assets[asset_name].href)
    return hrefs, [i.id for i in items]


def _validate_raster(path: Path):
    """Read every block so a truncated TIFF is never accepted as cached data."""
    import rasterio
    with rasterio.open(path) as ds:
        if not ds.crs or ds.count < 1 or ds.width < 1 or ds.height < 1:
            raise ValueError(f"Raster không hợp lệ: {path}")
        for _, window in ds.block_windows(1):
            ds.read(1, window=window)


def _download(url, path: Path):
    if path.exists():
        try:
            _validate_raster(path)
            return
        except (OSError, ValueError):
            print(f"Tải lại raster bị lỗi: {path.name}", flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=(20, 180),
                          headers={"Accept-Encoding": "identity"}) as r:
            r.raise_for_status()
            expected = r.headers.get("Content-Length")
            received = 0
            with partial.open("wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        received += len(chunk)
            if expected is not None and received != int(expected):
                raise OSError(f"Tải thiếu dữ liệu: {received}/{expected} byte")
        _validate_raster(partial)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def _overpass_query(bbox):
    west, south, east, north = bbox
    b = f"{south},{west},{north},{east}"
    return f"""
[out:json][timeout:120];
(
  way["highway"]({b});
  way["waterway"~"river|stream|canal|ditch|drain"]({b});
  node["place"~"city|town|village|hamlet|suburb"]({b});
  way["landuse"="residential"]({b});
);
out geom;
"""


def _fetch_overpass(bbox, cache_path: Path):
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    query = _overpass_query(bbox)
    last = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                timeout=180,
                headers={"User-Agent": "Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn research project"},
            )
            r.raise_for_status()
            obj = r.json()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(obj, ensure_ascii=False),
                encoding="utf-8",
            )
            return obj
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise RuntimeError(f"Không tải được OpenStreetMap qua Overpass: {last}")


def _lonlat_to_local(grid, lon, lat):
    lat0 = math.radians(grid.cfg.origin_lat)
    lon = np.asarray(lon, float)
    lat = np.asarray(lat, float)
    x = (
        np.radians(lon - grid.cfg.origin_lon)
        * EARTH_RADIUS_M
        * math.cos(lat0)
    )
    y = np.radians(lat - grid.cfg.origin_lat) * EARTH_RADIUS_M
    return x, y


def _densify_xy(coords, max_step=75.0):
    pts = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(d / max_step)))
        for t in np.linspace(0.0, 1.0, n, endpoint=False):
            pts.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    if coords:
        pts.append(coords[-1])
    return pts


def _osm_point_clouds(obj, grid):
    roads, rivers, settlements = [], [], []

    for el in obj.get("elements", []):
        tags = el.get("tags", {})
        typ = el.get("type")

        if typ == "node" and "place" in tags:
            x, y = _lonlat_to_local(grid, [el["lon"]], [el["lat"]])
            settlements.append((float(x[0]), float(y[0])))
            continue

        geom = el.get("geometry")
        if not geom:
            continue

        lon = [p["lon"] for p in geom]
        lat = [p["lat"] for p in geom]
        x, y = _lonlat_to_local(grid, lon, lat)
        coords = list(zip(x.tolist(), y.tolist()))

        if "highway" in tags:
            roads.extend(_densify_xy(coords))
        if "waterway" in tags:
            rivers.extend(_densify_xy(coords))
        if tags.get("landuse") == "residential":
            arr = np.asarray(coords, float)
            if arr.size:
                settlements.append(tuple(arr.mean(axis=0)))

    if not roads:
        raise RuntimeError("OSM không trả đường giao thông trong vùng nghiên cứu.")
    if not rivers:
        raise RuntimeError("OSM không trả sông/suối/kênh trong vùng nghiên cứu.")
    if not settlements:
        raise RuntimeError("OSM không trả điểm/khu dân cư trong vùng nghiên cứu.")

    return (
        np.asarray(roads, float),
        np.asarray(rivers, float),
        np.asarray(settlements, float),
    )


def _nearest_distance(grid_xy, source_xy):
    from scipy.spatial import cKDTree
    tree = cKDTree(source_xy)
    d, _ = tree.query(grid_xy, k=1, workers=-1)
    return d


def _slope(elevation, cell):
    gy, gx = np.gradient(elevation, cell)
    return np.rad2deg(np.arctan(np.hypot(gx, gy)))


def _normalise_log_population(pop):
    x = np.log1p(np.maximum(pop, 0.0))
    lo, hi = np.nanpercentile(x, [2, 98])
    return np.clip((x - lo) / max(hi - lo, 1e-9), 0.0, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        default="data/real/geospatial",
    )
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    grid = Grid(GridConfig())
    bbox = _bbox(grid)
    lons, lats = _grid_points(grid)
    n = lons.size

    print("Vùng nghiên cứu WGS84:", bbox)
    print("Số ô:", n)

    # 1) Copernicus DEM
    print("1/5 Copernicus DEM GLO-30")
    dem_hrefs, dem_items = _stac_assets(
        "cop-dem-glo-30", "data", bbox
    )
    elevation = _sample_assets(dem_hrefs, lons, lats).reshape(grid.shape)
    slope = _slope(elevation, grid.cell)

    # 2) ESA WorldCover
    print("2/5 ESA WorldCover")
    wc_hrefs, wc_items = _stac_assets(
        "esa-worldcover", "map", bbox
    )
    worldcover = _sample_assets(wc_hrefs, lons, lats).reshape(grid.shape)
    worldcover = np.rint(worldcover).astype(np.int16)

    # 3) WorldPop
    print("3/5 WorldPop 2020")
    worldpop_path = raw_dir / "worldpop_vnm_2020_100m.tif"
    _download(WORLDPOP_URL, worldpop_path)
    population = _sample_one_raster(
        str(worldpop_path), lons, lats
    ).reshape(grid.shape)
    population = np.maximum(population, 0.0)
    exposure = _normalise_log_population(population)

    # 4) SoilGrids
    print("4/5 SoilGrids clay/sand")
    clay_raw = _sample_one_raster(
        SOIL_CLAY_URL, lons, lats
    ).reshape(grid.shape)
    sand_raw = _sample_one_raster(
        SOIL_SAND_URL, lons, lats
    ).reshape(grid.shape)

    # SoilGrids clay/sand are g/kg, convert to percentage.
    clay_pct = clay_raw / 10.0
    sand_pct = sand_raw / 10.0
    if (
        np.nanmin(clay_pct) < 0
        or np.nanmax(clay_pct) > 100.5
        or np.nanmin(sand_pct) < 0
        or np.nanmax(sand_pct) > 100.5
    ):
        raise RuntimeError(
            "Giá trị SoilGrids ngoài khoảng kỳ vọng sau khi đổi sang %."
        )

    # Chỉ số này là biến dẫn xuất từ dữ liệu đất thật, không phải lớp quan sát độc lập.
    soil_softness = np.clip(
        0.65 * (clay_pct / 100.0)
        + 0.35 * (1.0 - sand_pct / 100.0),
        0.0,
        1.0,
    )

    # 5) OSM
    print("5/5 OpenStreetMap")
    osm_json = _fetch_overpass(bbox, raw_dir / "osm_overpass.json")
    road_xy, river_xy, settlement_xy = _osm_point_clouds(osm_json, grid)

    cols, rows = np.meshgrid(
        np.arange(grid.cfg.n_cells_x),
        np.arange(grid.cfg.n_cells_y),
    )
    gx, gy = grid.index_to_center_xy(cols.ravel(), rows.ravel())
    grid_xy = np.column_stack([gx, gy])

    dist_road = _nearest_distance(grid_xy, road_xy).reshape(grid.shape)
    dist_river = _nearest_distance(grid_xy, river_xy).reshape(grid.shape)
    dist_settlement = _nearest_distance(
        grid_xy, settlement_xy
    ).reshape(grid.shape)

    # WorldCover codes: 10 tree, 40 cropland, 50 built-up.
    is_forest = worldcover == 10
    is_farmland = worldcover == 40
    is_builtup = worldcover == 50

    np.savez_compressed(
        out_dir / "study_layers.npz",
        elevation_m=elevation.astype(np.float32),
        slope_deg=slope.astype(np.float32),
        soil_softness=soil_softness.astype(np.float32),
        soil_clay_pct=clay_pct.astype(np.float32),
        soil_sand_pct=sand_pct.astype(np.float32),
        is_farmland=is_farmland.astype(bool),
        is_forest=is_forest.astype(bool),
        is_builtup=is_builtup.astype(bool),
        dist_settlement_m=dist_settlement.astype(np.float32),
        dist_road_m=dist_road.astype(np.float32),
        dist_river_m=dist_river.astype(np.float32),
        population_count=population.astype(np.float32),
        exposure=exposure.astype(np.float32),
        worldcover_class=worldcover.astype(np.int16),
        settlement_xy=settlement_xy.astype(np.float32),
    )

    provenance = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_bbox_wgs84": {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
        },
        "grid": {
            "cell_size_m": grid.cell,
            "n_cells_x": grid.cfg.n_cells_x,
            "n_cells_y": grid.cfg.n_cells_y,
        },
        "sources": {
            "elevation": {
                "dataset": "Copernicus DEM GLO-30",
                "collection": "cop-dem-glo-30",
                "items": dem_items,
                "role": "observed public dataset",
            },
            "land_cover": {
                "dataset": "ESA WorldCover",
                "collection": "esa-worldcover",
                "items": wc_items,
                "role": "observed public dataset",
            },
            "population": {
                "dataset": "WorldPop 2020 constrained 100m, Vietnam",
                "url": WORLDPOP_URL,
                "role": "observed/modelled public population dataset",
            },
            "soil": {
                "dataset": "SoilGrids 0-5cm mean clay and sand",
                "clay_url": SOIL_CLAY_URL,
                "sand_url": SOIL_SAND_URL,
                "role": "public gridded soil predictions",
            },
            "roads_rivers_settlements": {
                "dataset": "OpenStreetMap",
                "query_cache": str(raw_dir / "osm_overpass.json"),
                "role": "public volunteered geographic data",
            },
        },
        "derived_layers": {
            "slope_deg": "derived from Copernicus DEM",
            "soil_softness": (
                "derived proxy = 0.65*clay_fraction + "
                "0.35*(1-sand_fraction)"
            ),
            "distances": "nearest distance to OSM geometry",
            "exposure": "robust-normalised log1p WorldPop cell count",
        },
        "no_synthetic_fallback": True,
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("Hoàn tất.")
    print("Layers:", out_dir / "study_layers.npz")
    print("Provenance:", out_dir / "provenance.json")
    print("Không có lớp nền nào được sinh ngẫu nhiên.")


if __name__ == "__main__":
    main()
