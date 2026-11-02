"""Check that the official BDDK historical period form preserves selected section."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.weekly_history import discover_period_form
from src.bddk_sections import parse_section_html

URL="https://www.bddk.gov.tr/BultenHaftalik/"
s=requests.Session()
for section_id in (290,292):
    home=s.get(URL,timeout=25);home.raise_for_status()
    soup=BeautifulSoup(home.text,"html.parser")
    selector=next(f for f in soup.find_all("form") if f.find("input",attrs={"name":"tabloId"}))
    endpoint=urljoin(home.url,selector.get("action") or home.url)
    token=selector.find("input",attrs={"name":"__RequestVerificationToken"})
    payload={"tabloId":str(section_id)}
    if token:payload["__RequestVerificationToken"]=token.get("value","")
    selected=s.post(endpoint,data=payload,headers={"Referer":home.url},timeout=25)
    selected.raise_for_status()
    selected_date,selected_rows=parse_section_html(selected.text,section_id)
    print("CURRENT",section_id,selected_date,len(selected_rows))
    action, options, csrf=discover_period_form(selected.text,selected.url)
    target_entries=[e for e in options if e['id'] in {'663','662','661'}] if section_id==292 else options[1:3]
    for entry in target_entries:
        year=entry["year"] or "2026"
        data={"yil":year,"donemId":entry["id"],"para":"TL"}
        if csrf:data["__RequestVerificationToken"]=csrf
        response=None
        try:
            response=s.post(action,data=data,headers={"Referer":selected.url},timeout=25)
            response.raise_for_status()
            period,rows=parse_section_html(response.text,section_id)
            print("HISTORY",section_id,entry["id"],period,len(rows),"VALID")
        except (requests.RequestException,ValueError) as err:
            print("HISTORY",section_id,entry["id"],type(err).__name__,str(err)[:90])
            if response is not None:
                table=BeautifulSoup(response.text,"html.parser").find("table",id="TabloExcel2")
                if table is not None:
                    labels=[]
                    for tr in table.find_all("tr"):
                        cells=[c.get_text(" ",strip=True) for c in tr.find_all(["td","th"],recursive=False)]
                        if cells and cells[0].isdigit():
                            labels.append((cells[0],cells[1] if len(cells)>1 else "MISSING",len(cells)))
                    print("REJECTED_SCHEMA",section_id,entry["id"],len(labels),labels[:30])
