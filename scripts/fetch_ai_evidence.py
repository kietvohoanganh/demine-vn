#!/usr/bin/env python3
"""Fetch minimal public QTMAC/Stimson evidence attributes; never staff details.

Raw records stay local, outside the web bundle. IDs are pinned before paging so
missing/duplicated pages cannot silently produce a partial training snapshot.
"""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data/real/ai_evidence'
URL = 'https://gis.stimson.org/server/rest/services/Hosted/Items_Found/FeatureServer/0'
FIELDS = ['objectid', 'hazreducdeviceinfo_guid', 'quantity', 'longitude', 'latitude',
          'year', 'activity_id', 'activity_type', 'point_type', 'ordnance_category']


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    path = DEST / 'items_found.json'
    manifest_path = DEST / 'manifest.json'
    if path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256']:
            print('Using verified local snapshot:', manifest['records'])
            return
        raise ValueError('Evidence snapshot hash mismatch; inspect before replacing.')
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1,
                  status_forcelist=[429, 500, 502, 503, 504])))

    def query(params):
        r = session.get(URL + '/query', params={'f': 'json', **params}, timeout=60)
        r.raise_for_status()
        obj = r.json()
        if 'error' in obj:
            raise ValueError(obj['error'])
        return obj

    # Include all point types for an auditable exclusion count, then filter locally.
    lookup = json.loads((ROOT / 'outputs_final/web/lookup_grid.json').read_text())['rows']
    bbox = [min(r[0] for r in lookup)-.0005, min(r[1] for r in lookup)-.0005,
            max(r[0] for r in lookup)+.0005, max(r[1] for r in lookup)+.0005]
    ids = sorted(query({'where': '1=1', 'returnIdsOnly': 'true',
        'geometry': ','.join(map(str, bbox)), 'geometryType': 'esriGeometryEnvelope',
        'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects'})['objectIds'])
    features = []
    for offset in range(0, len(ids), 800):
        batch = ids[offset:offset+800]
        data = query({'objectIds': ','.join(map(str, batch)), 'outFields': ','.join(FIELDS),
                      'returnGeometry': 'true', 'outSR': 4326})
        got = data['features']
        if data.get('exceededTransferLimit') or sorted(f['attributes']['objectid'] for f in got) != batch:
            raise ValueError('Incomplete or inconsistent evidence page')
        features.extend(got)
        print(f'Fetched {len(features)}/{len(ids)}', flush=True)
    payload = json.dumps({'source': URL, 'features': features}, ensure_ascii=False,
                         separators=(',', ':')).encode()
    temp = path.with_suffix('.part')
    temp.write_bytes(payload)
    temp.replace(path)
    manifest = {'source': URL, 'provider': 'QTMAC via Stimson War Legacies Dashboard',
        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'bbox': bbox,
        'fields': FIELDS, 'records': len(features), 'sha256': hashlib.sha256(payload).hexdigest(),
        'use': 'Local research snapshot; web exports only model outputs and aggregate evaluation.'}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('Saved', path)


if __name__ == '__main__':
    main()
