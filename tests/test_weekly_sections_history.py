"""Historical NPL/deposit collection must remain section-scoped and date-scoped."""
from types import SimpleNamespace
import pytest
from src.weekly_sections_history import collect_one_section


class Response:
    def __init__(self,html):
        self.text=html
        self.content=html.encode()
        self.url="https://www.bddk.gov.tr/BultenHaftalik/"
    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.requests=[]
    def get(self,url,**kwargs):
        return Response('<form action="/BultenHaftalik/" method="post">'
                        '<input name="tabloId" value="289"/>'
                        '<input name="__RequestVerificationToken" value="tok"/></form>')
    def post(self,url,data,**kwargs):
        self.requests.append((url,data))
        if "tabloId" in data:
            return Response('<p>SECTION_VALID</p>'
                            '<form action="/BultenHaftalik/tr/Home/DonemDegistir" method="post">'
                            '<input name="__RequestVerificationToken" value="tok"/>'
                            '<select name="donemId"><option value="669">2026</option>'
                            '<option value="668">2026</option></select></form>')
        return Response(f'<p>PERIOD_{data["donemId"]}</p>')


def test_one_section_dates_are_separate_and_period_ids_are_preserved(monkeypatch):
    s=FakeSession()
    def parse(html,section_id):
        assert section_id==292
        if "PERIOD_669" in html: period="2026-10-23"
        elif "PERIOD_668" in html: period="2026-10-16"
        else: period="2026-10-23"
        return period,[{"period":period,"source_section_id":section_id}]
    monkeypatch.setattr("src.weekly_sections_history.parse_section_html",parse)
    monkeypatch.setattr("src.weekly_sections_history.save_archive",lambda *a: None)
    r=collect_one_section(292,processed_ids=["669"],max_new=1,recheck_recent=0,session=s)
    assert r["completed_ids"]==["668"]
    assert r["new_ids"]==["668"]
    assert [x["period"] for x in r["rows"]]==["2026-10-16"]
    assert s.requests[0][1]["tabloId"]=="292"
    assert s.requests[1][1]["donemId"]=="668"
    assert s.requests[1][1]["__RequestVerificationToken"]=="tok"


def test_unknown_section_id_rejected():
    with pytest.raises(ValueError,match="Unsupported"):
        collect_one_section(289,session=FakeSession())
