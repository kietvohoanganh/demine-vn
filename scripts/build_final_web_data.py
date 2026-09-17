#!/usr/bin/env python3
"""Build deploy-ready web JSON from the bundled real historical priority product."""
from __future__ import annotations
import json,re,shutil
from pathlib import Path
import pandas as pd
from pyproj import Transformer

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'outputs_final'/'data'
WEB=ROOT/'outputs_final'/'web'
WEB.mkdir(parents=True,exist_ok=True)
tr=Transformer.from_crs(32648,4326,always_xy=True)

def ll(e,n):
    lon,lat=tr.transform(float(e)*100+50,float(n)*100+50)
    return float(lon),float(lat)

top=pd.read_csv(DATA/'priority_areas_top1000.csv')
rows=[]
for r in top.itertuples(index=False):
    m=re.search(r'_E(\d+)_N(\d+)$',str(r.cell_id)); e=int(m.group(1)); n=int(m.group(2)); lon,lat=ll(e,n)
    rows.append({
        'rank':int(r.priority_rank_all_cells),'cell_id':str(r.cell_id),'longitude':lon,'latitude':lat,
        'priority_score':float(r.priority_score_0_1),'priority_level':str(r.priority_level),
        'airstrike_evidence_score':float(r.thor_evidence_score_0_1),'crater_evidence_score':float(r.kh9_crater_evidence_score_0_1),
        'evidence_pattern':str(r.evidence_pattern),'airstrike_records':int(r.thor_record_count),
        'airstrike_record_density':float(r.record_kernel_per_km2),'recorded_weapons_density':float(r.known_weapons_kernel_per_km2),
        'craters_in_cell':int(r.crater_count),'craters_within_300m':int(r.craters_300m),
        'crater_density_per_km2':float(r.crater_density_per_km2),'mean_crater_diameter_m':None if pd.isna(r.mean_crater_diameter_m) else float(r.mean_crater_diameter_m),
        'field_verified':False,'is_probability':False,
    })
(WEB/'priority.json').write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

compact=json.loads((DATA/'priority_grid_compact.json').read_text(encoding='utf-8'))
lookup=[]
for vals in compact['rows']:
    rec=dict(zip(compact['schema'],vals)); e=int(rec['e']); n=int(rec['n']); lon,lat=ll(e,n)
    lookup.append([round(lon,6),round(lat,6),float(rec['priority']),int(rec['class']),float(rec['thor']),float(rec['kh9']),int(rec['thor_records']),int(rec['craters']),int(rec['craters_300m']),e,n])
lookup_obj={'schema':['lon','lat','priority','class','airstrike_score','crater_score','airstrike_records','craters','craters_300m','e','n'],'class_labels':compact['class_labels'],'rows':lookup}
(WEB/'lookup_grid.json').write_text(json.dumps(lookup_obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')

gt_path=DATA/'ground_truth_validation.json'
if gt_path.exists():
    ground_truth=json.loads(gt_path.read_text(encoding='utf-8'))
else:
    ground_truth={'available':False,'field_verified':False,'spatial_layers_loaded':0,'message':'Chưa có dữ liệu xác minh thực địa không gian trong snapshot này.'}

results={
  'mode':'real_historical_evidence','title':'Hỗ trợ xếp thứ tự ưu tiên khảo sát bom mìn từ dữ liệu thực','question':'Khu vực nào nên được khảo sát trước?',
  'cells':39870,'airstrike_records_in_aoi':28781,'recorded_weapons_in_aoi':376265,'craters_in_aoi':61361,'cells_with_craters':21724,
  'priority_score_max':0.9846689240030098,'top20_evidence_coverage':0.30894506365672886,'field_verified':False,'is_probability':False,
  'grid_resolution_m':100,'hotspot_spacing_m':300,
  'sources':[
    {'label':'Hồ sơ không kích giải mật','technical':'THOR — Theater History of Operations Reports'},
    {'label':'Dấu vết hố bom từ ảnh vệ tinh lịch sử','technical':'Kết quả nhận diện hố bom trên ảnh KH-9 HEXAGON'}],
  'figures':[
    {'file':'01_muc_tap_trung_bang_chung.png','title':'Mức tập trung bằng chứng lịch sử','caption':'Tỷ trọng điểm bằng chứng trong phần diện tích được ưu tiên khảo sát.'},
    {'file':'02_ban_do_uu_tien.png','title':'Bản đồ ưu tiên khảo sát','caption':'Phân bố chỉ số ưu tiên; các điểm đánh dấu là tâm ô phân tích.'},
    {'file':'03_ba_lop_thong_tin.png','title':'Ba lớp thông tin chính','caption':'Hồ sơ không kích giải mật, dấu vết hố bom lịch sử và chỉ số ưu tiên tổng hợp.'},
    {'file':'04_phan_bo_muc_uu_tien.png','title':'Phân bố mức ưu tiên','caption':'Số ô lưới thuộc từng mức ưu tiên trong toàn vùng nghiên cứu.'},
    {'file':'05_thanh_phan_diem_uu_tien.png','title':'Thành phần điểm ưu tiên','caption':'Đóng góp của hồ sơ không kích và dấu vết hố bom vào chỉ số ưu tiên.'},
    {'file':'06_top_khu_vuc_uu_tien.png','title':'Các khu vực ưu tiên cao nhất','caption':'So sánh chỉ số ưu tiên của các khu vực đứng đầu.'},
    {'file':'07_muc_dong_thuan_nguon.png','title':'Mức đồng thuận giữa hai nguồn','caption':'So sánh bằng chứng từ hồ sơ không kích với bằng chứng từ dấu vết hố bom.'}],
  'warning':'Chỉ số ưu tiên dùng để xếp thứ tự khảo sát, không phải xác suất còn bom mìn, vật nổ. Mức ưu tiên thấp không đồng nghĩa với đất an toàn.',
  'ground_truth':ground_truth}
(WEB/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

# Deploy-ready copies.
(ROOT/'src'/'data').mkdir(parents=True,exist_ok=True); (ROOT/'public'/'data').mkdir(parents=True,exist_ok=True); (ROOT/'public'/'figures').mkdir(parents=True,exist_ok=True)
shutil.copy2(WEB/'priority.json',ROOT/'src'/'data'/'priority.json'); shutil.copy2(WEB/'results.json',ROOT/'src'/'data'/'results.json'); shutil.copy2(WEB/'lookup_grid.json',ROOT/'public'/'data'/'lookup_grid.json')
if gt_path.exists(): shutil.copy2(gt_path,ROOT/'public'/'data'/'ground_truth_validation.json')
for old in (ROOT/'public'/'figures').glob('*.png'): old.unlink()
for p in sorted((ROOT/'outputs_final'/'figures').glob('*.png')): shutil.copy2(p,ROOT/'public'/'figures'/p.name)
print(json.dumps({'status':'PASS','priority_rows':len(rows),'lookup_rows':len(lookup),'figures':len(list((ROOT/'public'/'figures').glob('*.png')))},ensure_ascii=False,indent=2))
