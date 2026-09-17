#!/usr/bin/env python3
"""Audit ranking sensitivity. These diagnostics do not measure field accuracy."""
from pathlib import Path
import argparse
import json
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]


def audit(grid_path):
    obj = json.loads(Path(grid_path).read_text(encoding='utf-8'))
    a = np.asarray(obj['rows'], dtype=float)
    col = {name: i for i, name in enumerate(obj['schema'])}
    historical = a[:, col['priority']]
    thor, kh9 = a[:, col['thor']], a[:, col['kh9']]
    n = int(np.ceil(.2 * len(a)))
    baseline = set(np.argsort(-historical, kind='stable')[:n].tolist())
    variants = []
    for weight in [.25, .5, .75]:
        score = weight * thor + (1 - weight) * kh9
        selected = set(np.argsort(-score, kind='stable')[:n].tolist())
        variants.append({
            'thor_weight': weight,
            'kh9_weight': 1 - weight,
            'top20_jaccard_vs_published': len(selected & baseline) / len(selected | baseline),
            'top20_retained_fraction': len(selected & baseline) / n,
            'rank_spearman_vs_published': float(spearmanr(score, historical).statistic),
        })
    return {
        'cells': len(a), 'top20_cells': n,
        'independent_field_validation': False,
        'interpretation': 'Sensitivity and internal consistency only; no UXO accuracy, recovery or operational gain is measured.',
        'source_spearman': float(spearmanr(thor, kh9).statistic),
        'published_score_vs_equal_weight_max_abs_error': float(np.abs(historical - .5 * (thor + kh9)).max()),
        'top20_share_of_own_score': float(np.sort(historical)[::-1][:n].sum() / historical.sum()),
        'weight_sensitivity': variants,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--grid', type=Path, default=ROOT / 'outputs_final/data/priority_grid_compact.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs_audit/priority_evidence_audit.json')
    args = parser.parse_args()
    result = audit(args.grid)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
