"""Inspect BDDK weekly public table selectors without recording financial values."""
from bs4 import BeautifulSoup
import requests

URL = 'https://www.bddk.gov.tr/BultenHaftalik/'
r = requests.get(URL, timeout=30, headers={'User-Agent':'BankScope research public-bulletin'})
r.raise_for_status()
s = BeautifulSoup(r.text, 'html.parser')
for tag in s.find_all(['a', 'button', 'li', 'input']):
    label = tag.get_text(' ', strip=True)[:110]
    attrs = {k:tag.get(k) for k in ['id','name','href','onclick','value','data-target'] if tag.get(k) is not None}
    lookup = (label + ' ' + str(attrs)).lower()
    if any(k in lookup for k in ['mevduat','takip','menkul','bilanço','kredi','tablo','pozisyon']):
        if label or attrs: print('MENU', tag.name, repr(label), repr(attrs)[:330])
for script in s.find_all('script'):
    if script.get('src'):continue
    content=script.get_text()
    for term in ['TabloDegistir','tabloId','TabloId','tabloDegistir']:
        pos=content.find(term)
        if pos>=0:print('SCRIPT',term,repr(content[max(0,pos-170):pos+310])[:480])
for f in s.find_all('form'):
    fields=[(x.name,x.get('name'),x.get('id'),x.get('type')) for x in f.find_all(['input','select'])]
    if any('tablo' in str(z).lower() or 'taraf' in str(z).lower() for z in fields):
        print('FORM',f.get('method'),f.get('action'),fields)
