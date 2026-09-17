from pathlib import Path
import json


def test_bundled_web_contract():
    root=Path(__file__).resolve().parents[1]
    results=json.loads((root/'src/data/results.json').read_text(encoding='utf-8'))
    priority=json.loads((root/'src/data/priority.json').read_text(encoding='utf-8'))
    lookup=json.loads((root/'public/data/lookup_grid.json').read_text(encoding='utf-8'))
    assert results['field_verified'] is False
    assert results['is_probability'] is False
    assert len(priority)==1000
    assert len(lookup['rows'])==39870
    assert all(r['field_verified'] is False and r['is_probability'] is False for r in priority)
    assert len(results['figures'])==7
    for fig in results['figures']:
        assert (root/'public/figures'/fig['file']).exists()


def test_ground_truth_contract_present():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / 'outputs_final' / 'data' / 'ground_truth_validation.json').read_text(encoding='utf-8'))
    assert result['available'] is False
    assert result['field_verified'] is False
    assert result['is_probability'] is False
