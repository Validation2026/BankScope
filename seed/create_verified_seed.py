"""One-off transcription from official BDDK 23.10.2026 weekly Credits table.
https://www.bddk.gov.tr/BultenHaftalik/ (the 3-decimal table)"""
import json, pathlib
from decimal import Decimal
rows=[
 ('18320099.58323','10456456.45261','28776556.03584'),
 ('6927324.16','11404.5','6938728.66'),
 ('3524256.128','278.625','3524534.753'),
 ('850516.923','63.423','850580.346'),
 ('43034.454','89.364','43123.818'),
 ('2630704.751','125.838','2630830.589'),
 ('3403068.032','11125.875','3414193.907'),
 ('1316324.309','0','1316324.309'),
 ('2086743.723','11125.875','2097869.598'),
 ('11392775.42323','10445051.95261','21837827.37584'),
 ('4283319.801','1193581.62','5476901.421'),
 ('3157600.169','1192240.976','4349841.145'),
 ('36035.285','7983.766','44019.051'),
 ('368660.315','36735.421','405395.736'),
 ('2752904.569','1147521.789','3900426.358'),
 ('1125719.632','1340.644','1127060.276'),
 ('286783.905','0','286783.905'),
 ('838935.727','1340.644','840276.371'),
 ('6383001.039','1355695.942','7738696.981'),
 ('1008.36099','0','1008.36099'),
 ('952004.823','0','952004.823'),
 ('336137.621','0','336137.621')
]
from sys import path
path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from src.core import METRICS
out=[]
for (key,(label,group)),nums in zip(METRICS.items(),rows):
 assert abs(Decimal(nums[0])+Decimal(nums[1])-Decimal(nums[2]))<Decimal('.001')
 for cur,val in zip(('TP','YP','TOTAL'),nums):
  out.append({'source':'bddk_weekly','source_url':'https://www.bddk.gov.tr/BultenHaftalik/','period':'2026-10-23','scope':'sector','metric_id':key,'label':label,'group':group,'currency':cur,'unit':'million_try','value':float(Decimal(val)),'status':'official'})
pathlib.Path(__file__).with_name('bddk_2026_10_23_verified.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(len(out))
