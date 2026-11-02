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
 html='<div>Tarih: 23 Ekim 2026 Cuma | Birim: Milyon TL</div><table>'
 html+=''.join(f'<tr><td>{i}</td><td>Kalem {i}</td><td>500,125</td><td>6,125</td><td>506,250</td></tr>' for i in range(1,23))+'</table>'
 period,rows=parse_weekly_html(html)
 assert period=='2026-10-23' and len(rows)==66
 assert rows[0]['metric_id']=='total_loans' and rows[-1]['metric_id']=='commercial_overdraft'
 assert rows[0]['value']==pytest.approx(500.125)

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
 assert len(data['weekly'])==66
 assert data['quality']['status']=='partial_verified'
 assert data['quality']['bank_financials_complete'] is False
 assert not data['banks']
