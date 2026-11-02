"""No official NPL/deposit metrics are published without exact source reconciliation."""
import pytest
from src.bddk_sections import SECTION_SPECS, parse_section_html


def fixture(section_id, wrong_header=False, broken=False):
    spec = SECTION_SPECS[section_id]
    values = {}
    if section_id == 290:
        values = {4:10,5:20,6:30,3:60,7:15,2:75,8:125,1:200,9:50,10:40,11:10,12:20}
    elif section_id == 292:
        values = {3:100,4:200,2:300,6:250,7:250,5:500,9:75,10:125,8:200,1:1000,11:100}
    group = "Krediler" if wrong_header else spec["group"]
    html = '<p>Tarih: 23 Ekim 2026</p><table id="TabloExcel2">'
    html += f'<tr><th></th><th>Sektör / {group} (Milyon TL)</th><th>TP</th><th>YP</th><th>TOPLAM</th></tr>'
    for idx,label in enumerate(spec["labels"],1):
        amount = values[idx] + (1 if broken and idx == 1 else 0)
        html += (f'<tr><td>{idx}</td><td>{label}</td>'
                 f'<td>{amount*0.8:.3f}</td><td>{amount*0.2:.3f}</td><td>{amount:.3f}</td></tr>'.replace(".",","))
    return html + '</table>'


@pytest.mark.parametrize("section_id,expected",[(290,36),(292,33)])
def test_complete_original_structure(section_id,expected):
    date, rows = parse_section_html(fixture(section_id),section_id)
    assert date == "2026-10-23"
    assert len(rows) == expected
    assert all(x["source_section_id"] == section_id for x in rows)
    assert all(x["source_table_id"] == "TabloExcel2" for x in rows)


@pytest.mark.parametrize("section_id", [290,292])
def test_reject_wrong_section(section_id):
    with pytest.raises(ValueError,match="heading"):
        parse_section_html(fixture(section_id,wrong_header=True),section_id)


@pytest.mark.parametrize("section_id", [290,292])
def test_reject_subtotals_even_when_currency_sums_balance(section_id):
    with pytest.raises(ValueError,match="hierarchy"):
        parse_section_html(fixture(section_id,broken=True),section_id)


def test_reject_different_source_label():
    with pytest.raises(ValueError,match="source label"):
        parse_section_html(fixture(292).replace("Gerçek Kişiler (3+4)","Başka Kalem"),292)


def test_reject_rounded_table():
    with pytest.raises(ValueError,match="high-precision"):
        parse_section_html(fixture(290).replace("TabloExcel2","TabloExcel"),290)


def test_historical_kkm_information_row_is_optional_and_not_summed_twice():
    extra=('<tr><td>12</td><td>Kur Korumalı TL Mevduat ve Katılma Hesapları (Bilgi için)</td>'
           '<td>75,125</td><td>0,000</td><td>75,125</td></tr>')
    html=fixture(292).replace('</table>',extra+'</table>')
    period,rows=parse_section_html(html,292)
    assert len(rows)==36
    kkm=[r for r in rows if r['metric_id']=='deposit_kkm_try']
    assert len(kkm)==3
    assert {r['currency']:r['value'] for r in kkm}['TOTAL']==75.125
    assert all(r['source_row_number']==12 for r in kkm)


def test_unrecognized_extra_deposit_row_is_rejected():
    extra='<tr><td>12</td><td>Unknown Bank Total</td><td>0,000</td><td>0,000</td><td>0,000</td></tr>'
    with pytest.raises(ValueError,match="source label"):
        parse_section_html(fixture(292).replace('</table>',extra+'</table>'),292)
