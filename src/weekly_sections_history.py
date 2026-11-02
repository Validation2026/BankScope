"""Source-verified historical backfill for BDDK deposits and nonperforming loans.

Uses actual BDDK table IDs and official period-selection POST with CSRF. Each
section/date is accepted only after full source-label and balance validation.
"""
from __future__ import annotations
from datetime import date
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from .core import SOURCES, save_archive
from .weekly_history import discover_period_form
from .bddk_sections import SECTION_SPECS, parse_section_html


def collect_one_section(section_id, processed_ids=(), max_new=8, recheck_recent=2, min_year=2022, session=None):
    if section_id not in SECTION_SPECS:
        raise ValueError("Unsupported BDDK section ID")
    session = session or requests.Session()
    source=SOURCES["bddk_weekly"]
    home=session.get(source,timeout=30,headers={"User-Agent":"BankScope official-source data"})
    home.raise_for_status()
    page=BeautifulSoup(home.text,"html.parser")
    form=next((f for f in page.find_all("form") if f.find("input",attrs={"name":"tabloId"})),None)
    if form is None:
        raise ValueError("Missing official BDDK section selector")
    endpoint=urljoin(home.url,form.get("action") or home.url)
    if not endpoint.startswith("https://www.bddk.gov.tr/BultenHaftalik/"):
        raise ValueError("Unapproved BDDK table selector URL")
    token=form.find("input",attrs={"name":"__RequestVerificationToken"})
    payload={"tabloId":str(section_id)}
    if token:
        payload["__RequestVerificationToken"]=token.get("value","")
    selected=session.post(endpoint,data=payload,timeout=30,headers={"Referer":home.url})
    selected.raise_for_status()
    # Verify the menu actually selected this table before changing the period.
    parse_section_html(selected.text,section_id)
    action,periods,csrf=discover_period_form(selected.text,selected.url)

    processed=set(map(str,processed_ids))
    recent=set(sorted(processed,key=int,reverse=True)[:recheck_recent])
    rows,completed,errors=[],[],[]
    last_year=date.today().year
    observed_dates=set()
    for entry in periods:
        if len(completed)>=max_new+len(recent):
            break
        id_=entry["id"]
        if id_ in processed and id_ not in recent:
            continue
        year=entry["year"] or str(last_year)
        if int(year)<min_year:
            continue
        data={"yil":year,"donemId":id_,"para":"TL"}
        if csrf:
            data["__RequestVerificationToken"]=csrf
        try:
            report=session.post(action,data=data,timeout=30,headers={"Referer":selected.url})
            report.raise_for_status()
            period,observations=parse_section_html(report.text,section_id)
            if entry["year"] and period[:4]!=entry["year"]:
                raise ValueError("Source year does not match period selection")
            if int(period[:4])<min_year:
                break
            if period in observed_dates:
                raise ValueError("Two official period IDs yielded the same date")
            observed_dates.add(period)
            save_archive("bddk_weekly_section_history_"+str(section_id),report.content,".html",report.url)
            completed.append(id_)
            rows.extend(observations)
            last_year=int(period[:4])
        except (requests.RequestException,ValueError) as exc:
            errors.append({"section_id":section_id,"period_id":id_,
                           "error_type":type(exc).__name__,"error":str(exc)[:160]})
            if len(errors)>=2:
                break
    return {"rows":rows, "completed_ids":completed,
            "new_ids":[x for x in completed if x not in processed],
            "rechecked_ids":[x for x in completed if x in processed],
            "failures":errors, "available_period_count":len(periods)}


def collect_section_histories(completed_by_section=None,max_new=8,recheck_recent=2):
    """Separate cookie sessions prevent one selected section leaking into another."""
    completed_by_section=completed_by_section or {}
    rows,processed,details=[],{},[]
    for section_id in (290,292):
        old=completed_by_section.get(str(section_id),[])
        try:
            result=collect_one_section(section_id,processed_ids=old,max_new=max_new,
                                       recheck_recent=recheck_recent,session=requests.Session())
            rows.extend(result["rows"])
            processed[str(section_id)]=sorted(set(map(str,old))|set(result["completed_ids"]),key=int)
            details.append({"section_id":section_id,
                            "new_periods":len(result["new_ids"]),
                            "rechecked_periods":len(result["rechecked_ids"]),
                            "errors":result["failures"][:2]})
        except (requests.RequestException,ValueError) as exc:
            processed[str(section_id)]=list(old)
            details.append({"section_id":section_id,"status":"failed_last_verified_retained",
                            "error":str(exc)[:180]})
    return {"rows":rows,"completed_by_section":processed,"details":details}
