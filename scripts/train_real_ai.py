#!/usr/bin/env python3
"""Train, spatially evaluate and export the real-data evidence ranker.

Run after fetch_ai_evidence.py. Never imports legacy simulated observations.
Public exports have aggregate evaluation and model scores, not raw EOD records.
"""
from pathlib import Path
import sys
import os
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import asdict
from collections import Counter
import numpy as np
import pandas as pd
from pyproj import Transformer
import joblib
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from demine.risk.learned import EvidenceRanker, LearnedConfig, build_features, FEATURE_NAMES, FEATURE_LABELS
from demine.evaluation.learned import spatial_folds, coverage, budget_selection, paired_fold_interval

SEED = 20260917
FRACTIONS = [.1, .2, .3]
OUT = ROOT / 'outputs_ai'
PUBLIC = ROOT / 'public/data/ai'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')


def clean_evidence(features, grid):
    """Use evidence geometry, deduplicate device IDs, then collapse to cells.

Keep task memberships for leakage prevention. A zero label means no retained
record in this source, never an observed absence of ordnance.
"""
    mapping = {(int(row[0]), int(row[1])): i for i, row in enumerate(grid)}
    transform = Transformer.from_crs(4326, 32648, always_xy=True)
    y = np.zeros(len(grid), dtype=int)
    tasks = [set() for _ in grid]
    audit = Counter(input_records=len(features))
    seen = set()
    retained = []
    for f in sorted(features, key=lambda f: f['attributes']['objectid']):
        a, g = f['attributes'], f.get('geometry') or {}
        if a.get('point_type') != 'Evidence Point':
            audit['excluded_reference_or_other_point'] += 1
            continue
        if a.get('ordnance_category') in {'Unknown', 'Small Arms Ammunitions', None, ''}:
            audit['excluded_unknown_or_small_arms'] += 1
            continue
        quantity = a.get('quantity')
        if not isinstance(quantity, (int, float)) or not np.isfinite(quantity) or quantity <= 0:
            audit['excluded_nonpositive_quantity'] += 1
            continue
        task = a.get('activity_id')
        guid = a.get('hazreducdeviceinfo_guid')
        if not task or not guid:
            audit['excluded_missing_identity'] += 1
            continue
        try:
            lon, lat = float(g['x']), float(g['y'])
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError('Invalid geometry')
            x, z = transform.transform(lon, lat)
            ax, az = transform.transform(float(a['longitude']), float(a['latitude']))
            if not np.isfinite([x, z, ax, az]).all() or np.hypot(x-ax, z-az) > 25:
                raise ValueError('Conflicting coordinates')
        except (KeyError, ValueError, TypeError):
            audit['excluded_invalid_or_conflicting_coordinates'] += 1
            continue
        i = mapping.get((int(np.floor(x/100)), int(np.floor(z/100))))
        if i is None:
            audit['excluded_outside_exact_grid'] += 1
            continue
        if guid in seen:
            audit['excluded_duplicate_device_id'] += 1
            continue
        seen.add(guid)
        tasks[i].add(str(task))
        y[i] = 1
        retained.append({'cell_index': i, 'task': str(task), 'year': a.get('year'),
                         'activity': a.get('activity_type'), 'device_id': guid})
    audit['retained_records'] = len(retained)
    audit['recorded_cells'] = int(y.sum())
    audit['background_cells'] = int((1-y).sum())
    audit['unique_tasks'] = len(set().union(*tasks))
    return y, tasks, dict(audit), retained


def sample_population(grid, path):
    import rasterio
    from rasterio.transform import rowcol
    from rasterio.windows import Window
    transform = Transformer.from_crs(32648, 4326, always_xy=True)
    lon, lat = transform.transform(grid[:,0]*100+50, grid[:,1]*100+50)
    with rasterio.open(path) as ds:
        project = Transformer.from_crs(4326, ds.crs, always_xy=True)
        x, y = project.transform(lon, lat)
        row, col = (np.asarray(v) for v in rowcol(ds.transform, x, y))
        if (row < 0).any() or (row >= ds.height).any() or (col < 0).any() or (col >= ds.width).any():
            raise ValueError('WorldPop does not cover this grid')
        window = Window(int(col.min()), int(row.min()), int(col.max()-col.min()+1), int(row.max()-row.min()+1))
        values = ds.read(1, window=window, masked=True)
        result = np.asarray(values[row-row.min(), col-col.min()].filled(np.nan), float)
        result[result < 0] = np.nan
    if not np.isfinite(result).any():
        raise ValueError('WorldPop sample has no valid values')
    return result


def main():
    OUT.mkdir(exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    grid_path = ROOT / 'outputs_final/data/priority_grid_compact.json'
    snapshot_path = ROOT / 'data/real/ai_evidence/items_found.json'
    manifest = json.loads((snapshot_path.parent / 'manifest.json').read_text())
    if sha(snapshot_path) != manifest['sha256']:
        raise ValueError('Evidence snapshot hash mismatch')
    obj = json.loads(grid_path.read_text())
    grid = np.asarray(obj['rows'], dtype=float)
    population_path = ROOT / 'data/real/geospatial/raw/worldpop_vnm_2020_100m.tif'
    population = sample_population(grid, population_path)
    X = build_features(grid, population)
    xy = grid[:, :2]*100+50
    y, tasks, audit, retained = clean_evidence(json.loads(snapshot_path.read_text())['features'], grid)
    print('Evidence audit:', json.dumps(audit), flush=True)
    if y.sum() < 100:
        raise ValueError('Too few recorded cells for this experiment')
    write_json(OUT / 'evidence_audit.json', audit)
    # Local-only audit: task IDs never copied to public/.
    write_json(OUT / 'training_observations.json', retained)
    cfg = LearnedConfig()
    names = {'random': 'Ngẫu nhiên (kỳ vọng)', 'thor': 'Chỉ THOR', 'kh9': 'Chỉ KH-9',
        'baseline': 'Công thức 50–50', 'logistic': 'Hồi quy logistic',
        'ai_thor': 'AI chỉ THOR', 'ai_kh9': 'AI chỉ KH-9', 'ai_population': 'AI chỉ dân số',
        'ai_history': 'AI hai nguồn lịch sử', 'ai': 'AI lịch sử + dân số'}
    predictions = {name: np.zeros(len(y)) for name in names}
    folds = []
    selected = {name: {str(f): np.zeros(len(y)) for f in FRACTIONS} for name in names}
    fold_assign = np.full(len(y), -1, dtype=int)
    importances = []
    split_records = []
    for fold_id, train, test in spatial_folds(xy, tasks, buffer_m=600):
        if y[train].sum() < 50 or y[test].sum() < 20:
            raise ValueError('Too few positives in a spatial fold')
        fold_assign[test] = fold_id
        split_records.append({'fold': fold_id, 'train_indices': np.flatnonzero(train).tolist(),
                              'test_indices': np.flatnonzero(test).tolist()})
        print(f'Fold {fold_id}: train={train.sum()}, test={test.sum()}, positives={y[test].sum()}', flush=True)
        models = {'ai': (EvidenceRanker(cfg), list(range(X.shape[1]))),
                  'ai_history': (EvidenceRanker(cfg), [0, 1, 2, 3, 4]),
                  'ai_population': (EvidenceRanker(cfg), [5]),
                  'ai_thor': (EvidenceRanker(cfg), [0, 2]),
                  'ai_kh9': (EvidenceRanker(cfg), [1, 3, 4])}
        scores = {'random': np.zeros(test.sum()), 'thor': grid[test, 4],
                  'kh9': grid[test, 5], 'baseline': grid[test, 2]}
        for name, (model, columns) in models.items():
            model.fit(X[train][:, columns], y[train])
            scores[name] = model.predict_ranking_score(X[test][:, columns])
        logistic = make_pipeline(SimpleImputer(strategy='median', add_indicator=True), StandardScaler(), LogisticRegression(max_iter=1000, random_state=SEED))
        logistic.fit(X[train], y[train])
        scores['logistic'] = logistic.predict_proba(X[test])[:, 1]
        metrics = {}
        for name, score in scores.items():
            predictions[name][test] = score
            metrics[name] = {}
            for frac in FRACTIONS:
                selection = budget_selection(score, frac)
                selected[name][str(frac)][test] = selection
                metrics[name][str(frac)] = float(selection @ y[test] / y[test].sum())
        folds.append({'fold': fold_id, 'name': ['Tây Nam', 'Đông Nam', 'Tây Bắc', 'Đông Bắc'][fold_id],
            'train_cells': int(train.sum()), 'test_cells': int(test.sum()),
            'excluded_train_cells': int((~test & ~train).sum()),
            'train_recorded_cells': int(y[train].sum()), 'test_recorded_cells': int(y[test].sum()),
            'metrics': metrics})
        base = coverage(scores['ai'], y[test], .2)
        rng = np.random.default_rng(SEED + fold_id)
        for j in range(X.shape[1]):
            drops = []
            for _ in range(3):
                permuted = X[test].copy()
                rng.shuffle(permuted[:, j])
                drops.append(base-coverage(models['ai'][0].predict_ranking_score(permuted), y[test], .2))
            importances.append((j, float(np.mean(drops)), int(y[test].sum())))
    if (fold_assign < 0).any():
        raise ValueError('Incomplete held-out predictions')
    table = []
    for name, label in names.items():
        row = {'id': name, 'label': label}
        for f in FRACTIONS:
            row[f'coverage_{int(f*100)}'] = float(selected[name][str(f)] @ y / y.sum())
        table.append(row)
    ai20 = next(r for r in table if r['id'] == 'ai')['coverage_20']
    base20 = next(r for r in table if r['id'] == 'baseline')['coverage_20']
    positives = [f['test_recorded_cells'] for f in folds]
    interval = paired_fold_interval(
        [f['metrics']['ai']['0.2']*p for f, p in zip(folds, positives)],
        [f['metrics']['baseline']['0.2']*p for f, p in zip(folds, positives)], positives)
    feature_importance = []
    for j, label in enumerate(FEATURE_LABELS):
        entries = [(drop, count) for k, drop, count in importances if k == j]
        feature_importance.append({'feature': FEATURE_NAMES[j], 'label': label,
            'coverage_drop_20': float(np.average([v for v, _ in entries], weights=[w for _, w in entries]))})
    feature_importance.sort(key=lambda v: v['coverage_drop_20'], reverse=True)
    # Final inference model is fitted AFTER evaluating the fixed design. Its
    # in-sample map predictions are never reused as held-out test metrics.
    final = EvidenceRanker(cfg).fit(X, y)
    final_scores = final.predict_ranking_score(X)
    model_path = OUT / 'evidence_ranker.joblib'
    joblib.dump({'model': final, 'feature_names': FEATURE_NAMES, 'config': asdict(cfg),
                 'target': 'recorded_evidence_vs_unlabelled_background'}, model_path)
    reloaded = joblib.load(model_path)['model'].predict_ranking_score(X)
    if not np.array_equal(final_scores, reloaded):
        raise ValueError('Serialized model predictions changed')
    write_json(OUT / 'spatial_splits.json', split_records)
    np.savez_compressed(OUT / 'evaluation_arrays.npz', observed=y, fold=fold_assign,
        features=X, final_score=final_scores, **{f'oof_{k}': v for k, v in predictions.items()})
    summary = {'status': 'experimental', 'model': 'HistGradientBoostingClassifier',
        'trained_at': datetime.now(timezone.utc).isoformat(), 'cells': len(y),
        'is_probability': False, 'field_verified': False, 'config': asdict(cfg),
        'sklearn_version': sklearn.__version__, 'features': FEATURE_NAMES, 'audit': audit,
        'source': manifest['source'], 'source_retrieved_at': manifest['retrieved_at'],
        'source_sha256': manifest['sha256'], 'grid_sha256': sha(grid_path),
        'population_sha256': sha(population_path), 'population_valid_cells': int(np.isfinite(population).sum()),
        'population_source': 'https://data.worldpop.org/GIS/Population/Global_2015_2030/R2024B/2020/VNM/v1/100m/constrained/vnm_pop_2020_CN_100m_R2024B_v1.tif',
        'experiment_stage': 'Exploratory: WorldPop variant added after inspecting history-only CV. No untouched confirmatory test.',
        'model_sha256': sha(model_path), 'splits_sha256': sha(OUT / 'spatial_splits.json'),
        'base_lookup_sha256': sha(ROOT / 'outputs_final/web/lookup_grid.json'),
        'evaluation': {'method': 'four_spatial_quadrants_task_exclusion_600m_buffer',
            'folds': folds, 'comparison': table, 'delta_20': ai20-base20,
            'delta_20_interval': interval, 'bootstrap_regions': 4,
            'metric': 'Coverage of unique held-out recorded cells at equal area budget per quadrant',
            'feature_importance': feature_importance},
        'limitations': [
            'Học vị trí có ghi nhận trong nguồn công khai; chịu thiên lệch nơi đã khảo sát và báo cáo.',
            'Đây là so sánh thăm dò; đã bổ sung biến thể dân số sau lượt thử lịch sử. Chưa có tập kiểm tra xác nhận chưa từng xem.',
            'WorldPop 2020 là bối cảnh dân cư hồi cứu, có thể phản ánh khả năng được khảo sát; không phải bằng chứng vật nổ hay kiểm chứng dự báo theo thời gian.',
            'Ô chưa có bản ghi là dữ liệu chưa gán nhãn, không phải ô đã xác nhận không có vật nổ.',
            'Ghi nhận vật nổ đã xử lý trong quá khứ không chứng minh hiện tại còn vật nổ.',
            'Chưa biết đầy đủ sai số định vị và độ phủ ảnh KH-9; số hố bom bằng 0 chỉ là không có dự đoán trong nguồn.',
            'Chưa kiểm chứng bằng khảo sát mới, dữ liệu tai nạn độc lập hoặc địa bàn ngoài vùng nghiên cứu.',
            'Khoảng bootstrap từ bốn vùng chỉ mang tính tham khảo; chưa loại bỏ toàn bộ phụ thuộc không gian.'
        ]}
    write_json(OUT / 'results.json', summary)
    write_json(PUBLIC / 'summary.json', summary)
    transform = Transformer.from_crs(32648, 4326, always_xy=True)
    lon, lat = transform.transform(xy[:, 0], xy[:, 1])
    # Level thresholds defined by score quantiles; ties remain in one level.
    cuts = np.quantile(final_scores, [.2, .4, .7, .9])
    classes = np.searchsorted(cuts, final_scores, side='right')
    order = np.argsort(-final_scores, kind='stable')
    rows = []
    for rank, i in enumerate(order[:1000], 1):
        e, n = map(int, grid[i, :2])
        rows.append({'rank': rank, 'cell_id': f'U48N_100_E{e}_N{n}',
            'longitude': float(lon[i]), 'latitude': float(lat[i]),
            'priority_score': float(final_scores[i]), 'priority_level': obj['class_labels'][classes[i]],
            'airstrike_evidence_score': float(grid[i, 4]), 'crater_evidence_score': float(grid[i, 5]),
            'evidence_pattern': 'Mô hình học từ bằng chứng lịch sử và bối cảnh dân cư',
            'airstrike_records': int(grid[i, 6]), 'airstrike_record_density': None,
            'recorded_weapons_density': None, 'craters_in_cell': int(grid[i, 7]),
            'craters_within_300m': int(grid[i, 8]), 'crater_density_per_km2': float(grid[i, 7]*100),
            'mean_crater_diameter_m': None, 'baseline_score': float(grid[i, 2]),
            'population_count': None if not np.isfinite(population[i]) else float(population[i]),
            'field_verified': False, 'is_probability': False})
    write_json(PUBLIC / 'priority.json', {'model_sha256': summary['model_sha256'], 'rows': rows})
    lookup = {'model_sha256': summary['model_sha256'], 'schema': ['lon','lat','priority','class','airstrike_score','crater_score',
                        'airstrike_records','craters','craters_300m','e','n'],
        'class_labels': obj['class_labels'],
        'rows': [[round(float(lon[i]),6), round(float(lat[i]),6), round(float(final_scores[i]),8),
                  int(classes[i]), *map(float, grid[i,4:9]), int(grid[i,0]), int(grid[i,1])]
                 for i in range(len(y))]}
    (PUBLIC / 'lookup_grid.json').write_text(json.dumps(lookup, separators=(',', ':')))
    pd.DataFrame(table).to_csv(OUT / 'comparison.csv', index=False)
    report = ['# AI trên dữ liệu thực — kết quả chạy', '',
        f"Đã huấn luyện {summary['model']} trên {len(y):,} ô, trong đó {int(y.sum()):,} ô có ghi nhận được giữ lại.",
        'Nhãn đích là có ghi nhận / chưa có ghi nhận trong nguồn; không phải còn / không còn vật nổ.', '',
        '| Phương pháp | Bao phủ tại 10% diện tích | 20% | 30% |', '|---|---:|---:|---:|']
    report += [f"| {r['label']} | {r['coverage_10']:.2%} | {r['coverage_20']:.2%} | {r['coverage_30']:.2%} |" for r in table]
    report += ['', 'Bốn vùng kiểm tra riêng, loại mẫu học cách vùng kiểm tra ≤600 m và nhiệm vụ xuất hiện ở cả hai tập.',
        'Tỷ lệ bao phủ gộp theo số ô có ghi nhận; ngân sách diện tích được áp dụng riêng trong mỗi vùng. Tại điểm hòa, dùng tỷ lệ lựa chọn kỳ vọng.',
        f'Chênh lệch AI − 50–50 tại 20%: {(ai20-base20)*100:.2f} điểm phần trăm; khoảng bootstrap tham khảo [{interval[0]*100:.2f}; {interval[1]*100:.2f}].',
        'Mô hình bản đồ được học lại trên toàn bộ dữ liệu sau đánh giá, không dùng điểm trên bản đồ để tính bảng kiểm tra.', '',
        '## Giới hạn', *['- '+s for s in summary['limitations']], '',
        '## Tái lập', '`.venv/bin/python scripts/fetch_ai_evidence.py`', '`.venv/bin/python scripts/train_real_ai.py`',
        'Snapshot, cấu hình, mã băm và tập chia được lưu cùng kết quả; không đưa bản ghi thực địa chi tiết lên web.']
    (OUT / 'REPORT.md').write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps({'comparison': table, 'delta_20_interval': interval}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=4):
        main()
