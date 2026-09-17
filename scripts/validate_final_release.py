#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
errors=[]

def need(p):
    p=ROOT/p
    if not p.exists(): errors.append(f"missing: {p.relative_to(ROOT)}")
    return p

required=[
    'app/page.tsx','app/layout.tsx','app/globals.css','components/Dashboard.tsx','components/MapPanel.tsx','components/types.ts',
    'src/data/results.json','src/data/priority.json','public/data/lookup_grid.json','package.json','next.config.mjs','tsconfig.json',
    'outputs_final/data/priority_grid_compact.json','outputs_final/data/priority_areas_top1000.csv'
]
for p in required: need(p)

results=json.loads(need('src/data/results.json').read_text(encoding='utf-8'))
priority=json.loads(need('src/data/priority.json').read_text(encoding='utf-8'))
lookup=json.loads(need('public/data/lookup_grid.json').read_text(encoding='utf-8'))
if len(priority)!=1000: errors.append(f'priority rows != 1000: {len(priority)}')
if len(lookup.get('rows',[]))!=39870: errors.append(f'lookup rows != 39870: {len(lookup.get("rows",[]))}')
if results.get('field_verified') is not False: errors.append('field_verified must be false')
if results.get('is_probability') is not False: errors.append('is_probability must be false')
if not all(r.get('field_verified') is False and r.get('is_probability') is False for r in priority): errors.append('priority flags invalid')

figs=results.get('figures',[])
if len(figs)!=7: errors.append(f'expected 7 figures, got {len(figs)}')
for f in figs:
    p=need(Path('public/figures')/f['file'])
    try:
        with Image.open(p) as im:
            if im.width<500 or im.height<300: errors.append(f'figure too small: {p.name} {im.size}')
    except Exception as exc: errors.append(f'figure unreadable: {p.name}: {exc}')

page=need('app/page.tsx').read_text(encoding='utf-8')
if '@/components/Dashboard' in page: errors.append('page.tsx still uses fragile alias import')
map_code=need('components/MapPanel.tsx').read_text(encoding='utf-8')
for term in ['OpenStreetMap','server.arcgisonline.com','Math.min(300,rows.length)']:
    if term not in map_code: errors.append(f'map feature missing: {term}')

if errors:
    print(json.dumps({'status':'FAIL','errors':errors},ensure_ascii=False,indent=2)); sys.exit(1)
print(json.dumps({'status':'PASS','priority_rows':len(priority),'lookup_rows':len(lookup['rows']),'figures':len(figs),'field_verified':False,'is_probability':False},ensure_ascii=False,indent=2))
