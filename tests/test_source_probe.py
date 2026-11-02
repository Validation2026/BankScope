from scripts.bddk_probe import summarize_html


def test_probe_discovers_form_without_exposing_sensitive_values():
    html = '''<html><head><title>Haftalık Bülten</title></head><body>
    <form method="post" action="/BultenHaftalik/Rapor">
    <input name="__RequestVerificationToken" type="hidden" value="DO_NOT_LOG_THIS">
    <select name="Yil"><option value="2025">2025</option><option value="2026">2026</option></select>
    <input name="Gonder" type="submit" value="Getir"></form>
    <script src="/js/weekly.js"></script></body></html>'''
    r = summarize_html(html, 'https://www.bddk.gov.tr/BultenHaftalik/')
    assert r['forms'][0]['method'] == 'POST'
    assert r['forms'][0]['action'] == 'https://www.bddk.gov.tr/BultenHaftalik/Rapor'
    assert r['forms'][0]['fields'][1]['option_values_first'] == ['2025', '2026']
    assert 'DO_NOT_LOG_THIS' not in str(r)
    assert r['scripts'] == ['https://www.bddk.gov.tr/js/weekly.js']
