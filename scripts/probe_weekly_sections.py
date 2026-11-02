"""Read-only map of BDDK weekly bulletin sections; do not output financial values."""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.bddk.gov.tr/BultenHaftalik/"
session = requests.Session()
landing = session.get(URL, timeout=25)
landing.raise_for_status()
soup = BeautifulSoup(landing.text, "html.parser")

for element in soup.find_all(attrs={"onclick": True}):
    action = element.get("onclick", "")
    match = re.search(r"TabloDegistir\s*\(\s*['\"]?(\d+)", action)
    if match:
        name = element.get_text(" ", strip=True)
        print("SECTION_LINK", match.group(1), repr(name[:140]))

form = next((f for f in soup.find_all("form") if f.find("input", attrs={"name": "tabloId"})), None)
if form is None:
    raise RuntimeError("Official table selector not found")
from urllib.parse import urljoin
endpoint = urljoin(landing.url, form.get("action") or landing.url)
token = form.find("input", attrs={"name": "__RequestVerificationToken"})
token_value = token.get("value") if token else None
if not endpoint.startswith("https://www.bddk.gov.tr/BultenHaftalik/"):
    raise RuntimeError("Unexpected endpoint")

for table_id in range(1, 9):
    values = {"tabloId": str(table_id)}
    if token_value:
        values["__RequestVerificationToken"] = token_value
    try:
        response = session.post(endpoint, data=values, headers={"Referer": landing.url}, timeout=25)
        response.raise_for_status()
        parsed = BeautifulSoup(response.text, "html.parser")
        table = parsed.find("table", id="TabloExcel2")
        if table is None:
            print("SECTION", table_id, "NO_HIGH_PRECISION_TABLE")
            continue
        rows = []
        for tr in table.find_all("tr"):
            cells = [t.get_text(" ", strip=True) for t in tr.find_all(["td", "th"], recursive=False)]
            if cells:
                rows.append(cells)
        header = rows[0][:5] if rows else []
        labels = []
        for row in rows[1:]:
            if len(row) >= 3 and re.fullmatch(r"\d{1,3}", row[0]):
                labels.append((row[0], row[1]))
        fulltext = parsed.get_text(" ", strip=True)
        match = re.search(r"Tarih\s*:\s*\d{1,2}\s+\S+\s+20\d\d", fulltext)
        print("SECTION", table_id, "DATE", match.group(0) if match else "NONE", "HEADER", repr(header), "ROWS", len(labels))
        for number, name in labels[:65]:
            print("LABEL", table_id, number, repr(name))
    except requests.RequestException as exc:
        print("SECTION_ERROR", table_id, type(exc).__name__)
