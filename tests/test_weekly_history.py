from types import SimpleNamespace

import pytest

from src.weekly_history import discover_period_form, collect_weekly_history, SourceFormChanged


def make_report(day):
    html=f'<p>Tarih: {day} Ekim 2026 Cuma | Birim: Milyon TL</p><table>'
    html+=''.join(f'<tr><td>{i}</td><td>Kredi {i}</td><td>500,125</td><td>6,125</td><td>506,250</td></tr>' for i in range(1,23))
    return html+'</table>'


LANDING='''<form action="/BultenHaftalik/tr/Home/DonemDegistir" method="post">
<input name="__RequestVerificationToken" value="token123" type="hidden">
<select name="donemId"><option value="669">2026 hafta 43</option><option value="668">2026 hafta 42</option></select>
</form>'''


class FakeSession:
    def get(self, *a, **kw):
        return FakeResponse(LANDING)
    def post(self, url, data, **kw):
        assert url=='https://www.bddk.gov.tr/BultenHaftalik/tr/Home/DonemDegistir'
        assert data['__RequestVerificationToken']=='token123'
        return FakeResponse(make_report('23' if data['donemId']=='669' else '16'))


class FakeResponse:
    def __init__(self, html):
        self.url='https://www.bddk.gov.tr/BultenHaftalik/'
        self.text=html
        self.content=html.encode()
    def raise_for_status(self):
        pass


def test_period_form_discovers_csrf_and_ids():
    target, options, token = discover_period_form(LANDING,'https://www.bddk.gov.tr/BultenHaftalik/')
    assert token=='token123'
    assert target.endswith('/DonemDegistir')
    assert [o['id'] for o in options]==['669','668']


def test_bad_form_rejected():
    with pytest.raises(SourceFormChanged):
        discover_period_form('<div>No data</div>', 'https://www.bddk.gov.tr/BultenHaftalik/')


def test_history_merges_only_verified_reports(monkeypatch):
    monkeypatch.setattr('src.weekly_history.save_archive', lambda *a: {'sha256':'abc'})
    data=collect_weekly_history(processed_ids=['669'],max_reports=8,session=FakeSession())
    assert data['completed_ids']==['668']
    assert len(data['rows'])==66
    assert {row['period'] for row in data['rows']}=={'2026-10-16'}
    assert not data['failures']
