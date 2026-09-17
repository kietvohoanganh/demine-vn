"""Utilities for optional real-world mine-action validation layers.

Ground-truth/field-validation data are deliberately kept OUT of the priority
score. They are used only after ranking to compare the ranking with independent
observations such as Confirmed Hazardous Areas (CHA), land-release polygons, or
EOD/EO finding points.

No missing field record is interpreted as a negative observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

GRID_CRS = "EPSG:32648"
WGS84 = "EPSG:4326"
CELL_SIZE_M = 100.0


@dataclass(frozen=True)
class ValidationSummary:
    available: bool
    confirmed_hazard_cells: int = 0
    released_cells: int = 0
    eod_cells: int = 0
    validated_cells: int = 0
    cha_coverage_top10: Optional[float] = None
    cha_coverage_top20: Optional[float] = None
    eod_coverage_top10: Optional[float] = None
    eod_coverage_top20: Optional[float] = None


def grid_from_compact_json(path: str | Path) -> gpd.GeoDataFrame:
    """Reconstruct the canonical 100 m UTM grid used by the bundled outputs."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = obj["schema"]
    rows = [dict(zip(schema, vals)) for vals in obj["rows"]]
    records = []
    for r in rows:
        e, n = int(r["e"]), int(r["n"])
        x0, y0 = e * CELL_SIZE_M, n * CELL_SIZE_M
        records.append({
            "cell_id": f"U48N_100_E{e}_N{n}",
            "e": e,
            "n": n,
            "priority_score": float(r["priority"]),
            "geometry": box(x0, y0, x0 + CELL_SIZE_M, y0 + CELL_SIZE_M),
        })
    return gpd.GeoDataFrame(records, geometry="geometry", crs=GRID_CRS)


def _load_optional(paths: Iterable[str | Path]) -> Optional[gpd.GeoDataFrame]:
    frames = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        gdf = gpd.read_file(p)
        if gdf.empty:
            continue
        if gdf.crs is None:
            raise ValueError(f"Ground-truth layer has no CRS: {p}")
        frames.append(gdf.to_crs(GRID_CRS))
    if not frames:
        return None
    merged = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=GRID_CRS)


def _cells_intersecting(grid: gpd.GeoDataFrame, layer: Optional[gpd.GeoDataFrame]) -> set[str]:
    if layer is None or layer.empty:
        return set()
    # Spatial join is used only as presence/overlap evidence. We do not infer
    # exact ordnance location from a polygon.
    joined = gpd.sjoin(grid[["cell_id", "geometry"]], layer[["geometry"]], how="inner", predicate="intersects")
    return set(joined["cell_id"].astype(str).unique())


def _coverage_at_fraction(df: pd.DataFrame, positive_mask: pd.Series, frac: float) -> Optional[float]:
    positives = int(positive_mask.sum())
    if positives <= 0:
        return None
    n = max(1, int(np.ceil(len(df) * frac)))
    top_ids = set(df.nsmallest(n, "priority_rank")["cell_id"].astype(str))
    covered = int(df.loc[positive_mask, "cell_id"].astype(str).isin(top_ids).sum())
    return covered / positives


def integrate_validation(
    grid_compact_json: str | Path,
    cha_paths: Iterable[str | Path] = (),
    land_release_paths: Iterable[str | Path] = (),
    eod_paths: Iterable[str | Path] = (),
) -> tuple[pd.DataFrame, ValidationSummary]:
    """Overlay independent real-world validation data onto the canonical grid.

    Status precedence:
      CONFIRMED_EO  -> a field EOD/EO point intersects the cell
      CONFIRMED_HAZARD -> cell intersects a CHA polygon
      LAND_RELEASED -> cell intersects a land-release/clearance polygon
      UNKNOWN -> no spatial validation record

    LAND_RELEASED is not treated as a universal 'negative UXO' label; it is a
    documented land-release status and remains separate in outputs.
    """
    grid = grid_from_compact_json(grid_compact_json)
    grid = grid.sort_values("priority_score", ascending=False).reset_index(drop=True)
    grid["priority_rank"] = np.arange(1, len(grid) + 1)

    cha = _load_optional(cha_paths)
    release = _load_optional(land_release_paths)
    eod = _load_optional(eod_paths)

    cha_ids = _cells_intersecting(grid, cha)
    release_ids = _cells_intersecting(grid, release)
    eod_ids = _cells_intersecting(grid, eod)

    ids = grid["cell_id"].astype(str)
    grid["inside_confirmed_hazard"] = ids.isin(cha_ids)
    grid["inside_land_release"] = ids.isin(release_ids)
    grid["has_confirmed_eo_record"] = ids.isin(eod_ids)
    grid["field_verified"] = (
        grid["inside_confirmed_hazard"] | grid["inside_land_release"] | grid["has_confirmed_eo_record"]
    )

    status = np.full(len(grid), "UNKNOWN", dtype=object)
    status[grid["inside_land_release"].to_numpy()] = "LAND_RELEASED"
    status[grid["inside_confirmed_hazard"].to_numpy()] = "CONFIRMED_HAZARD"
    status[grid["has_confirmed_eo_record"].to_numpy()] = "CONFIRMED_EO"
    grid["validation_status"] = status

    cha_mask = grid["inside_confirmed_hazard"] | grid["has_confirmed_eo_record"]
    eod_mask = grid["has_confirmed_eo_record"]
    summary = ValidationSummary(
        available=bool(grid["field_verified"].any()),
        confirmed_hazard_cells=int(grid["inside_confirmed_hazard"].sum()),
        released_cells=int(grid["inside_land_release"].sum()),
        eod_cells=int(grid["has_confirmed_eo_record"].sum()),
        validated_cells=int(grid["field_verified"].sum()),
        cha_coverage_top10=_coverage_at_fraction(grid, cha_mask, 0.10),
        cha_coverage_top20=_coverage_at_fraction(grid, cha_mask, 0.20),
        eod_coverage_top10=_coverage_at_fraction(grid, eod_mask, 0.10),
        eod_coverage_top20=_coverage_at_fraction(grid, eod_mask, 0.20),
    )

    # Export only columns required by web/data QA. Geometry stays out of the CSV.
    out = grid.drop(columns="geometry").copy()
    return out, summary
