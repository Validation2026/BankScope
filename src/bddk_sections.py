"""Strict verified reader for official BDDK weekly NPL and deposit tables.

Never infer a source from row order alone. Require official table ID,
source heading, exact row labels, denomination and published balance identities.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from .bddk import MONTHS
from .core import SOURCES, normalize, turkish_decimal, save_archive

SECTION_SPECS = {
    290: {
        "group": "Takipteki Alacaklar",
        "metric_ids": (
            "npl_total", "npl_retail_plus_cards", "npl_consumer_loans",
            "npl_housing", "npl_auto", "npl_personal", "npl_retail_cards",
            "npl_commercial_other", "npl_specific_provisions",
            "npl_installment_commercial", "npl_corporate_cards", "npl_sme",
        ),
        "labels": (
            "Takipteki Alacaklar (2+8)",
            "Tüketici Kredileri ve Bireysel Kredi Kartları (3+7)",
            "Tüketici Kredileri (4+5+6)",
            "a) Konut", "b) Taşıt", "c) İhtiyaç",
            "Bireysel Kredi Kartları",
            "Ticari ve Diğer Krediler",
            "Takipteki Alacaklar Özel Karşılığı (-)",
            "Taksitli Ticari Krd. (Bilgi)",
            "Kurumsal Kredi Kartları (Bilgi)",
            "KOBİ Kredileri (Bilgi)",
        ),
        "identities": {1:(2,8), 2:(3,7), 3:(4,5,6)},
    },
    292: {
        "group": "Mevduat",
        "metric_ids": (
            "deposit_total", "deposit_households", "deposit_households_demand",
            "deposit_households_time", "deposit_businesses",
            "deposit_businesses_demand", "deposit_businesses_time",
            "deposit_public_other", "deposit_public_other_demand",
            "deposit_public_other_time", "deposit_insured",
        ),
        "labels": (
            "Mevduat (Katılım Fonu) (2+5+8)",
            "Gerçek Kişiler (3+4)", "a) Vadesiz", "b) Vadeli",
            "Ticari Kuruluşlar (6+7)", "a) Vadesiz", "b) Vadeli",
            "Resmi ve Diğer Kuruluşlar (9+10)", "a) Vadesiz", "b) Vadeli",
            "Sigortaya Tabi Mevduat (Bilgi)",
        ),
        "identities": {1:(2,5,8), 2:(3,4), 5:(6,7), 8:(9,10)},
    },
}


DISPLAY_LABELS = {
    290: (
        "Takipteki Alacaklar (Brüt)", "Takip - Bireysel Krediler ve Kartlar",
        "Takip - Tüketici Kredileri", "Takip - Konut Kredileri",
        "Takip - Taşıt Kredileri", "Takip - İhtiyaç Kredileri",
        "Takip - Bireysel Kredi Kartları", "Takip - Ticari ve Diğer Krediler",
        "Takip - Özel Karşılıklar", "Takip - Taksitli Ticari Krediler (Bilgi)",
        "Takip - Kurumsal Kredi Kartları (Bilgi)", "Takip - KOBİ Kredileri (Bilgi)",
    ),
    292: (
        "Toplam Mevduat ve Katılım Fonu", "Gerçek Kişi Mevduatı",
        "Gerçek Kişi - Vadesiz", "Gerçek Kişi - Vadeli",
        "Ticari Kuruluş Mevduatı", "Ticari Kuruluş - Vadesiz",
        "Ticari Kuruluş - Vadeli", "Resmi ve Diğer Kuruluş Mevduatı",
        "Resmi ve Diğer - Vadesiz", "Resmi ve Diğer - Vadeli",
        "Sigortaya Tabi Mevduat (Bilgi)",
    ),
}

def parse_section_html(html: str, section_id: int):
    if section_id not in SECTION_SPECS:
        raise ValueError("Unapproved BDDK section")
    spec = SECTION_SPECS[section_id]
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = re.search(
        r"Tarih\s*:\s*(\d{1,2})\s+"
        r"(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)"
        r"\s+(20\d\d)", text, re.I
    )
    if not match:
        raise ValueError("Missing official reporting date")
    period = date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1))).isoformat()
    if period > date.today().isoformat():
        raise ValueError("Future report cannot be published")
    table = soup.find("table", id="TabloExcel2")
    if table is None:
        raise ValueError("Missing high-precision BDDK table")
    header = table.find("tr")
    columns = [cell.get_text(" ", strip=True) for cell in header.find_all(["td", "th"], recursive=False)] if header else []
    if len(columns) != 5 or [normalize(c) for c in columns[-3:]] != ["tp", "yp", "toplam"]:
        raise ValueError("Currency columns changed")
    header_norm = normalize(columns[1])
    if normalize(spec["group"]) not in header_norm or "milyon tl" not in header_norm:
        raise ValueError("Wrong official section heading or unit")
    lines = {}
    for tr in table.find_all("tr"):
        cells = [v.get_text(" ", strip=True) for v in tr.find_all(["td","th"], recursive=False)]
        if not cells or not re.fullmatch(r"\d{1,3}", cells[0]):
            continue
        idx = int(cells[0])
        if len(cells) != 5 or idx < 1 or idx > len(spec["labels"]) or idx in lines:
            raise ValueError("Incomplete, repeated or unexpected BDDK source row")
        values = [turkish_decimal(x) for x in cells[2:]]
        if any(v is None for v in values):
            raise ValueError("Missing numeric value")
        if idx != 9 or section_id != 290:
            if any(v < 0 for v in values):
                raise ValueError("Unexpected negative BDDK amount")
        lines[idx] = (cells[1], values)
    if set(lines) != set(range(1,len(spec["labels"])+1)):
        raise ValueError("Incomplete official BDDK rows")
    for idx, expected in enumerate(spec["labels"], 1):
        if normalize(lines[idx][0]) != normalize(expected):
            raise ValueError(f"Unexpected official source label {section_id}/{idx}")
        values = lines[idx][1]
        if abs(values[0] + values[1] - values[2]) > 0.25:
            raise ValueError(f"TP + YP mismatch {section_id}/{idx}")
    for total_idx, components in spec["identities"].items():
        for currency_idx in range(3):
            diff = lines[total_idx][1][currency_idx] - sum(lines[i][1][currency_idx] for i in components)
            if abs(diff) > 0.25:
                raise ValueError(f"Balance hierarchy mismatch {section_id}/{total_idx}")
    results = []
    for idx, metric in enumerate(spec["metric_ids"],1):
        original, triple = lines[idx]
        # Repeated labels such as 'a) Vadesiz' become unambiguous by parent path.
        for currency, value in zip(("TP","YP","TOTAL"), triple):
            results.append({
                "source":"bddk_weekly", "source_url":SOURCES["bddk_weekly"],
                "period":period, "scope":"sector", "group":spec["group"],
                "metric_id":metric, "label":DISPLAY_LABELS[section_id][idx-1], "source_label":original,
                "source_row_number":idx, "source_table_id":"TabloExcel2",
                "source_section_id":section_id, "currency":currency,
                "unit":"million_try", "value":value, "status":"official",
            })
    return period, results


def collect_latest_sections(session=None, section_ids=(290,292)):
    """Change active BDDK section using its actual official menu ID."""
    session = session or requests.Session()
    source = SOURCES["bddk_weekly"]
    found, errors = [], []
    for section_id in section_ids:
        try:
            landing = session.get(source, timeout=30, headers={"User-Agent":"BankScope public-statistics"})
            landing.raise_for_status()
            soup = BeautifulSoup(landing.text, "html.parser")
            form = next((f for f in soup.find_all("form")
                         if f.find("input", attrs={"name":"tabloId"})),None)
            if form is None:
                raise ValueError("Official weekly table selector missing")
            endpoint = urljoin(landing.url, form.get("action") or landing.url)
            if not endpoint.startswith("https://www.bddk.gov.tr/BultenHaftalik/"):
                raise ValueError("Unapproved source form target")
            token = form.find("input", attrs={"name":"__RequestVerificationToken"})
            data = {"tabloId":str(section_id)}
            if token is not None:
                data["__RequestVerificationToken"] = token.get("value", "")
            response = session.post(endpoint,data=data,timeout=30,
                                    headers={"Referer":landing.url, "User-Agent":"BankScope public-statistics"})
            response.raise_for_status()
            period, rows = parse_section_html(response.text, section_id)
            save_archive("bddk_weekly_section_"+str(section_id),response.content,".html",response.url)
            found.extend(rows)
        except (requests.RequestException,ValueError) as exc:
            errors.append({"section_id":section_id, "error_type":type(exc).__name__, "error":str(exc)[:180]})
    return {"rows":found,"errors":errors,"sections_found":sorted(set(x["source_section_id"] for x in found))}
