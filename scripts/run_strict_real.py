#!/usr/bin/env python3
"""Chạy Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn với các lớp đầu vào công khai, không sinh ground truth giả.

Đầu ra là "chỉ số ưu tiên", không phải xác suất UXO.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demine.config import GridConfig, StrictRealConfig
from demine.data.geo import Grid
from demine.data.real_geospatial import load_real_terrain
from demine.data.real_craters import load_published_craters
from demine.risk.strict_real import build_strict_real_table
from demine.viz.strict_real_figures import make_strict_real_figures


def _priority_label(score):
    if score >= 0.75:
        return "Rất cao"
    if score >= 0.55:
        return "Cao"
    if score >= 0.35:
        return "Trung bình"
    return "Thấp"


def _make_map(df, out_html):
    import folium
    from branca.colormap import linear

    center = [float(df["vi_do"].median()), float(df["kinh_do"].median())]
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    cmap = linear.YlOrRd_09.scale(
        float(df["chi_so_uu_tien"].min()),
        float(df["chi_so_uu_tien"].max()),
    )
    cmap.caption = "Chỉ số ưu tiên"

    top = df.nsmallest(min(500, len(df)), "thu_tu_uu_tien")
    for _, r in top.iterrows():
        popup = (
            f"<b>Ưu tiên #{int(r['thu_tu_uu_tien'])}</b><br>"
            f"Chỉ số ưu tiên: {r['chi_so_uu_tien']:.3f}<br>"
            f"Mức ưu tiên: {r['muc_uu_tien']}<br>"
            f"Hồ sơ không kích (THOR): {r['tai_trong_bom_ghi_nhan_tan']:.2f} tấn<br>"
            f"Dấu vết hố bom (KH-9): {int(r['so_ho_bom_phat_hien'])}<br>"
            f"Dân số WorldPop: {r['dan_so_uoc_tinh_o']:.1f} người/ô"
        )
        folium.CircleMarker(
            [r["vi_do"], r["kinh_do"]],
            radius=5,
            color="white",
            weight=1,
            fill=True,
            fill_color=cmap(r["chi_so_uu_tien"]),
            fill_opacity=0.85,
            popup=popup,
        ).add_to(m)

    cmap.add_to(m)
    m.save(out_html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--missions",
        default="data/real/quang_tri/thor_quang_tri_missions.csv",
    )
    ap.add_argument(
        "--craters",
        default="data/real/craters/quang_tri/crater_centroids.geojson",
    )
    ap.add_argument(
        "--geo-layers",
        default="data/real/geospatial/study_layers.npz",
    )
    ap.add_argument(
        "--geo-provenance",
        default="data/real/geospatial/provenance.json",
    )
    ap.add_argument("--output-dir", default="outputs_strict_real")
    args = ap.parse_args()

    grid_cfg = GridConfig()
    strict_cfg = StrictRealConfig()
    grid = Grid(grid_cfg)

    terrain, geo_prov = load_real_terrain(
        args.geo_layers,
        args.geo_provenance,
    )

    crater_map, _, crater_coverage, crater_meta = load_published_craters(
        grid, args.craters
    )

    table = build_strict_real_table(
        grid,
        terrain,
        crater_map,
        args.missions,
        strict_cfg.record_kernel_radius_m,
    )

    missions = pd.read_csv(args.missions)
    tonnage_grid = grid.accumulate(
        missions["record_x"].to_numpy(float),
        missions["record_y"].to_numpy(float),
        missions["recorded_tonnage_t"].to_numpy(float),
    )
    record_count_grid = grid.accumulate(
        missions["record_x"].to_numpy(float),
        missions["record_y"].to_numpy(float),
    )

    lon, lat = grid.cell_centers_lonlat()
    rows = np.arange(grid.n_cells)
    score = table.score.ravel()

    # Source-level scores are exported for transparent explanation in the web UI.
    # They are derived from the exact same normalized components already used by
    # the strict-real ranking, so this does not change the final priority score.
    def _weighted_source(names):
        denom = sum(table.weights[n] for n in names)
        out = np.zeros(grid.shape, dtype=float)
        for n in names:
            out += table.weights[n] * table.components[n]
        return out / denom if denom > 0 else out

    airstrike_evidence = _weighted_source([
        "tai_trong_thor_lan_toa",
        "tai_trong_thor_lan_can_500m",
        "mat_do_mission_thor",
    ]).ravel()
    crater_evidence = _weighted_source([
        "mat_do_ho_bom_kh9",
        "ho_bom_lan_can_300m",
    ]).ravel()
    spatial_context = _weighted_source([
        "clay_soilgrids", "dat_canh_tac_worldcover", "dat_xay_dung_worldcover",
        "gan_song_osm", "gan_duong_osm", "gan_khu_dan_cu_osm", "dan_so_worldpop",
    ]).ravel()
    rank = pd.Series(-score).rank(
        method="first", ascending=True
    ).astype(int).to_numpy()

    cols = rows % grid.cfg.n_cells_x
    row_idx = rows // grid.cfg.n_cells_x
    stable_cell_id = [f"GRID100_C{int(c):03d}_R{int(r):03d}" for c, r in zip(cols, row_idx)]

    out = pd.DataFrame({
        "thu_tu_uu_tien": rank,
        "chi_so_o_luoi": rows,
        "cell_id": stable_cell_id,
        "kinh_do": lon,
        "vi_do": lat,
        "chi_so_uu_tien": score,
        "muc_uu_tien": [_priority_label(v) for v in score],
        "diem_bang_chung_khong_kich": airstrike_evidence,
        "diem_bang_chung_ho_bom": crater_evidence,
        "diem_boi_canh_khong_gian": spatial_context,
        "tai_trong_bom_ghi_nhan_tan": tonnage_grid.ravel(),
        "so_ho_so_khong_kich": record_count_grid.ravel(),
        "so_ho_bom_phat_hien": crater_map.ravel(),
        "so_ho_bom_300m": table.X[:, table.names.index("ho_bom_lan_can_300m")],
        "do_cao_m": terrain.elevation_m.ravel(),
        "do_doc_do": terrain.slope_deg.ravel(),
        "clay_pct": terrain.soil_clay_pct.ravel(),
        "sand_pct": terrain.soil_sand_pct.ravel(),
        "la_dat_canh_tac": terrain.is_farmland.ravel(),
        "la_rung": terrain.is_forest.ravel(),
        "la_dat_xay_dung": terrain.is_builtup.ravel(),
        "khoang_cach_song_m": terrain.dist_river_m.ravel(),
        "khoang_cach_duong_m": terrain.dist_road_m.ravel(),
        "khoang_cach_khu_dan_cu_m": terrain.dist_village_m.ravel(),
        "dan_so_uoc_tinh_o": terrain.population_count.ravel(),
    }).sort_values("thu_tu_uu_tien")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "danh_muc_uu_tien_ra_pha.csv"
    out.to_csv(csv_path, index=False, encoding="utf-8-sig")

    score_sorted = np.sort(score[np.isfinite(score)])[::-1]
    score_total = float(score_sorted.sum())

    def _coverage(frac: float) -> float:
        if len(score_sorted) == 0 or score_total <= 0:
            return 0.0
        n = max(1, int(np.ceil(frac * len(score_sorted))))
        return float(score_sorted[:n].sum() / score_total)

    summary = {
        "che_do": "strict_real_observed_inputs",
        "ten_ket_qua": "Chỉ số ưu tiên từ các lớp dữ liệu công khai",
        "khong_phai_xac_suat_uxo": True,
        "field_verified": False,
        "so_o_luoi": int(grid.n_cells),
        "so_thor_missions": int(len(missions)),
        "so_ho_bom_kh9_trong_vung": int(crater_map.sum()),
        "coverage_ho_bom": float(crater_coverage.mean()),
        "tap_trung_diem_uu_tien": {
            "top_10pct": _coverage(0.10),
            "top_20pct": _coverage(0.20),
            "top_50pct": _coverage(0.50),
            "dien_giai": "Tỉ lệ tổng chỉ số ưu tiên nằm trong phần diện tích được xếp hạng cao nhất; không phải tỉ lệ UXO thu hồi."
        },
        "nguon_dia_ly": geo_prov,
        "nguon_ho_bom": crater_meta,
        "trong_so_chi_so": table.weights,
        "ghi_chu": (
            "Bản này không dùng UXO point-level, clearance polygon hoặc "
            "casualty point giả lập. Chỉ số dùng để xếp thứ tự xem xét hiện trường."
        ),
    }
    (out_dir / "ket_qua.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn — kết quả xếp hạng từ dữ liệu công khai

Bản chạy này chỉ sử dụng các lớp đầu vào có nguồn công khai hoặc được công bố:

- hồ sơ không kích THOR;
- hố bom công bố từ ảnh KH-9;
- Copernicus DEM GLO-30;
- ESA WorldCover;
- OpenStreetMap;
- WorldPop 2020;
- SoilGrids.

## Cách đọc kết quả

`chi_so_uu_tien` là điểm xếp hạng tổng hợp từ 0 đến 1. Điểm cao hơn nghĩa là ô
lưới có nhiều bằng chứng lịch sử và mức phơi nhiễm hiện tại hơn theo các lớp trên.

Điểm này **không phải xác suất còn UXO** và không thay thế khảo sát kỹ thuật.

## Những dữ liệu không có trong bản chạy này

Không sử dụng vị trí UXO giả lập, polygon rà phá giả lập hay vị trí tai nạn giả lập.
Muốn kiểm chứng độ chính xác theo thực địa cần dữ liệu IMSMA/QTMAC ở cấp điểm hoặc
polygon tương ứng.
"""
    (out_dir / "bao_cao_tong_hop.md").write_text(
        report,
        encoding="utf-8",
    )

    try:
        _make_map(out, out_dir / "ban_do_uu_tien.html")
    except Exception as exc:
        print("Cảnh báo: chưa tạo được bản đồ HTML:", exc)

    try:
        figures = make_strict_real_figures(
            out,
            (grid.cfg.n_cells_y, grid.cfg.n_cells_x),
            table.weights,
            out_dir / "figures",
        )
        summary["figures"] = [p.name for p in figures]
        (out_dir / "ket_qua.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print("Cảnh báo: chưa tạo được figures strict-real:", exc)

    print("Hoàn tất.")
    print("Danh mục:", csv_path.resolve())
    print("Kết quả:", (out_dir / "ket_qua.json").resolve())
    print("Không có lớp ground truth giả trong bản chạy strict-real.")


if __name__ == "__main__":
    main()
