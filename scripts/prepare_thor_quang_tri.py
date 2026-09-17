#!/usr/bin/env python3
"""
Chuẩn bị dữ liệu THOR thật cho vùng nghiên cứu hiện tại của Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn.

Đầu vào:
    thor_data_vietnam.csv  (THOR Vietnam, ~4.6-4.8 triệu dòng)

Đầu ra:
    thor_quang_tri_missions.csv
    thor_quang_tri_contract.npz
    thor_quang_tri_summary.json

Script đọc theo chunk nên không cần nạp toàn bộ file nhiều GB vào RAM.

Lưu ý:
- Lọc NONKINETIC theo đúng cách phổ biến khi xử lý THOR.
- Chỉ lấy các bản ghi có numweaponsdelivered > 0 và tọa độ WGS84 hợp lệ.
- Vùng lọc mặc định khớp CHÍNH XÁC lưới Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn hiện tại
  (origin 106.85E, 16.72N; 220x180 ô; 100 m/ô), không phải toàn tỉnh Quảng Trị.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_M = 6_371_000.0
LB_TO_KG = 0.45359237
DEFAULT_STANDARD_BOMB_KG = 340.0

# Khớp src/demine/config.py hiện tại
ORIGIN_LON = 106.85
ORIGIN_LAT = 16.72
CELL_SIZE_M = 100.0
N_CELLS_X = 220
N_CELLS_Y = 180

REQUIRED = {
    "tgtlatdd_ddd_wgs84",
    "tgtlonddd_ddd_wgs84",
    "numweaponsdelivered",
}

OPTIONAL = [
    "thor_data_viet_id",
    "msndate",
    "sourceid",
    "sourcerecord",
    "weapontype",
    "weapontypeweight",
    "mfunc_desc",
    "missionid",
    "tgtcountry",
    "mfunc_desc_class",
    "weaponsloadedweight",
    "year",
]


def study_bbox() -> dict:
    """BBox WGS84 khớp phép chiếu phẳng đơn giản trong data/geo.py."""
    width_m = N_CELLS_X * CELL_SIZE_M
    height_m = N_CELLS_Y * CELL_SIZE_M
    lat0 = math.radians(ORIGIN_LAT)

    east = ORIGIN_LON + math.degrees(
        width_m / (EARTH_RADIUS_M * math.cos(lat0))
    )
    north = ORIGIN_LAT + math.degrees(height_m / EARTH_RADIUS_M)

    return {
        "west": ORIGIN_LON,
        "south": ORIGIN_LAT,
        "east": east,
        "north": north,
    }


def lonlat_to_local_xy(lon, lat):
    """
    Phép nghịch đảo của Grid.xy_to_lonlat trong Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn.
    Trả x/y theo mét tính từ gốc vùng nghiên cứu.
    """
    lat0 = math.radians(ORIGIN_LAT)
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    x = (
        np.radians(lon - ORIGIN_LON)
        * EARTH_RADIUS_M
        * math.cos(lat0)
    )
    y = np.radians(lat - ORIGIN_LAT) * EARTH_RADIUS_M
    return x, y


def _resolve_columns(path: Path):
    header = pd.read_csv(path, nrows=0)
    actual = list(header.columns)
    by_lower = {c.strip().lower(): c for c in actual}

    missing = [c for c in REQUIRED if c not in by_lower]
    if missing:
        raise ValueError(
            "THOR CSV thiếu cột bắt buộc: "
            + ", ".join(sorted(missing))
            + "\nCác cột tìm thấy đầu file:\n"
            + ", ".join(actual[:80])
        )

    wanted_lower = list(REQUIRED) + OPTIONAL
    usecols = [by_lower[c] for c in wanted_lower if c in by_lower]
    rename = {by_lower[c]: c for c in wanted_lower if c in by_lower}
    return usecols, rename


def _numeric(series):
    return pd.to_numeric(series, errors="coerce")


def process_thor(input_csv: Path, out_dir: Path, chunksize: int = 200_000):
    out_dir.mkdir(parents=True, exist_ok=True)
    bbox = study_bbox()
    usecols, rename = _resolve_columns(input_csv)

    pieces = []
    total_read = 0
    total_kinetic_delivered = 0

    for chunk in pd.read_csv(
        input_csv,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    ):
        total_read += len(chunk)
        chunk = chunk.rename(columns=rename)

        lat = _numeric(chunk["tgtlatdd_ddd_wgs84"])
        lon = _numeric(chunk["tgtlonddd_ddd_wgs84"])
        delivered = _numeric(chunk["numweaponsdelivered"])

        keep = (
            lat.notna()
            & lon.notna()
            & delivered.notna()
            & (delivered > 0)
        )

        # Cách lọc THOR thực dụng: loại NONKINETIC nếu cột này có mặt.
        if "mfunc_desc_class" in chunk.columns:
            cls = (
                chunk["mfunc_desc_class"]
                .astype("string")
                .str.upper()
                .str.strip()
            )
            keep &= cls.ne("NONKINETIC") | cls.isna()

        total_kinetic_delivered += int(keep.sum())

        keep &= (
            lon.between(bbox["west"], bbox["east"], inclusive="both")
            & lat.between(bbox["south"], bbox["north"], inclusive="both")
        )

        if not keep.any():
            continue

        q = chunk.loc[keep].copy()
        q["tgtlatdd_ddd_wgs84"] = lat[keep].astype(float)
        q["tgtlonddd_ddd_wgs84"] = lon[keep].astype(float)
        q["numweaponsdelivered"] = (
            delivered[keep].round().clip(lower=1).astype("int64")
        )

        x, y = lonlat_to_local_xy(
            q["tgtlonddd_ddd_wgs84"].to_numpy(),
            q["tgtlatdd_ddd_wgs84"].to_numpy(),
        )
        q["record_x"] = x
        q["record_y"] = y
        q["record_n_bombs"] = q["numweaponsdelivered"].astype("int64")

        # Tải trọng:
        # THOR weapontypeweight thể hiện trọng lượng danh định của vũ khí
        # (ví dụ MK-82 có giá trị 500, tương ứng 500 lb).
        if "weapontypeweight" in q.columns:
            w_lb = _numeric(q["weapontypeweight"])
        else:
            w_lb = pd.Series(np.nan, index=q.index)

        known_weight = w_lb.notna() & (w_lb > 0)
        tonnage_known = (
            q["record_n_bombs"].astype(float)
            * w_lb.fillna(0.0)
            * LB_TO_KG
            / 1000.0
        )
        tonnage_fallback = (
            q["record_n_bombs"].astype(float)
            * DEFAULT_STANDARD_BOMB_KG
            / 1000.0
        )

        q["recorded_tonnage_t"] = np.where(
            known_weight,
            tonnage_known,
            tonnage_fallback,
        )
        q["tonnage_source"] = np.where(
            known_weight,
            "thor_weapontypeweight",
            "standardized_340kg_fallback",
        )

        pieces.append(q)

    if not pieces:
        raise RuntimeError(
            "Không có bản ghi THOR nào rơi vào bbox vùng nghiên cứu hiện tại.\n"
            f"BBox: {bbox}"
        )

    df = pd.concat(pieces, ignore_index=True)

    # Mã phi vụ của THOR thường là chuỗi. Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn hiện dùng integer,
    # vì vậy factorize một lần sau khi đã lọc vùng để tạo mã int ổn định trong file.
    if "missionid" in df.columns:
        mission_key = df["missionid"].astype("string")
    else:
        mission_key = pd.Series(pd.NA, index=df.index, dtype="string")

    if "sourcerecord" in df.columns:
        mission_key = mission_key.fillna(
            df["sourcerecord"].astype("string")
        )

    mission_key = mission_key.fillna(
        pd.Series(
            [f"row-{i}" for i in range(len(df))],
            index=df.index,
            dtype="string",
        )
    )
    df["record_mission_id"] = pd.factorize(mission_key, sort=True)[0].astype(
        "int64"
    )

    # Sắp xếp cột quan trọng lên đầu.
    first = [
        "record_x",
        "record_y",
        "record_n_bombs",
        "record_mission_id",
        "recorded_tonnage_t",
        "tonnage_source",
        "tgtlatdd_ddd_wgs84",
        "tgtlonddd_ddd_wgs84",
        "numweaponsdelivered",
    ]
    first = [c for c in first if c in df.columns]
    rest = [c for c in df.columns if c not in first]
    df = df[first + rest]

    csv_path = out_dir / "thor_quang_tri_missions.csv"
    npz_path = out_dir / "thor_quang_tri_contract.npz"
    summary_path = out_dir / "thor_quang_tri_summary.json"

    df.to_csv(csv_path, index=False)

    np.savez_compressed(
        npz_path,
        record_x=df["record_x"].to_numpy(dtype=float),
        record_y=df["record_y"].to_numpy(dtype=float),
        record_n_bombs=df["record_n_bombs"].to_numpy(dtype=np.int64),
        record_mission_id=df["record_mission_id"].to_numpy(dtype=np.int64),
        recorded_tonnage_t=df["recorded_tonnage_t"].to_numpy(dtype=float),
        latitude=df["tgtlatdd_ddd_wgs84"].to_numpy(dtype=float),
        longitude=df["tgtlonddd_ddd_wgs84"].to_numpy(dtype=float),
    )

    date_min = None
    date_max = None
    if "msndate" in df.columns:
        dates = pd.to_datetime(df["msndate"], errors="coerce")
        if dates.notna().any():
            date_min = str(dates.min().date())
            date_max = str(dates.max().date())

    summary = {
        "input_file": str(input_csv),
        "rows_scanned": int(total_read),
        "rows_kinetic_with_delivered_weapon_before_bbox": int(
            total_kinetic_delivered
        ),
        "rows_in_demine_study_area": int(len(df)),
        "raw_target_records_in_demine_bbox": int(len(df)),
        "unique_missions_in_area": int(df["record_mission_id"].nunique()),
        "sum_weapons_delivered": int(df["record_n_bombs"].sum()),
        "sum_recorded_tonnage_t": float(df["recorded_tonnage_t"].sum()),
        "fraction_rows_with_thor_weapon_weight": float(
            (df["tonnage_source"] == "thor_weapontypeweight").mean()
        ),
        "mission_date_min": date_min,
        "mission_date_max": date_max,
        "study_bbox_wgs84": bbox,
        "study_grid": {
            "origin_lon": ORIGIN_LON,
            "origin_lat": ORIGIN_LAT,
            "cell_size_m": CELL_SIZE_M,
            "n_cells_x": N_CELLS_X,
            "n_cells_y": N_CELLS_Y,
        },
        "note": (
            "Historical bombing records are real THOR records. "
            "Rows without a usable THOR weapon weight use the existing "
            "Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn standardized 340 kg/weapon fallback and are marked "
            "explicitly in tonnage_source."
        ),
    }

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Hoàn tất.")
    print(f"  CSV:     {csv_path}")
    print(f"  Contract:{npz_path}")
    print(f"  Summary: {summary_path}")
    print()
    print(f"  Bản ghi trong vùng: {len(df):,}")
    print(f"  Phi vụ:              {df['record_mission_id'].nunique():,}")
    print(f"  Vũ khí giao:          {df['record_n_bombs'].sum():,}")
    print(
        "  Tỷ lệ có weight THOR: "
        f"{100*(df['tonnage_source']=='thor_weapontypeweight').mean():.1f}%"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("thor_csv", type=Path)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/real/quang_tri"),
    )
    p.add_argument("--chunksize", type=int, default=200_000)
    args = p.parse_args()

    process_thor(args.thor_csv, args.out_dir, args.chunksize)


if __name__ == "__main__":
    main()
