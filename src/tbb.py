"""Official TBB publication discovery / raw archive. Never guess spreadsheet cell definitions."""
import re,zipfile,io
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlparse
from .core import SOURCES,safe_url,save_archive,http_get

MONTH={'Ocak':1,'Şubat':2,'Mart':3,'Nisan':4,'Mayıs':5,'Haziran':6,'Temmuz':7,'Ağustos':8,'Eylül':9,'Ekim':10,'Kasım':11,'Aralık':12}

def discover_report_pages(html,base):
 soup=BeautifulSoup(html,'html.parser');res=[];seen=set()
 for a in soup.select('a[href]'):
  name=a.get_text(' ',strip=True)
  if not ('Finansal Tablolar' in name or 'Aktif Büyüklüklerine Göre Banka Sıralaması' in name or 'Banka Bilgileri' in name):continue
  u=urljoin(base,a['href'])
  if urlparse(u).hostname not in ('www.tbb.org.tr','tbb.org.tr'):continue
  if u in seen:continue
  seen.add(u)
  period_match=re.search(r'(20\d\d)\s+(Ocak|Şubat|Mart|Haziran|Eylül|Aralık)',name,re.I)
  period=f'{period_match.group(1)}-{MONTH[period_match.group(2)]:02d}' if period_match else None
  scope='solo' if 'Konsolide Olmayan' in name else ('consolidated' if 'Konsolide' in name else None)
  res.append({'title':name,'url':u,'period':period,'scope':scope})
 return res

def extract_attachment_links(html,base):
 soup=BeautifulSoup(html,'html.parser');found=[];seen=set()
 for a in soup.select('a[href]'):
  url=urljoin(base,a['href'])
  if not re.search(r'\.(zip|xls|xlsx|pdf)(?:$|\?)',url,re.I) and '/download/node/' not in url:continue
  try:safe_url(url)
  except ValueError:continue
  if url in seen:continue
  seen.add(url)
  # Name should come from adjacent text; if absent, file is still archived with name unknown.
  label=a.get_text(' ',strip=True)
  parent=a.parent
  if len(label)<5 and parent:label=parent.get_text(' ',strip=True)
  found.append({'label':label[:180],'url':url})
 return found

def archive_attachments(links,max_files=60,session=None):
 result=[]
 for x in links[:max_files]:
  u=safe_url(x['url'])
  try:
   r=http_get(u,session=session,timeout=50)
   raw=r.content
   if raw[:2]==b'PK':
    if not zipfile.is_zipfile(io.BytesIO(raw)):raise ValueError('Corrupt ZIP container')
    with zipfile.ZipFile(io.BytesIO(raw)) as packet:
     extension='.xlsx' if 'xl/workbook.xml' in packet.namelist() else '.zip'
   elif raw[:8]==bytes.fromhex('D0CF11E0A1B11AE1'):extension='.xls'
   elif raw[:4]==b'%PDF':extension='.pdf'
   else:raise ValueError('Unsupported data file signature; possible HTML rejection')
   audit=save_archive('tbb',raw,extension,u)
   if extension=='.zip':
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
     if len(z.namelist())>80:raise ValueError('Excessive zip entries')
     audit['members']=[{'name':n,'size':z.getinfo(n).file_size} for n in z.namelist() if not n.endswith('/')]
   audit['title']=x['label'];audit['status']='archived_unmapped'
   result.append(audit)
  except Exception as exc:
   result.append({'url':u,'title':x['label'],'status':'download_failed','error':str(exc)[:250]})
 return result

# For financial statement processing a separate, versioned ledger mapping MUST be approved
# against the original accounting line and report unit. Download alone != verified data.
