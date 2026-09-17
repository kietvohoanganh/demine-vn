"""Regression checks use temporary fixtures; production data is never replaced."""
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    return runpy.run_path(str(ROOT / 'scripts' / name))


class DownloadTests(unittest.TestCase):
    def valid_tiff(self):
        with MemoryFile() as mem:
            with mem.open(driver='GTiff', width=2, height=2, count=1, dtype='uint8',
                          crs='EPSG:4326', transform=from_origin(106, 17, .01, .01)) as ds:
                ds.write(np.ones((1, 2, 2), dtype='uint8'))
            return mem.read()

    def response(self, payload, expected=None):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'Content-Length': str(len(payload) if expected is None else expected)}
        response.iter_content.return_value = [payload]
        return response

    def test_corrupt_large_cache_is_replaced_and_valid_cache_is_reused(self):
        download = script('fetch_real_geospatial.py')['_download']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worldpop.tif'
            path.write_bytes(b'broken' * 200000)
            with patch('requests.get', return_value=self.response(self.valid_tiff())) as get:
                download('https://example.invalid/worldpop.tif', path)
                get.assert_called_once()
            with rasterio.open(path) as ds:
                self.assertEqual(int(ds.read(1).sum()), 4)
            with patch('requests.get') as get:
                download('https://example.invalid/worldpop.tif', path)
                get.assert_not_called()

    def test_incomplete_download_does_not_publish_partial_file(self):
        download = script('fetch_real_geospatial.py')['_download']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worldpop.tif'
            path.write_bytes(b'old-broken-file')
            with patch('requests.get', return_value=self.response(b'incomplete', expected=100)):
                with self.assertRaises(OSError):
                    download('https://example.invalid/worldpop.tif', path)
            self.assertEqual(path.read_bytes(), b'old-broken-file')
            self.assertFalse(path.with_suffix('.tif.part').exists())


class DataPipelineTests(unittest.TestCase):
    def test_thor_preparation_replaces_file_consumed_by_pipeline(self):
        prepare = script('prepare_thor_quang_tri.py')['process_thor']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'input.csv'
            pd.DataFrame({
                'tgtlatdd_ddd_wgs84': [16.8, 16.81],
                'tgtlonddd_ddd_wgs84': [106.95, 106.96],
                'numweaponsdelivered': [2, 3], 'weapontypeweight': [500, 750],
            }).to_csv(raw, index=False)
            output = root / 'output'; output.mkdir()
            (output / 'thor_quang_tri_missions.csv').write_text('stale')
            prepare(raw, output, chunksize=1)
            df = pd.read_csv(output / 'thor_quang_tri_missions.csv')
            self.assertEqual(len(df), 2)
            self.assertEqual(df.record_n_bombs.tolist(), [2, 3])
            self.assertTrue((df.recorded_tonnage_t > 0).all())
            summary = json.loads((output / 'thor_quang_tri_summary.json').read_text())
            self.assertEqual(summary['raw_target_records_in_demine_bbox'], 2)

    def test_switching_modes_keeps_lookup_and_priority_in_sync(self):
        main = script('sync_outputs.py')['main']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'strict'; source.mkdir()
            pd.DataFrame([{
                'thu_tu_uu_tien': i + 1, 'chi_so_o_luoi': i,
                'cell_id': f'GRID100_C00{i}_R000', 'kinh_do': 106.85 + i * .001,
                'vi_do': 16.72, 'chi_so_uu_tien': .8 - i * .2, 'muc_uu_tien': 'Cao',
                'so_ho_so_khong_kich': 3, 'so_ho_bom_phat_hien': 2,
                'diem_bang_chung_khong_kich': .7, 'diem_bang_chung_ho_bom': .6,
            } for i in range(2)]).to_csv(source / 'danh_muc_uu_tien_ra_pha.csv', index=False)
            (source / 'ket_qua.json').write_text(json.dumps({'so_o_luoi': 2}))
            with patch.dict(main.__globals__, {'ROOT': root}), patch('sys.argv', ['sync', str(source)]):
                main()
            rows = json.loads((root / 'src/data/priority.json').read_text())
            lookup = json.loads((root / 'public/data/lookup_grid.json').read_text())
            self.assertEqual(lookup['cell_ids'], [r['cell_id'] for r in rows])
            self.assertEqual([r[2] for r in lookup['rows']], [r['priority_score'] for r in rows])
            self.assertEqual(len(lookup['rows']), 2)
            # Use a non-default bundled source: no hard-coded outputs_final paths.
            bundled = root / 'another_snapshot'; (bundled / 'web').mkdir(parents=True)
            (bundled / 'data').mkdir()
            (bundled / 'data/priority_areas_top1000.csv').touch()
            for name in ['priority.json', 'results.json']:
                (bundled / 'web' / name).write_bytes((root / 'src/data' / name).read_bytes())
            lookup['cell_ids'] = ['new-cell-1', 'new-cell-2']
            for row, cell_id in zip(rows, lookup['cell_ids']):
                row['cell_id'] = cell_id
            (bundled / 'web/priority.json').write_text(json.dumps(rows))
            (bundled / 'web/lookup_grid.json').write_text(json.dumps(lookup))
            with patch.dict(main.__globals__, {'ROOT': root}), patch('sys.argv', ['sync', str(bundled)]):
                main()
            self.assertEqual(json.loads((root / 'public/data/lookup_grid.json').read_text()), lookup)


if __name__ == '__main__':
    unittest.main()
