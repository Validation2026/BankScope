from copy import deepcopy
import json
import pytest

from src.core import DATA
from src.quality_gate import check_publication, check_snapshot


def snapshot():
    return json.loads((DATA / 'snapshot.json').read_text(encoding='utf-8'))


def test_existing_publication_passes_quality_gate():
    result = check_publication()
    assert result['weekly_records'] >= 66
    from src.core import IDS
    doc=snapshot()
    credit=[r for r in doc['weekly'] if r['metric_id'] in IDS]
    assert len(credit)==66*len({r['period'] for r in credit})
    assert result['bddk_other_section_identity_checks'] >= 0
    assert result['bddk_credit_identity_checks'] == result['weekly_periods'] * 3 * 7
    assert result['complete'] is False


def test_reject_misleading_completeness():
    doc = snapshot()
    doc['quality']['status'] = 'complete'
    with pytest.raises(ValueError, match='marketed as complete'):
        check_snapshot(doc)


def test_reject_unverified_financial_row():
    doc = snapshot()
    doc['weekly'][0]['status'] = 'estimated'
    with pytest.raises(ValueError, match='Unverified'):
        check_snapshot(doc)


def test_reject_mismatched_currency_total():
    doc = snapshot()
    row = next(r for r in doc['weekly'] if r['currency'] == 'TOTAL')
    row['value'] += 100
    with pytest.raises(ValueError, match='(reconciliation failed|accounting identity failed)'):
        check_snapshot(doc)


def test_reject_unconfirmed_banks():
    doc = snapshot()
    doc['quality']['bank_count_verified'] = 10
    with pytest.raises(ValueError, match='bank count'):
        check_snapshot(doc)


def test_js_json_mismatch_fails(tmp_path):
    doc = snapshot()
    (tmp_path / 'snapshot.json').write_text(json.dumps(doc), encoding='utf-8')
    (tmp_path / 'snapshot.js').write_text('window.BANKSCOPE_DATA = {};', encoding='utf-8')
    (tmp_path / 'audit.json').write_text(json.dumps({
        'quality': doc['quality'], 'run_at': doc['generated_at']}), encoding='utf-8')
    with pytest.raises(ValueError, match='not identical'):
        check_publication(tmp_path)
