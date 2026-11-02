"""Extract only the verified weekly Credits table, preserving its 22 original lines."""
import re
from datetime import date
from bs4 import BeautifulSoup
from .core import IDS,METRICS,turkish_decimal,SOURCES

MONTHS={'Ocak':1,'Şubat':2,'Mart':3,'Nisan':4,'Mayıs':5,'Haziran':6,'Temmuz':7,'Ağustos':8,'Eylül':9,'Ekim':10,'Kasım':11,'Aralık':12}

def parse_weekly_html(html):
 soup=BeautifulSoup(html,'html.parser')
 text=soup.get_text(' ',strip=True)
 pattern=r'Tarih\s*:\s*(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(20\d\d)'
 m=re.search(pattern,text,re.I)
 if not m:raise ValueError('BDDK weekly reporting date missing')
 period=date(int(m.group(3)),MONTHS[m.group(2)],int(m.group(1))).isoformat()
 candidates=[]
 for table in soup.select('table'):
  rows=[]
  precision=0
  for tr in table.select('tr'):
   cells=[td.get_text(' ',strip=True) for td in tr.find_all(['th','td'],recursive=False)]
   if not cells:continue
   # 1 + row name + three values; some tables add index as the first of five cells.
   n=next((i for i,x in enumerate(cells) if re.fullmatch(r'\d{1,2}',x)),None)
   if n is None or int(cells[n]) not in range(1,23):continue
   if len(cells)<n+5:continue
   try:values=[turkish_decimal(x) for x in cells[n+2:n+5]]
   except ValueError:continue
   if any(v is None for v in values):continue
   rows.append((int(cells[n]),cells[n+1],values))
   precision+=sum(len(z.split(',')[-1]) if ',' in z else 0 for z in cells[n+2:n+5])
  if len(rows)>=20:candidates.append((precision,rows))
 if not candidates:raise ValueError('No complete credits table (22 lines) found; source may have changed')
 # Prefer decimal-precision source table; never combine duplicate HTML display tables.
 chosen=max(candidates,key=lambda t:t[0])[1]
 by_index={i:(label,v) for i,label,v in chosen}
 if set(by_index)!=set(range(1,23)):raise ValueError('Incomplete or duplicated credit categories')
 result=[]
 for pos,metric_id in enumerate(IDS,1):
  label=METRICS[metric_id][0]
  _,v=by_index[pos]
  tp,yp,total=v
  if abs(tp+yp-total)>0.15:raise ValueError(f'Weekly reconciliation failed for {metric_id}: {v}')
  for cur,val in zip(('TP','YP','TOTAL'),v):
   result.append({'source':'bddk_weekly','source_url':SOURCES['bddk_weekly'],'period':period,'scope':'sector',
                  'metric_id':metric_id,'label':label,'group':'Krediler','currency':cur,'unit':'million_try','value':val,'status':'official'})
 return period,result
