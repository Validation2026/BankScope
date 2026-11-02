"""Fail-closed parser for the BDDK weekly CREDIT table.

The official page includes three superficially identical HTML tables:
  Tablo (rounded to full million), TabloExcel (two decimals),
  TabloExcel2 (highest published precision).
Only TabloExcel2 is accepted. The official names and all six published
addition identities are checked *before* emitting observations.
"""
import re
from datetime import date
from bs4 import BeautifulSoup
from .core import IDS, METRICS, SOURCES, normalize, turkish_decimal

MONTHS = {'Ocak': 1, 'Şubat': 2, 'Mart': 3, 'Nisan': 4,
          'Mayıs': 5, 'Haziran': 6, 'Temmuz': 7, 'Ağustos': 8,
          'Eylül': 9, 'Ekim': 10, 'Kasım': 11, 'Aralık': 12}

# Literal official labels from BDDK's 23 October 2026 high-precision table;
# these are intentionally distinct from the user-friendly labels in METRICS.
OFFICIAL_CREDIT_LABELS = (
    'Toplam Krediler (2+10)',
    'Tüketici Kredileri ve Bireysel Kredi Kartları (3+7)',
    'Tüketici Kredileri (4+5+6)',
    'a) Konut', 'b) Taşıt', 'c) İhtiyaç',
    'Bireysel Kredi Kartları (8+9)', 'a) Taksitli', 'b) Taksitsiz',
    'Ticari ve Diğer Krediler',
    'Taksitli Tic. Krd. ve Kurumsal Kredi Kartları (12+16) (Bilgi)',
    'Taksitli Ticari Krediler (13+14+15) (Bilgi)',
    'a) İşyeri', 'b) Taşıt', 'c) İhtiyaç',
    'Kurumsal Kredi Kartları (17+18) (Bilgi)',
    'a) Taksitli', 'b) Taksitsiz',
    'KOBİ Kredileri (Bilgi)', 'Döv. Endeksli Krediler (Bilgi)',
    'Kredili Mevduat Hesapları-Tüketici Kredileri (Bilgi)',
    'Kredili Mevduat Hesapları-Taksitli Ticari Krediler(Bilgi)',
)

# Component indices from official row labels, not independent estimates.
CREDIT_IDENTITIES = {
    1: (2, 10),
    2: (3, 7),
    3: (4, 5, 6),
    7: (8, 9),
    11: (12, 16),
    12: (13, 14, 15),
    16: (17, 18),
}


def validate_credit_lines(lines, tolerance=0.25):
    """Check every TP/YP/TOTAL and official balance identity for 22 rows."""
    if set(lines) != set(range(1, 23)):
        raise ValueError('Incomplete BDDK credit table')
    for number, (source_label, values) in lines.items():
        if normalize(source_label) != normalize(OFFICIAL_CREDIT_LABELS[number - 1]):
            raise ValueError(f'BDDK source row-name mismatch at {number}: {source_label!r}')
        if len(values) != 3 or any(v is None or v < 0 for v in values):
            raise ValueError(f'Missing or negative BDDK amount at row {number}')
        if abs(values[0] + values[1] - values[2]) > tolerance:
            raise ValueError(f'BDDK TP+YP mismatch at row {number}')
    for total_index, component_indices in CREDIT_IDENTITIES.items():
        for currency_pos in range(3):
            expected = sum(lines[i][1][currency_pos] for i in component_indices)
            actual = lines[total_index][1][currency_pos]
            if abs(actual - expected) > tolerance:
                raise ValueError(f'BDDK balance identity mismatch at {total_index}, column {currency_pos}')


def parse_weekly_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    pattern = (r'Tarih\s*:\s*(\d{1,2})\s+'
               r'(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+'
               r'(20\d\d)')
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError('BDDK weekly reporting date missing')
    period = date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1))).isoformat()

    table = soup.find('table', id='TabloExcel2')
    if table is None:
        raise ValueError('BDDK high-precision TabloExcel2 not found; do not use rounded tables')
    heading = table.find('tr')
    cols = [cell.get_text(' ', strip=True) for cell in heading.find_all(['th', 'td'], recursive=False)] if heading else []
    if len(cols) < 5 or [normalize(c) for c in cols[-3:]] != ['tp', 'yp', 'toplam']:
        raise ValueError('BDDK high-precision table currency headers changed')
    if 'krediler' not in normalize(' '.join(cols[:-3])):
        raise ValueError('BDDK selected table is not Krediler')

    lines = {}
    for tr in table.select('tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.find_all(['th','td'], recursive=False)]
        if not cells or not re.fullmatch(r'\d{1,2}', cells[0]):
            continue
        row_num = int(cells[0])
        if row_num not in range(1, 23) or len(cells) != 5:
            raise ValueError(f'Unexpected official BDDK row/shape: {cells[:2]}')
        if row_num in lines:
            raise ValueError(f'Duplicate official BDDK row: {row_num}')
        values = [turkish_decimal(c) for c in cells[2:5]]
        lines[row_num] = (cells[1], values)

    validate_credit_lines(lines)
    rows = []
    for pos, metric_id in enumerate(IDS, 1):
        label = METRICS[metric_id][0]
        official_label, amounts = lines[pos]
        for currency, value in zip(('TP','YP','TOTAL'), amounts):
            rows.append({
                'source': 'bddk_weekly', 'source_url': SOURCES['bddk_weekly'],
                'period': period, 'scope': 'sector', 'metric_id': metric_id,
                'label': label, 'source_label': official_label, 'source_row_number': pos,
                'source_table_id': 'TabloExcel2', 'group': 'Krediler',
                'currency': currency, 'unit': 'million_try', 'value': value,
                'status': 'official'
            })
    return period, rows
