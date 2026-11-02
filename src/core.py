"""BankScope ingestion core. Fail-closed: data without provenance never reaches UI."""
from __future__ import annotations
import hashlib, json, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from decimal import Decimal, InvalidOperation

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'archive'
DATA=ROOT/'web'/'data'
SOURCES={
 'bddk_weekly':'https://www.bddk.gov.tr/BultenHaftalik/',
 'bddk_monthly':'https://www.bddk.gov.tr/BultenAylik',
 'bddk_monthly_announcement':'https://www.bddk.gov.tr/Duyuru/Detay/4318',
 'tbb_reports':'https://www.tbb.org.tr/istatistiki-raporlar/search',
 'tbb_index':'https://www.tbb.org.tr/banka-ve-sektor-bilgileri',
 'tbb_rank':'https://www.tbb.org.tr/istatistiki-raporlar/2026-haziran-aktif-buyukluklerine-gore-banka-siralamasi',
 'kap':'https://www.kap.org.tr/tr', 'tkbb':'https://www.tkbb.org.tr'
}
METRICS={
 'total_loans':('Toplam Krediler','Krediler'),
 'retail_plus_cards':('Tüketici Kredileri ve Bireysel Kredi Kartları','Krediler'),
 'consumer_loans':('Tüketici Kredileri','Krediler'),
 'housing_loans':('Konut Kredileri','Krediler'),
 'auto_loans':('Taşıt Kredileri','Krediler'),
 'personal_loans':('İhtiyaç Kredileri','Krediler'),
 'retail_cards':('Bireysel Kredi Kartları','Krediler'),
 'retail_cards_installment':('Bireysel Kredi Kartları - Taksitli','Krediler'),
 'retail_cards_revolving':('Bireysel Kredi Kartları - Taksitsiz','Krediler'),
 'commercial_other_loans':('Ticari ve Diğer Krediler','Krediler'),
 'installment_commercial_plus_corporate_cards':('Taksitli Ticari Krediler ve Kurumsal Kartlar (Bilgi)','Krediler'),
 'installment_commercial':('Taksitli Ticari Krediler (Bilgi)','Krediler'),
 'workplace_commercial':('Ticari İşyeri Kredileri','Krediler'),
 'auto_commercial':('Ticari Taşıt Kredileri','Krediler'),
 'personal_commercial':('Ticari İhtiyaç Kredileri','Krediler'),
 'corporate_cards':('Kurumsal Kredi Kartları (Bilgi)','Krediler'),
 'corporate_cards_installment':('Kurumsal Kredi Kartları - Taksitli','Krediler'),
 'corporate_cards_revolving':('Kurumsal Kredi Kartları - Taksitsiz','Krediler'),
 'sme_loans':('KOBİ Kredileri (Bilgi)','Krediler'),
 'fx_indexed_loans':('Dövize Endeksli Krediler (Bilgi)','Krediler'),
 'retail_overdraft':('Bireysel Kredili Mevduat Hesabı (Bilgi)','Krediler'),
 'commercial_overdraft':('Ticari Kredili Mevduat Hesabı (Bilgi)','Krediler')
}
IDS=list(METRICS)

def normalize(s):
 s=unicodedata.normalize('NFKD',str(s)).casefold()
 return re.sub(r'[^a-z0-9]+',' ',''.join(x for x in s if not unicodedata.combining(x))).strip()

def turkish_decimal(value):
 """Financial table numbers are Turkish, not US formatted."""
 s=str(value).strip().replace('\u00a0','').replace(' ','').replace('−','-')
 if not s or s in ('-','—','n/a'):return None
 if re.search(r'[^\d.,+\-()]',s):raise ValueError(f'Not numeric: {value}')
 negative=s.startswith('(') and s.endswith(')')
 if negative:s=s[1:-1]
 if ',' in s:s=s.replace('.','').replace(',','.')
 elif s.count('.')>1 or re.fullmatch(r'-?\d{1,3}(\.\d{3})+',s):s=s.replace('.','')
 try:x=Decimal(s)
 except InvalidOperation as e:raise ValueError(f'Bad number: {value}') from e
 if not x.is_finite():raise ValueError('Non-finite number')
 return float(-x if negative else x)

def validate_rows(rows):
 seen=set()
 for r in rows:
  k=(r['source'],r['period'],r['scope'],r['metric_id'],r.get('currency','TOTAL'),r.get('bank_id',''))
  if k in seen:raise ValueError('Duplicate metric '+str(k))
  seen.add(k)
  if r['value'] is None or not isinstance(r['value'],(float,int)):raise ValueError('Missing/invalid value')
  if not r['source_url'].startswith('https://'):raise ValueError('Missing provenance')
  if r['unit'] not in ('million_try','percent'):raise ValueError('Unknown unit')
 return rows

def save_archive(source_name, content, suffix, url):
 sha=hashlib.sha256(content).hexdigest();p=ARCHIVE/source_name/(sha+suffix)
 p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_bytes(content)
 return {'sha256':sha,'path':str(p.relative_to(ROOT)),'url':url,'bytes':len(content)}

def write_json(path, payload):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)

def http_get(url,session=None,timeout=30):
 import requests
 s=session or requests.Session()
 h={'User-Agent':'BankScope Research/0.2 (public-statistics; respectful requests)', 'Accept':'text/html,application/zip,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/pdf,*/*'}
 r=s.get(url,timeout=timeout,headers=h);r.raise_for_status()
 if len(r.content)>80*1024*1024:raise ValueError('Unexpectedly large download')
 return r

def safe_url(url):
 parsed=urlparse(url)
 if parsed.scheme!='https' or parsed.hostname not in {'www.tbb.org.tr','tbb.org.tr','www.bddk.gov.tr','bddk.gov.tr','www.bddk.org.tr','bddk.org.tr'}:
  raise ValueError('Non-official link rejected: '+url)
 return url
