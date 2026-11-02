"""Read-only discovery of BDDK's public form structure.

Does not send report requests, infer undocumented parameters, or publish numbers.
Logs field names and option counts, NEVER cookies or hidden field values.
Intended for a temporary GitHub Actions diagnostic before backfilling dates.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

URLS = {
    "weekly": "https://www.bddk.gov.tr/BultenHaftalik/",
    "monthly": "https://www.bddk.gov.tr/BultenAylik/tr/Home/Gelismis",
}


def summarize_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    forms = []
    for form in soup.find_all("form"):
        fields = []
        for tag in form.find_all(["input", "select", "button"]):
            if tag.name == "input" and tag.get("type", "").lower() in {"hidden", "password"}:
                fields.append({"tag": tag.name, "name": tag.get("name"), "type": tag.get("type")})
                continue
            field = {"tag": tag.name, "name": tag.get("name"), "id": tag.get("id")}
            if tag.name == "input":
                field["type"] = tag.get("type", "text")
            if tag.name == "select":
                options = tag.find_all("option")
                field["options_count"] = len(options)
                field["option_values_first"] = [x.get("value") for x in options[:4]]
                field["option_values_last"] = [x.get("value") for x in options[-4:]]
            fields.append(field)
        forms.append({
            "method": form.get("method", "GET").upper(),
            "action": urljoin(base_url, form.get("action", "")),
            "id": form.get("id"),
            "fields": fields,
        })
    scripts = []
    for tag in soup.select("script[src]"):
        path = urljoin(base_url, tag.get("src", ""))
        host = urlparse(path).hostname
        if host in {"bddk.gov.tr", "www.bddk.gov.tr", "bddk.org.tr", "www.bddk.org.tr"}:
            scripts.append(path)
    return {
        "title": soup.title.get_text(" ", strip=True)[:150] if soup.title else "",
        "forms": forms,
        "scripts": scripts[:50],
        "select_count": len(soup.find_all("select")),
        "table_count": len(soup.find_all("table")),
    }


def probe_weekly_periods(session: requests.Session) -> list[dict]:
    """Try two past dates through the official published period-selection form."""
    out = []
    try:
        landing = session.get(URLS["weekly"], timeout=25)
        landing.raise_for_status()
        soup = BeautifulSoup(landing.text, 'html.parser')
        form = next((f for f in soup.find_all('form') if f.find('select', attrs={'name': 'donemId'})), None)
        if form is None:
            return [{'status': 'form_missing'}]
        selector = form.find('select', attrs={'name': 'donemId'})
        options = [o.get('value') for o in selector.find_all('option') if o.get('value')]
        csrf = form.find('input', attrs={'name': '__RequestVerificationToken'})
        token = csrf.get('value') if csrf else None
        for period_id in options[1:3]:
            data = {'yil': '2026', 'donemId': period_id, 'para': 'TL'}
            if token:
                data['__RequestVerificationToken'] = token
            try:
                response = session.post(urljoin(landing.url, form.get('action', '')),
                                        data=data, timeout=25,
                                        headers={'Referer': landing.url})
                response.raise_for_status()
                content = BeautifulSoup(response.text, 'html.parser').get_text(' ', strip=True)
                date_match = re.search(r'Tarih\s*:\s*(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(20\d\d)', content)
                out.append({'period_id': period_id, 'status': 'response_received',
                            'http_status': response.status_code,
                            'reporting_date_text': date_match.group(0) if date_match else None,
                            'tables_count': len(BeautifulSoup(response.text, 'html.parser').find_all('table'))})
            except requests.RequestException as exc:
                out.append({'period_id': period_id, 'status': 'request_failed',
                            'error_type': type(exc).__name__})
    except requests.RequestException as exc:
        return [{'status': 'landing_failed', 'error_type': type(exc).__name__}]
    return out


def run(output: Path = Path("probe_report.json")) -> dict:
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "sites": {}}
    session = requests.Session()
    for name, url in URLS.items():
        try:
            response = session.get(url, timeout=25, headers={
                "User-Agent": "BankScope/0.3 (public-source-form-discovery)",
                "Accept": "text/html",
            })
            response.raise_for_status()
            summary = summarize_html(response.text, response.url)
            summary["status"] = "ok"
            summary["url"] = response.url
            result["sites"][name] = summary
        except requests.RequestException as exc:
            result["sites"][name] = {"status": "unavailable", "error_type": type(exc).__name__}
    # The historical selector is a read-only report request. Probe two older
    # published periods (no speculative IDs or values are ever published).
    if result["sites"].get("weekly", {}).get("status") == "ok":
        result["sites"]["weekly"]["sample_period_requests"] = probe_weekly_periods(session)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run(Path(os.environ.get("BANKSCOPE_PROBE_OUTPUT", "probe_report.json")))
