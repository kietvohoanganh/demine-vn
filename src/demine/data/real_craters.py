"""Load published crater observations/predictions from real KH-9 imagery."""
from __future__ import annotations
from pathlib import Path
import math
import numpy as np

EARTH_RADIUS_M=6_371_000.0

def _local_xy_from_lonlat(grid,lon,lat):
    lat0=math.radians(grid.cfg.origin_lat)
    lon=np.asarray(lon,dtype=float); lat=np.asarray(lat,dtype=float)
    x=np.radians(lon-grid.cfg.origin_lon)*EARTH_RADIUS_M*math.cos(lat0)
    y=np.radians(lat-grid.cfg.origin_lat)*EARTH_RADIUS_M
    return x,y

def load_published_craters(grid,geojson_path:str|Path,default_diameter_m:float=15.0):
    try: import geopandas as gpd
    except ImportError as exc: raise ImportError("Cần geopandas để đọc crater GeoJSON thật.") from exc
    path=Path(geojson_path); gdf=gpd.read_file(path)
    if gdf.empty: raise ValueError(f"Không có hố bom trong {path}")
    source_crs=str(gdf.crs) if gdf.crs is not None else "unknown"
    if gdf.crs is None: gdf=gdf.set_crs("EPSG:4326",allow_override=True)
    geom_type=str(gdf.geometry.geom_type.mode().iloc[0])
    if geom_type in {"Polygon","MultiPolygon"}:
        projected=gdf if not gdf.crs.is_geographic else gdf.to_crs("EPSG:32648")
        cent=projected.geometry.centroid; area=projected.geometry.area.to_numpy(float)
        diameters=2.0*np.sqrt(np.maximum(area,0.0)/np.pi)
        c_gdf=projected.copy(); c_gdf.geometry=cent; c_gdf=c_gdf.to_crs("EPSG:4326")
    else:
        c_gdf=gdf.to_crs("EPSG:4326"); diameters=np.full(len(c_gdf),default_diameter_m,dtype=float)
    lon=c_gdf.geometry.x.to_numpy(float); lat=c_gdf.geometry.y.to_numpy(float)
    x,y=_local_xy_from_lonlat(grid,lon,lat); col,row=grid.xy_to_index(x,y); keep=grid.inside(col,row)
    x,y=x[keep],y[keep]; diameters=diameters[keep]
    crater_map=grid.accumulate(x,y); diameter_sum=grid.accumulate(x,y,diameters)
    crater_diameter_map=np.divide(diameter_sum,crater_map,out=np.zeros_like(diameter_sum),where=crater_map>0)
    min_lon,min_lat,max_lon,max_lat=c_gdf.total_bounds; centers_lon,centers_lat=grid.cell_centers_lonlat()
    coverage=((centers_lon>=min_lon)&(centers_lon<=max_lon)&(centers_lat>=min_lat)&(centers_lat<=max_lat)).reshape(grid.shape)
    meta={"mode":"published_real_kh9_crater_observations","source_file":str(path),"source_crs":source_crs,"geometry_type":geom_type,
          "n_features_total":int(len(gdf)),"n_features_inside_bbox":int(keep.sum()),"coverage_fraction_approx":float(coverage.mean()),
          "note":"Published crater predictions on real declassified KH-9 imagery; not UXO ground truth."}
    return crater_map,crater_diameter_map,coverage,meta
