"""Fail closed when the source changes names, tables or accounting structure."""
import json
import pytest
from src.core import ROOT, IDS
from src.bddk import OFFICIAL_CREDIT_LABELS, parse_weekly_html
from src.quality_gate import check_snapshot


def source_fixture():
    rows=json.loads((ROOT/'seed'/'bddk_2026_10_23_verified.json').read_text(encoding='utf-8'))
    vals={(r['metric_id'], r['currency']):r['value'] for r in rows}
    head='<p>Tarih: 23 Ekim 2026</p><table id="TabloExcel2">'
    head+='<tr><th></th><th>Sektör / Krediler</th><th>TP</th><th>YP</th><th>TOPLAM</th></tr>'
    for ix,mid in enumerate(IDS,1):
        def fmt(x):return ('%.5f' % x).replace('.',',')
        head+=f'<tr><td>{ix}</td><td>{OFFICIAL_CREDIT_LABELS[ix-1]}</td>'
        head+=''.join(f'<td>{fmt(vals[mid,c])}</td>' for c in ('TP','YP','TOTAL'))+'</tr>'
    return head+'</table>'


def test_precision_source_selected():
    period,rows=parse_weekly_html(source_fixture())
    assert period=='2026-10-23'
    assert len(rows)==66
    assert all(r['source_table_id']=='TabloExcel2' for r in rows)
    assert all(r['source_row_number']==IDS.index(r['metric_id'])+1 for r in rows)


def test_reject_rounded_table_even_when_otherwise_consistent():
    html=source_fixture().replace('id="TabloExcel2"','id="TabloExcel"')
    with pytest.raises(ValueError,match='high-precision'):
        parse_weekly_html(html)


def test_reject_changed_credit_row_name():
    html=source_fixture().replace('a) Konut','a) Yanlış hesap',1)
    with pytest.raises(ValueError,match='row-name mismatch'):
        parse_weekly_html(html)


def test_reject_swapped_balances_even_when_currency_totals_reconcile():
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(source_fixture(), 'html.parser')
    trs=soup.find('table',id='TabloExcel2').find_all('tr')
    # Swap full TP/YP/TOTAL triples between two different branches. Each
    # currency's row-level reconciliation remains valid, but the formal
    # hierarchy is corrupted: the balance-identity check must catch it.
    a=trs[4].find_all('td')
    b=trs[13].find_all('td')
    av=[x.get_text() for x in a[2:5]]
    bv=[x.get_text() for x in b[2:5]]
    for cell,value in zip(a[2:5],bv): cell.string=value
    for cell,value in zip(b[2:5],av): cell.string=value
    with pytest.raises(ValueError,match='balance identity mismatch'):
        parse_weekly_html(str(soup))


def test_quality_gate_detects_swapped_names_in_existing_data():
    snapshot=json.loads((ROOT/'web/data/snapshot.json').read_text(encoding='utf-8'))
    rows=next(r for r in snapshot['weekly'] if r['metric_id']=='total_loans' and r['currency']=='TOTAL')
    rows['source_row_number']=6
    with pytest.raises(ValueError,match='Wrong BDDK row-number'):
        check_snapshot(snapshot)
