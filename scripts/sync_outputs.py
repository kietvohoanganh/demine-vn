#!/usr/bin/env python3
"""Synchronise pipeline outputs into the deployable Next.js frontend.

Supported input formats:
1) strict-real pipeline output directory containing:
   - danh_muc_uu_tien_ra_pha.csv
   - ket_qua.json
   - figures/*.png
2) bundled historical-priority product directory containing:
   - data/priority_areas_top1000.csv
   - data/priority_grid_compact.json
   - figures/*.png

The web UI uses plain-language field names while preserving technical provenance in
metadata. No conversion creates P(UXO) or field-verification claims.
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def _jsonable(v):
    if pd.isna(v): return None
    if hasattr(v,"item"):
        try:return v.item()
        except Exception:pass
    return v


def _load_ground_truth(src:Path):
    candidates=[src/"data"/"ground_truth_validation.json", src/"ground_truth_validation.json"]
    for p in candidates:
        if p.exists():
            try:return json.loads(p.read_text(encoding="utf-8"))
            except Exception:pass
    return {"available":False,"field_verified":False,"spatial_layers_loaded":0,"message":"Chưa có dữ liệu xác minh thực địa không gian trong snapshot này."}


def _copy_figures(src:Path):
    dst=ROOT/"public"/"figures"; dst.mkdir(parents=True,exist_ok=True)
    for old in dst.glob("*.png"): old.unlink()
    copied=[]
    if src.exists():
        for p in sorted(src.glob("*.png")):
            shutil.copy2(p,dst/p.name); copied.append(p.name)
    return copied


def _sync_strict_real(src:Path):
    df=pd.read_csv(src/"danh_muc_uu_tien_ra_pha.csv").sort_values("thu_tu_uu_tien")
    raw=json.loads((src/"ket_qua.json").read_text(encoding="utf-8"))
    rows=[]
    for r in df.itertuples(index=False):
        rows.append({
            "rank":int(r.thu_tu_uu_tien),
            "cell_id":str(getattr(r,"cell_id",f"GRID_CELL_{int(r.chi_so_o_luoi)}")),
            "longitude":float(r.kinh_do),"latitude":float(r.vi_do),
            "priority_score":float(r.chi_so_uu_tien),"priority_level":str(r.muc_uu_tien),
            "airstrike_evidence_score":float(getattr(r,"diem_bang_chung_khong_kich",0.0)),
            "crater_evidence_score":float(getattr(r,"diem_bang_chung_ho_bom",0.0)),
            "spatial_context_score":float(getattr(r,"diem_boi_canh_khong_gian",0.0)),
            "evidence_pattern":"Bằng chứng lịch sử + bối cảnh không gian",
            "airstrike_records":int(round(float(getattr(r,"so_ho_so_khong_kich",0)))),
            "airstrike_record_density":0.0,
            "recorded_weapons_density":float(getattr(r,"tai_trong_bom_ghi_nhan_tan",0.0)),
            "craters_in_cell":int(getattr(r,"so_ho_bom_phat_hien",0)),
            "craters_within_300m":int(round(float(getattr(r,"so_ho_bom_300m",0)))),
            "crater_density_per_km2":0.0,"mean_crater_diameter_m":None,
            "elevation_m":_jsonable(getattr(r,"do_cao_m",None)),
            "slope_deg":_jsonable(getattr(r,"do_doc_do",None)),
            "population_count":_jsonable(getattr(r,"dan_so_uoc_tinh_o",None)),
            "distance_to_settlement_m":_jsonable(getattr(r,"khoang_cach_khu_dan_cu_m",None)),
            "field_verified":False,"is_probability":False,
        })
    figures=_copy_figures(src/"figures")
    results={
        "mode":"strict_real_observed_inputs",
        "title":"Xếp hạng ưu tiên khảo sát/rà phá từ dữ liệu công khai",
        "question":"Khu vực nào nên được khảo sát/rà phá trước?",
        "cells":int(raw.get("so_o_luoi",len(df))),
        "airstrike_records_in_aoi":int(raw.get("so_thor_missions",0)),
        "recorded_weapons_in_aoi":0,
        "craters_in_aoi":int(raw.get("so_ho_bom_kh9_trong_vung",0)),
        "cells_with_craters":int((df.get("so_ho_bom_phat_hien",pd.Series(dtype=float))>0).sum()),
        "priority_score_max":float(df.chi_so_uu_tien.max()),
        "top20_evidence_coverage":float(raw.get("tap_trung_diem_uu_tien",{}).get("top_20pct",0)),
        "field_verified":False,"is_probability":False,"grid_resolution_m":100,"hotspot_spacing_m":0,
        "sources":[
            {"label":"Hồ sơ không kích lịch sử","technical":"THOR — Theater History of Operations Reports"},
            {"label":"Dấu vết hố bom từ ảnh vệ tinh lịch sử","technical":"KH-9 HEXAGON crater dataset"},
            {"label":"Địa hình, sử dụng đất và phơi nhiễm","technical":"Copernicus DEM · ESA WorldCover · OSM · WorldPop · SoilGrids"},
        ],
        "figures":[{"file":f,"title":f.replace("_"," ").replace(".png",""),"caption":"Figure được sinh từ strict-real pipeline."} for f in figures],
        "warning":"Chỉ số ưu tiên là chỉ số tương đối từ dữ liệu quan sát; không phải xác suất UXO. Xác minh thực địa chỉ được hiển thị khi có record không gian độc lập.",
        "ground_truth":_load_ground_truth(src),
    }
    labels=list(dict.fromkeys(r["priority_level"] for r in rows))
    lookup={
        "schema":["lon","lat","priority","class","airstrike_score","crater_score","airstrike_records","craters","craters_300m"],
        "class_labels":labels,
        "cell_ids":[r["cell_id"] for r in rows],
        "rows":[[r["longitude"],r["latitude"],r["priority_score"],labels.index(r["priority_level"]),
                 r["airstrike_evidence_score"],r["crater_evidence_score"],r["airstrike_records"],
                 r["craters_in_cell"],r["craters_within_300m"]] for r in rows],
    }
    return rows,results,lookup


def _sync_bundled(src:Path):
    # This mode expects web-ready data already generated by build_final_web_data.py.
    priority_path=src/"web"/"priority.json"
    results_path=src/"web"/"results.json"
    lookup_path=src/"web"/"lookup_grid.json"
    if not all(p.exists() for p in [priority_path,results_path,lookup_path]):
        raise SystemExit(f"Thiếu priority/results/lookup_grid trong {src / 'web'}.")
    rows=json.loads(priority_path.read_text(encoding="utf-8")); results=json.loads(results_path.read_text(encoding="utf-8"))
    lookup=json.loads(lookup_path.read_text(encoding="utf-8"))
    if len(lookup["rows"]) != results["cells"]:
        raise ValueError("Lưới tra cứu không khớp số ô phân tích.")
    _copy_figures(src/"figures")
    return rows,results,lookup


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("output_dir",nargs="?",default="outputs_final");args=ap.parse_args()
    src=Path(args.output_dir); src=src if src.is_absolute() else (ROOT/src).resolve()
    if (src/"danh_muc_uu_tien_ra_pha.csv").exists() and (src/"ket_qua.json").exists():
        rows,results,lookup=_sync_strict_real(src); mode="strict-real"
    elif (src/"data"/"priority_areas_top1000.csv").exists():
        rows,results,lookup=_sync_bundled(src); mode="bundled-real-historical"
    else:
        raise SystemExit(f"Không nhận diện được output tại {src}")
    data_dir=ROOT/"src"/"data"; data_dir.mkdir(parents=True,exist_ok=True)
    (data_dir/"priority.json").write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (data_dir/"results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    public_dir=ROOT/"public"/"data"; public_dir.mkdir(parents=True,exist_ok=True)
    (public_dir/"lookup_grid.json").write_text(json.dumps(lookup,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (public_dir/"ground_truth_validation.json").write_text(json.dumps(results["ground_truth"],ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","mode":mode,"rows":len(rows),"source":str(src)},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
