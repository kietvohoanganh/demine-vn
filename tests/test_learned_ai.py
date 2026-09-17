"""Regression tests for evidence cleaning, leakage controls and shipped AI data."""
from pathlib import Path
import sys
import json
import hashlib
import unittest
import importlib.util
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from demine.evaluation.learned import spatial_folds, budget_selection, coverage
from demine.risk.learned import build_features, EvidenceRanker

spec = importlib.util.spec_from_file_location('train_real_ai', ROOT / 'scripts/train_real_ai.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class EvidenceTests(unittest.TestCase):
    def test_cleaning_excludes_reference_duplicates_and_outside_grid(self):
        tr = Transformer.from_crs(32648, 4326, always_xy=True)
        lon, lat = tr.transform(700050, 1850050)
        def record(i, **changes):
            a = {'objectid': i, 'hazreducdeviceinfo_guid': 'device-1', 'activity_id': 'task-1',
                 'point_type': 'Evidence Point', 'ordnance_category': 'Grenades',
                 'quantity': 1, 'longitude': lon, 'latitude': lat, **changes}
            return {'attributes': a, 'geometry': {'x': a['longitude'], 'y': a['latitude']}}
        records = [record(1), record(2), record(3, point_type='Reference Point'),
                   record(4, hazreducdeviceinfo_guid='other', longitude=108),
                   record(5, quantity=0), record(6, ordnance_category='Unknown')]
        y, tasks, audit, kept = pipeline.clean_evidence(records, [[7000,18500], [7001,18500]])
        self.assertEqual(y.tolist(), [1,0])
        self.assertEqual(tasks, [{'task-1'}, set()])
        self.assertEqual(len(kept), 1)
        self.assertEqual(audit['excluded_duplicate_device_id'], 1)
        self.assertEqual(audit['background_cells'], 1)

    def test_geometry_attribute_conflict_rejected(self):
        f = {'attributes': {'objectid':1,'hazreducdeviceinfo_guid':'a','activity_id':'t',
            'point_type':'Evidence Point','ordnance_category':'Grenades','quantity':1,
            'longitude':107,'latitude':16.8}, 'geometry':{'x':106.9,'y':16.8}}
        y, _, audit, _ = pipeline.clean_evidence([f], [[7000,18500]])
        self.assertEqual(int(y.sum()), 0)
        self.assertEqual(audit['excluded_invalid_or_conflicting_coordinates'], 1)

    def test_equal_scores_have_exact_area_budget_without_order_bias(self):
        scores=np.ones(11)
        self.assertAlmostEqual(budget_selection(scores,.2).sum(),2.2)
        self.assertAlmostEqual(coverage(scores,[1,0,0,1,0,0,1,0,0,0,0],.2),.2)
        selection=budget_selection([5,4,4,4,1],.4)
        np.testing.assert_allclose(selection,[1,1/3,1/3,1/3,0])

    def test_spatial_buffer_and_shared_tasks_excluded(self):
        coords=np.array([(x,y) for y in range(0,5000,500) for x in range(0,5000,500)])
        tasks=[set() for _ in coords]
        tasks[0]={'cross-region'};tasks[-1]={'cross-region'}
        all_test=[]
        for _,train,test in spatial_folds(coords,tasks,600):
            self.assertFalse((train & test).any())
            self.assertGreater(cKDTree(coords[test]).query(coords[train])[0].min(),600)
            train_tasks=set().union(*(tasks[i] for i in np.flatnonzero(train)))
            test_tasks=set().union(*(tasks[i] for i in np.flatnonzero(test)))
            self.assertFalse(train_tasks & test_tasks)
            all_test.extend(np.flatnonzero(test))
        self.assertEqual(sorted(all_test),list(range(len(coords))))

    def test_target_never_enters_features_and_population_missing_stays_missing(self):
        grid=np.array([[1,2,.9,4,.2,.4,3,5,7],[2,2,.1,0,.8,.6,4,2,8]],float)
        first=build_features(grid,[np.nan,10])
        grid[:,2:4]=0
        np.testing.assert_allclose(first,build_features(grid,[np.nan,10]),equal_nan=True)
        self.assertTrue(np.isnan(first[0,-1]))
        with self.assertRaises(ValueError):
            EvidenceRanker().fit(first,[1,1])

    def test_exported_model_map_and_summary_contract(self):
        directory=ROOT/'public/data/ai'
        summary=json.loads((directory/'summary.json').read_text())
        bundle=json.loads((directory/'priority.json').read_text())
        rows=bundle['rows']
        lookup=json.loads((directory/'lookup_grid.json').read_text())
        self.assertEqual(summary['cells'],len(lookup['rows']))
        self.assertFalse(summary['field_verified'])
        self.assertFalse(summary['is_probability'])
        self.assertEqual(bundle['model_sha256'],summary['model_sha256'])
        self.assertEqual(lookup['model_sha256'],summary['model_sha256'])
        self.assertEqual(summary['base_lookup_sha256'],hashlib.sha256((ROOT/'public/data/lookup_grid.json').read_bytes()).hexdigest())
        by_id={f'U48N_100_E{int(r[9])}_N{int(r[10])}':r for r in lookup['rows']}
        self.assertEqual(len(by_id),summary['cells'])
        self.assertEqual(len(rows),1000)
        for row in rows:
            r=by_id[row['cell_id']]
            self.assertAlmostEqual(row['priority_score'],r[2],places=7)
            self.assertEqual(row['priority_level'],lookup['class_labels'][r[3]])
        self.assertTrue(all(a['priority_score']>=b['priority_score'] for a,b in zip(rows,rows[1:])))
        random=next(r for r in summary['evaluation']['comparison'] if r['id']=='random')
        self.assertAlmostEqual(random['coverage_20'],.2)

    def test_actual_spatial_splits_and_metrics(self):
        grid=np.asarray(json.loads((ROOT/'outputs_final/data/priority_grid_compact.json').read_text())['rows'])
        retained=json.loads((ROOT/'outputs_ai/training_observations.json').read_text())
        tasks=[set() for _ in grid]
        for record in retained: tasks[record['cell_index']].add(record['task'])
        arrays=np.load(ROOT/'outputs_ai/evaluation_arrays.npz')
        summary=json.loads((ROOT/'outputs_ai/results.json').read_text())
        hits=0
        for fold,train,test in spatial_folds(grid[:,:2]*100+50,tasks):
            self.assertTrue((arrays['fold'][test]==fold).all())
            train_tasks=set().union(*(tasks[i] for i in np.flatnonzero(train)))
            test_tasks=set().union(*(tasks[i] for i in np.flatnonzero(test)))
            self.assertFalse(train_tasks & test_tasks)
            hits+=budget_selection(arrays['oof_ai'][test],.2) @ arrays['observed'][test]
        expected=next(r['coverage_20'] for r in summary['evaluation']['comparison'] if r['id']=='ai')
        self.assertAlmostEqual(hits/arrays['observed'].sum(),expected)


if __name__=='__main__': unittest.main()
