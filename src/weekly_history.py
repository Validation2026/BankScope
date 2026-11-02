"""Read official historical BDDK weekly credit reports, with CSRF/session preservation.

A complete reporting period is merged only when its 22 TP/YP/TOTAL lines pass
all original-source checks. Never reconstruct an official figure from news text.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .bddk import parse_weekly_html
from .core import SOURCES, save_archive


class SourceFormChanged(ValueError):
    pass


def discover_period_form(html: str, base_url: str):
    soup = BeautifulSoup(html, 'html.parser')
    form = next((f for f in soup.find_all('form') if f.find('select', attrs={'name': 'donemId'})), None)
    if not form:
        raise SourceFormChanged('Official BDDK period-selection form not found')
    selector = form.find('select', attrs={'name': 'donemId'})
    values = []
    for option in selector.find_all('option'):
        id_ = option.get('value', '')
        if not re.fullmatch(r'\d{1,6}', id_):
            continue
        label = option.get_text(' ', strip=True)
        match = re.search(r'\b20\d{2}\b', label)
        values.append({'id': id_, 'label': label, 'year': match.group(0) if match else None})
    if not values or len(values) != len({x['id'] for x in values}):
        raise SourceFormChanged('Missing or duplicate BDDK reporting period IDs')
    action = urljoin(base_url, form.get('action') or base_url)
    if not action.startswith('https://www.bddk.gov.tr/BultenHaftalik/'):
        raise SourceFormChanged('Unexpected BDDK period selector endpoint')
    token = form.find('input', attrs={'name': '__RequestVerificationToken'})
    csrf = token.get('value') if token else None
    return action, values, csrf


def collect_weekly_history(processed_ids=(), max_reports=8, min_year=2022, session=None):
    """Return all-or-nothing verified rows per weekly report and IDs accepted.

    One request per reporting period, no future periods or unverified totals.
    When a report fails, preserve the previously verified publication unchanged.
    """
    session = session or requests.Session()
    source = SOURCES['bddk_weekly']
    response = session.get(source, timeout=30, headers={
        'User-Agent': 'BankScope/0.3 (official-public-weekly-statistics)',
    })
    response.raise_for_status()
    action, periods, csrf = discover_period_form(response.text, response.url)
    processed = set(map(str, processed_ids))
    output, completed, failures = [], [], []
    last_year = date.today().year
    for entry in periods:
        if len(completed) >= max_reports:
            break
        id_ = entry['id']
        if id_ in processed:
            continue
        # If year cannot be inferred from the option, let the server resolve
        # the period ID; verify the response's exact reporting date below.
        year = entry['year'] or str(last_year)
        if int(year) < min_year:
            continue
        payload = {'yil': year, 'donemId': id_, 'para': 'TL'}
        if csrf:
            payload['__RequestVerificationToken'] = csrf
        try:
            report = session.post(action, data=payload, timeout=30,
                                  headers={'Referer': response.url,
                                           'User-Agent': 'BankScope/0.3 (official-public-weekly-statistics)'})
            report.raise_for_status()
            reported_period, rows = parse_weekly_html(report.text)
            if reported_period > date.today().isoformat():
                raise ValueError('Future official reporting period rejected')
            if int(reported_period[:4]) < min_year:
                # Old reports are outside the requested coverage horizon.
                break
            if entry['year'] and entry['year'] != reported_period[:4]:
                raise ValueError('Selected year does not match official report')
            if reported_period in {x['period'] for x in output}:
                raise ValueError('Different period IDs produced the same reporting date')
            archive_info = save_archive('bddk_weekly_history', report.content, '.html', report.url)
            completed.append(id_)
            output.extend(rows)
            last_year = int(reported_period[:4])
        except (requests.RequestException, ValueError) as exc:
            failures.append({'period_id': id_, 'error_type': type(exc).__name__,
                             'error': str(exc)[:160]})
            # If the report form no longer works, avoid hammering the source.
            if len(failures) >= 2:
                break
    return {'rows': output, 'completed_ids': completed, 'failures': failures,
            'available_period_count': len(periods)}
