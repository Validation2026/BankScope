"""Verify that BankScope's static publication is internally consistent.

Run *after* refreshing and before committing/deploying a published snapshot.
Official source availability and completeness are separate checks. This module
must never promote an unverified metric to verified or fabricate missing data.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

from .core import DATA, validate_rows


def check_snapshot(snapshot: dict) -> dict:
    """Raise ValueError on unsafe data; return a small independent audit summary."""
    if not isinstance(snapshot, dict):
        raise ValueError('The publication must be a JSON object')
    for section in ('weekly', 'monthly', 'banks'):
        if not isinstance(snapshot.get(section), list):
            raise ValueError(f'Missing or invalid data section: {section}')
        validate_rows(snapshot[section])
    quality = snapshot.get('quality')
    if not isinstance(quality, dict):
        raise ValueError('Missing quality flags')
    for field in ('weekly_complete', 'monthly_complete', 'bank_financials_complete'):
        if type(quality.get(field)) is not bool:
            raise ValueError(f'Missing/ambiguous quality flag: {field}')
    if quality['bank_financials_complete'] and not snapshot['banks']:
        raise ValueError('Bank financials cannot be complete without verified rows')
    if quality['monthly_complete'] and not snapshot['monthly']:
        raise ValueError('Monthly data cannot be complete without verified rows')
    if quality['weekly_complete'] and not snapshot['weekly']:
        raise ValueError('Weekly data cannot be complete without verified rows')
    if quality.get('bank_count_verified') != len({r.get('bank_id') for r in snapshot['banks'] if r.get('bank_id')}):
        raise ValueError('Verified-bank count does not match the records')
    if quality.get('status') == 'complete' and not all(quality[x] for x in (
            'weekly_complete', 'monthly_complete', 'bank_financials_complete')):
        raise ValueError('Partial data cannot be marketed as complete')

    today = date.today()
    aggregate = defaultdict(dict)
    for section in ('weekly', 'monthly', 'banks'):
        for row in snapshot[section]:
            try:
                period = date.fromisoformat(row['period'])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError('Invalid reporting date') from exc
            if period > today:
                raise ValueError('A reported value cannot be from a future period')
            if isinstance(row.get('value'), bool) or not math.isfinite(row['value']):
                raise ValueError('A financial value must be a finite number')
            if row.get('status') not in ('official', 'verified', 'derived_verified'):
                raise ValueError('Unverified or unsourced value cannot be published')
            key = (section, row['source'], row['period'], row['scope'],
                   row['metric_id'], row.get('bank_id', ''))
            aggregate[key][row.get('currency', 'TOTAL')] = row['value']

    # BDDK TP and YP columns are both TRY equivalents; rounding can introduce
    # a small difference between the two and published TOTAL.
    for key, values in aggregate.items():
        if {'TP', 'YP', 'TOTAL'}.issubset(values):
            difference = abs(values['TP'] + values['YP'] - values['TOTAL'])
            if difference > 0.25:
                raise ValueError(f'TP + YP reconciliation failed: {key}, delta={difference}')
    return {
        'weekly_records': len(snapshot['weekly']),
        'monthly_records': len(snapshot['monthly']),
        'bank_records': len(snapshot['banks']),
        'weekly_periods': len({r['period'] for r in snapshot['weekly']}),
        'complete': all(quality[x] for x in ('weekly_complete', 'monthly_complete', 'bank_financials_complete')),
    }


def check_publication(directory: Path = DATA) -> dict:
    """Check the JSON, file://-friendly JS mirror, and audit consistency."""
    snapshot = json.loads((directory / 'snapshot.json').read_text(encoding='utf-8'))
    status = check_snapshot(snapshot)
    js = (directory / 'snapshot.js').read_text(encoding='utf-8').strip()
    prefix = 'window.BANKSCOPE_DATA = '
    if not js.startswith(prefix) or not js.endswith(';'):
        raise ValueError('JS snapshot does not match the expected data format')
    js_snapshot = json.loads(js[len(prefix):-1])
    if js_snapshot != snapshot:
        raise ValueError('JSON and JS datasets are not identical')
    audit = json.loads((directory / 'audit.json').read_text(encoding='utf-8'))
    if audit.get('quality') != snapshot.get('quality'):
        raise ValueError('Audit and snapshot quality flags differ')
    if audit.get('run_at') != snapshot.get('generated_at'):
        raise ValueError('Publication and audit timestamps differ')
    return status


if __name__ == '__main__':
    print(json.dumps(check_publication(), ensure_ascii=False, indent=2))
