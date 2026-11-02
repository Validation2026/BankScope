"""CLI: python -m src.pipeline. Generates a publishable static snapshot.
Online refresh will only replace official verified metric groups.
"""
import argparse,json,sys,traceback
from datetime import datetime,timezone
from pathlib import Path
from bs4 import BeautifulSoup
from .core import ROOT,DATA,ARCHIVE,SOURCES,IDS,METRICS,write_json,http_get,save_archive,validate_rows
from .bddk import parse_weekly_html
from .weekly_history import collect_weekly_history
from .bddk_sections import collect_latest_sections
from .weekly_sections_history import collect_section_histories
from .tbb import discover_report_pages,extract_attachment_links,archive_attachments

SEED=ROOT/'seed'/'bddk_2026_10_23_verified.json'
SNAPSHOT=DATA/'snapshot.json'
AUDIT=DATA/'audit.json'

def load_existing():
 if SNAPSHOT.exists():return json.loads(SNAPSHOT.read_text(encoding='utf-8'))
 return {'weekly':[],'monthly':[],'banks':[],'quality':{},'source_catalog':[]}

def merge_rows(old,new):
 keys=lambda r:(r['source'],r['period'],r['scope'],r['metric_id'],r.get('currency','TOTAL'),r.get('bank_id',''))
 d={keys(x):x for x in old}
 for x in validate_rows(new):d[keys(x)]=x
 return sorted(d.values(),key=lambda r:(r['period'],r['metric_id'],r.get('currency','TOTAL')))

def source_revisions(old_rows, incoming_rows):
 """Only compare like-for-like *official* observations; do not guess revisions."""
 key=lambda r:(r['source'],r['period'],r['scope'],r['metric_id'],r.get('currency','TOTAL'),r.get('bank_id',''))
 old={key(r):r for r in old_rows}
 changes=[]
 for row in incoming_rows:
  prev=old.get(key(row))
  if prev is not None and abs(prev['value']-row['value']) > 0.000001:
   changes.append({'period':row['period'],'source':row['source'],'metric_id':row['metric_id'],
                   'currency':row.get('currency','TOTAL'),'old_value':prev['value'],
                   'new_value':row['value'],'unit':row['unit'],'status':'official_source_changed'})
 return changes


def run(online=False,downloads=False):
 result=load_existing()
 if not result['weekly'] and SEED.exists():
  result['weekly']=merge_rows([],json.loads(SEED.read_text(encoding='utf-8')))
 logs=[];catalog=result.get('source_catalog',[])
 revisions=[]
 if online:
  try:
   resp=http_get(SOURCES['bddk_weekly']);save_archive('bddk_weekly',resp.content,'.html',resp.url)
   period,rows=parse_weekly_html(resp.text)
   revisions.extend(source_revisions(result['weekly'],rows))
   result['weekly']=merge_rows(result['weekly'],rows)
   logs.append({'source':'bddk_weekly','status':'ok','period':period,'records':len(rows)})
  except Exception as exc:logs.append({'source':'bddk_weekly','status':'failed_last_verified_retained','error':str(exc)[:250]})
  try:
   history=collect_weekly_history(processed_ids=result.get('weekly_backfill_completed_ids', []), max_reports=16, recheck_recent=4)
   if history['rows']:
    revisions.extend(source_revisions(result['weekly'],history['rows']))
    result['weekly']=merge_rows(result['weekly'],history['rows'])
   result['weekly_backfill_completed_ids']=sorted(set(result.get('weekly_backfill_completed_ids', []) + history['completed_ids']),key=int)
   logs.append({'source':'bddk_weekly_history','status':'partial_backfill',
                'new_periods':len(history['new_ids']),'rechecked_periods':len(history['rechecked_ids']),
                'available_periods':history['available_period_count'],
                'errors':history['failures'][:2]})
  except Exception as exc:
   logs.append({'source':'bddk_weekly_history','status':'failed_last_verified_retained',
                'error':str(exc)[:250]})
  try:
   other=collect_latest_sections()
   if other['rows']:
    revisions.extend(source_revisions(result['weekly'],other['rows']))
    result['weekly']=merge_rows(result['weekly'],other['rows'])
   logs.append({'source':'bddk_weekly_other_sections',
                'status':'verified' if len(other['sections_found'])==2 else 'partial',
                'sections':other['sections_found'],'records':len(other['rows']),
                'errors':other['errors']})
  except Exception as exc:
   logs.append({'source':'bddk_weekly_other_sections','status':'failed_last_verified_retained',
                'error':str(exc)[:250]})
  try:
   section_history=collect_section_histories(
       completed_by_section=result.get('weekly_section_backfill_completed_ids',{}),
       max_new=8, recheck_recent=2)
   if section_history['rows']:
    revisions.extend(source_revisions(result['weekly'],section_history['rows']))
    result['weekly']=merge_rows(result['weekly'],section_history['rows'])
   result['weekly_section_backfill_completed_ids']=section_history['completed_by_section']
   logs.append({'source':'bddk_weekly_section_history','status':'partial_backfill',
                'records':len(section_history['rows']),
                'sections':section_history['details']})
  except Exception as exc:
   logs.append({'source':'bddk_weekly_section_history','status':'failed_last_verified_retained',
                'error':str(exc)[:250]})
  try:
   # Paginated searchable TBB reports, with automated current and historical report discovery.
   all_pages=[];seen=set()
   for page in range(5):
    url=SOURCES['tbb_reports']+(f'?page={page}' if page else '')
    res=http_get(url)
    found=discover_report_pages(res.text,res.url)
    for p in found:
     if p['url'] not in seen:all_pages.append(p);seen.add(p['url'])
   catalog=all_pages
   logs.append({'source':'tbb_reports','status':'catalogued','records':len(all_pages)})
   # Download raw standardised workbooks for the most recent solo and consolidated periods.
   if downloads:
    selected={}
    for p in all_pages:
     if 'Excel formatında ortak veri seti' not in p['title']:continue
     if p['scope'] not in selected or (p['period'] or '')>(selected[p['scope']]['period'] or ''):selected[p['scope']]=p
    attachment_audit=[]
    for p in selected.values():
     html=http_get(p['url']).text
     links=extract_attachment_links(html,p['url'])
     if not links:
      # Many TBB report detail pages require a JS selection; homepage sometimes exposes the bank ZIP links directly.
      index_response=http_get(SOURCES['tbb_index'])
      links=[x for x in extract_attachment_links(index_response.text,index_response.url) if '.zip' in x['url'].lower()]
     attachment_audit.extend(archive_attachments(links))
    # Keep raw ZIPs for auditing; do NOT present unverified cells as real financial facts.
    write_json(DATA/'raw_bank_archive_status.json',attachment_audit)
    logs.append({'source':'tbb_archives','status':'archived_pending_layout_validation','records':len(attachment_audit)})
  except Exception as exc:logs.append({'source':'tbb_reports','status':'failed','error':str(exc)[:250]})
  try:
   response=http_get(SOURCES['bddk_monthly_announcement'])
   soup=BeautifulSoup(response.text,'html.parser')
   title=soup.get_text(' ',strip=True)
   result['monthly_latest_release']='2026-09' if '2026 Eylül verileri yayımlanmıştır' in title else None
   logs.append({'source':'bddk_monthly','status':'announcement_checked_unparsed', 'release':result['monthly_latest_release']})
  except Exception as exc:logs.append({'source':'bddk_monthly','status':'failed','error':str(exc)[:250]})
 # Preserve an audit trail of actual official changes without publishing
 # extrapolated/estimated replacements. New observations are not revisions.
 if revisions:
  old_revs=result.get('recent_revisions',[])
  result['recent_revisions']=(old_revs + revisions)[-250:]
 else:
  result.setdefault('recent_revisions',[])
 logs.append({'source':'official_revisions','status':'checked','changed_observations':len(revisions)})
 result['source_catalog']=catalog
 result['generated_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
 result['version']='0.7.0'
 result['sources']=SOURCES
 periods=sorted(set(x['period'] for x in result['weekly']))
 groups=sorted({x.get('group','Krediler') for x in result['weekly']})
 group_periods={g:sorted({x['period'] for x in result['weekly'] if x.get('group','Krediler')==g}) for g in groups}
 # Do not claim full coverage when only the credit tab is ingested.
 result['quality']={'weekly_periods':periods,'weekly_categories_covered':groups,'weekly_periods_by_group':group_periods,
 'weekly_complete':False,'monthly_complete':False,'bank_financials_complete':False,
 'bank_count_verified':len(set(x.get('bank_id') for x in result['banks'] if x.get('bank_id'))),
 'missing_modules':['BDDK diğer haftalık sekmeler','BDDK aylık interaktif tarihsel seriler','TBB bankaların doğrulanmış finansal tablo kalemleri','TKBB katılım bankaları kapsam kontrolü'],
 'status':'partial_verified'}
 write_json(SNAPSHOT,result)
 write_json(AUDIT,{'run_at':result['generated_at'],'steps':logs,'quality':result['quality']})
 # file://-compatible frontend. NETLIFY serves this as a static script as well.
 (DATA/'snapshot.js').write_text('window.BANKSCOPE_DATA = '+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
 return logs,result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--online',action='store_true');p.add_argument('--download-bank-archives',action='store_true')
 args=p.parse_args();logs,data=run(args.online,args.download_bank_archives)
 print(json.dumps({'logs':logs,'quality':data['quality'],'weekly_facts':len(data['weekly'])},ensure_ascii=False,indent=2))
