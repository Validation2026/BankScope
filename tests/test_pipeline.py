from src.core import turkish_decimal,validate_rows,SOURCES
from src.bddk import parse_weekly_html
from src.tbb import discover_report_pages,extract_attachment_links
from src.pipeline import run
import pytest

def test_tr_number():
 assert turkish_decimal('28.776.556,03584')==pytest.approx(28776556.03584)
 assert turkish_decimal('(1.250,44)')==-1250.44
 assert turkish_decimal(' 4.355 ') ==4355
 assert turkish_decimal('—') is None

def test_weekly_complete_fixture():
 from src.bddk import OFFICIAL_CREDIT_LABELS
 # Financially consistent miniature: original official 2026 snapshot is a
 # fixture ONLY, not a source for new publication.
 import json
 from src.core import ROOT
 original=json.loads((ROOT/'seed'/'bddk_2026_10_23_verified.json').read_text(encoding='utf-8'))
 by_key={(row['metric_id'],row['currency']):row['value'] for row in original}
 from src.core import IDS
 table='<p>Tarih: 23 Ekim 2026 Cuma | Birim: Milyon TL</p><table id="TabloExcel2">'
 table+='<tr><th></th><th>Sektör / Krediler</th><th>TP</th><th>YP</th><th>TOPLAM</th></tr>'
 for n,metric in enumerate(IDS,1):
  vals=[by_key[metric,c] for c in ('TP','YP','TOTAL')]
  numerics=['{:,.5f}'.format(v).replace(',','X').replace('.',',').replace('X','.') for v in vals]
  table+=f'<tr><td>{n}</td><td>{OFFICIAL_CREDIT_LABELS[n-1]}</td>'+''.join(f'<td>{v}</td>' for v in numerics)+'</tr>'
 period,rows=parse_weekly_html(table+'</table>')
 assert period=='2026-10-23' and len(rows)==66
 assert rows[0]['source_table_id']=='TabloExcel2'
 assert rows[0]['metric_id']=='total_loans' and rows[-1]['metric_id']=='commercial_overdraft'
 assert rows[0]['value']==pytest.approx(by_key['total_loans','TP'])

def test_weekly_fail_closed():
 html='<p>Tarih: 23 Ekim 2026</p><table><tr><td>1</td><td>Kredi</td><td>25,0</td><td>5,0</td><td>10,0</td></tr></table>'
 with pytest.raises(ValueError):parse_weekly_html(html)

def test_tbb_link_discovery():
 html='<a href="/istatistiki-raporlar/2026-haziran">2026 Haziran - Finansal Tablolar - Konsolide Olmayan (Solo Banka, Excel formatında ortak veri seti)</a>'
 result=discover_report_pages(html,'https://www.tbb.org.tr/')
 assert len(result)==1 and result[0]['scope']=='solo' and result[0]['period']=='2026-06'
 assert extract_attachment_links('<a href="/download/node/123/abc">Tablo.xls</a>','https://www.tbb.org.tr/')==[{'label':'Tablo.xls','url':'https://www.tbb.org.tr/download/node/123/abc'}]

def test_baseline_snapshot():
 logs,data=run(False,False)
 assert len(data['weekly']) >= 66 and len(data['weekly']) % 66 == 0
 assert data['quality']['status']=='partial_verified'
 assert data['quality']['bank_financials_complete'] is False
 assert not data['banks']
