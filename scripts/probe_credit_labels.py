"""Only inspect public credit-line names and section headings, never persist unverified amounts."""
from bs4 import BeautifulSoup
import requests
import re
from src.core import SOURCES


def main():
    url = SOURCES['bddk_weekly']
    res = requests.get(url, timeout=30, headers={'User-Agent': 'BankScope/0.3 public-source-structure-check'})
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')
    for table_index, table in enumerate(soup.select('table')):
        rows=[]
        for tr in table.select('tr'):
            cells=[td.get_text(' ',strip=True) for td in tr.find_all(['th','td'],recursive=False)]
            n=next((i for i,x in enumerate(cells) if re.fullmatch(r'\d{1,2}',x)), None)
            if n is not None and int(cells[n]) in range(1,23) and len(cells)>=n+5:
                rows.append((int(cells[n]),cells[n+1]))
        if len(rows)>=20:
            print('TABLE',table_index,'ROW_COUNT',len(rows))
            for idx,label in rows:
                print(f'  {idx:02} {label}')


if __name__=='__main__':
    main()
