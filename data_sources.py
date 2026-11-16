"""Public-data retrieval plus dated, transparent reference snapshots.

The snapshot files are *not* passed off as live figures. Each endpoint is fetched
on refresh or when the one-hour Streamlit cache expires. Failed sources retain
an explicit offline status so the dashboard still permits manual scenarios.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parent / "data"
BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html"
BETAS_XLS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/"
            "OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A..ST..S13...?"
            "startPeriod=2024&dimensionAtObservation=AllDimensions&format=csvfile")
OECD_PAGE = "https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html"
BONDS_URL = "https://tradingeconomics.com/country-list/government-bond-10y"
USER_AGENT = "Mozilla/5.0 (compatible; International-WACC-Education/1.0; public-data-fetch)"

# Public-data country name normalizations. Missing OECD coverage is reported.
ISO_TO_NAME = {
    'AUS':'Australia','AUT':'Austria','BEL':'Belgium','BRA':'Brazil','BGR':'Bulgaria',
    'CAN':'Canada','CHL':'Chile','CHN':'China','COL':'Colombia','HRV':'Croatia',
    'CZE':'Czech Republic','DNK':'Denmark','FIN':'Finland','FRA':'France',
    'DEU':'Germany','GRC':'Greece','HKG':'Hong Kong','HUN':'Hungary',
    'ISL':'Iceland','IND':'India','IDN':'Indonesia','IRL':'Ireland',
    'ISR':'Israel','ITA':'Italy','JPN':'Japan','KEN':'Kenya','LTU':'Lithuania',
    'MYS':'Malaysia','MEX':'Mexico','NLD':'Netherlands','NZL':'New Zealand',
    'NGA':'Nigeria','NOR':'Norway','PAK':'Pakistan','PER':'Peru','PHL':'Philippines',
    'POL':'Poland','PRT':'Portugal','ROU':'Romania','RUS':'Russia','SGP':'Singapore',
    'SVK':'Slovakia','SVN':'Slovenia','ZAF':'South Africa','KOR':'South Korea',
    'ESP':'Spain','SWE':'Sweden','CHE':'Switzerland','TWN':'Taiwan',
    'THA':'Thailand','TUR':'Turkey','GBR':'United Kingdom','USA':'United States',
    'VNM':'Vietnam','ZMB':'Zambia','EST':'Estonia','LVA':'Latvia',
    'LUX':'Luxembourg','CRI':'Costa Rica','ARG':'Argentina','SAU':'Saudi Arabia',
    'ARE':'United Arab Emirates','EGY':'Egypt','MAR':'Morocco',
}


def _get(url: str) -> requests.Response:
    response = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/csv,*/*"}, timeout=12)
    response.raise_for_status()
    if len(response.content) < 100:
        raise ValueError("Source returned an unexpectedly short response")
    return response


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [" ".join(str(x) for x in c if not str(x).startswith('Unnamed'))
                  if isinstance(c, tuple) else str(c) for c in df.columns]
    df.columns = [re.sub(r'\s+', ' ', c).strip() for c in df.columns]
    return df


def _extract_betas_table(frame: pd.DataFrame) -> pd.DataFrame:
    frame = _flatten_columns(frame)
    cols = frame.columns.tolist()
    name_cols = [c for c in cols if 'industry name' in c.lower()]
    beta_cols = [c for c in cols if 'unlevered beta' in c.lower() and 'corrected' not in c.lower()]
    if not name_cols or not beta_cols:
        raise ValueError('Beta table did not include industry and unlevered beta columns')
    out = frame[[name_cols[0], beta_cols[0]]].copy()
    out.columns = ['industry', 'unlevered_beta']
    out['industry'] = out['industry'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
    out['unlevered_beta'] = pd.to_numeric(out['unlevered_beta'].astype(str).str.replace(',', ''), errors='coerce')
    out = out.dropna(subset=['unlevered_beta'])
    out = out[~out['industry'].str.lower().str.startswith(('total market', 'industry name'))]
    out = out[out['unlevered_beta'].between(0, 20)]
    return out.drop_duplicates('industry').sort_values('industry').reset_index(drop=True)


def parse_betas_html(html: str) -> pd.DataFrame:
    for frame in pd.read_html(StringIO(html)):
        try:
            result = _extract_betas_table(frame)
            if len(result) >= 15:
                return result
        except ValueError:
            continue
    raise ValueError('Could not identify the industry beta table')


def fetch_betas() -> pd.DataFrame:
    try:
        return parse_betas_html(_get(BETAS_URL).text)
    except (ValueError, ImportError, requests.RequestException):
        r = _get(BETAS_XLS_URL)
        # Damodaran's source XLS can include front-matter rows above the table.
        raw = pd.read_excel(BytesIO(r.content), header=None, engine='xlrd')
        for pos in range(min(len(raw), 25)):
            cells = [str(x).lower() for x in raw.iloc[pos].tolist()]
            if any('industry name' in x for x in cells) and any('unlevered beta' in x for x in cells):
                raw.columns = [str(v).strip() for v in raw.iloc[pos]]
                frame = raw.iloc[pos+1:].copy()
                return _extract_betas_table(frame)
        raise ValueError('Could not locate header row in Damodaran XLS')


def parse_bbb_spread_html(html: str) -> float:
    soup = BeautifulSoup(html, 'lxml')
    for tr in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['td','th'])]
        for index, cell in enumerate(cells):
            if re.search(r'\bBaa2\s*/\s*BBB\b', cell, re.IGNORECASE):
                if index + 1 < len(cells):
                    match = re.search(r'(-?\d+(?:\.\d+)?)\s*%', cells[index+1])
                    if match:
                        return float(match.group(1)) / 100
    text = soup.get_text(' ', strip=True)
    match = re.search(r'Baa2\s*/\s*BBB\s+(-?\d+(?:\.\d+)?)\s*%', text, re.I)
    if match:
        return float(match.group(1)) / 100
    raise ValueError('Baa2/BBB default spread not found in ratings table')


def fetch_bbb_spread() -> float:
    return parse_bbb_spread_html(_get(RATINGS_URL).text)


def _find_column(cols: list[str], options: list[str]) -> str | None:
    normalized = {re.sub(r'[^a-z0-9]', '', c.lower()): c for c in cols}
    for option in options:
        key = re.sub(r'[^a-z0-9]', '', option.lower())
        if key in normalized:
            return normalized[key]
    return None


def parse_oecd_csv(csv_text: str) -> pd.DataFrame:
    raw = pd.read_csv(StringIO(csv_text), dtype=str)
    raw.columns = [str(c).strip() for c in raw.columns]
    cols = raw.columns.tolist()
    area = _find_column(cols, ['REF_AREA', 'Reference area'])
    period = _find_column(cols, ['TIME_PERIOD', 'Time period'])
    value = _find_column(cols, ['OBS_VALUE', 'Observation value'])
    if not all((area, period, value)):
        raise ValueError('OECD CSV omitted REF_AREA / TIME_PERIOD / OBS_VALUE')
    measure = _find_column(cols, ['MEASURE', 'Combined measure', 'Measure'])
    targeting = _find_column(cols, ['TARGETING', 'Targeting'])
    sector = _find_column(cols, ['INSTITUTIONAL_SECTOR', 'Institutional sector'])
    if targeting:
        raw = raw[raw[targeting].astype(str).str.fullmatch('ST|Statutory', case=False, na=False)]
    if sector:
        raw = raw[raw[sector].astype(str).str.fullmatch('S13|General government', case=False, na=False)]
    if measure:
        vals = raw[measure].astype(str)
        # 2.0 uses CIT_C for the combined rate; some CSV formats use long labels.
        combined = vals.str.fullmatch('CIT_C', case=False, na=False) | vals.str.contains('combined corporate income tax rate', case=False, na=False)
        if combined.any():
            raw = raw[combined]
    df = raw[[area, period, value]].copy()
    df.columns = ['country', 'year', 'tax_pct']
    df['country'] = df['country'].map(lambda v: ISO_TO_NAME.get(str(v).upper(), str(v)))
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['tax_pct'] = pd.to_numeric(df['tax_pct'], errors='coerce')
    df = df.dropna()
    df = df[df['tax_pct'].between(0, 100) & df['year'].between(2020, 2100)]
    return df.sort_values('year', ascending=False).drop_duplicates('country').reset_index(drop=True)


def fetch_tax_rates() -> pd.DataFrame:
    r = _get(OECD_URL)
    if 'html' in r.headers.get('Content-Type', '').lower() and '<html' in r.text[:200].lower():
        raise ValueError('OECD endpoint sent HTML rather than CSV')
    df = parse_oecd_csv(r.text)
    if len(df) < 10 or 'United States' not in df['country'].values:
        raise ValueError('OECD data failed completeness check')
    return df


def parse_bonds_html(html: str) -> pd.DataFrame:
    # Pandas reads the public by-country table; this is not an authenticated API.
    for frame in pd.read_html(StringIO(html)):
        frame = _flatten_columns(frame)
        col = _find_column(frame.columns.tolist(), ['Country'])
        last = _find_column(frame.columns.tolist(), ['Last'])
        ref = _find_column(frame.columns.tolist(), ['Reference'])
        if col and last and len(frame) >= 15:
            out = frame[[col,last]+([ref] if ref else [])].copy()
            out.columns = ['country','yield_pct']+(['reference'] if ref else [])
            if 'reference' not in out:
                out['reference'] = 'Not stated'
            out['yield_pct'] = pd.to_numeric(out['yield_pct'].astype(str).str.replace('%', '', regex=False).str.replace(',','',regex=False), errors='coerce')
            out['country'] = out['country'].astype(str).str.strip()
            out = out[out['yield_pct'].between(-10, 100) & ~out['country'].str.lower().isin(['country list', 'report'])]
            if 'United States' in out['country'].values:
                return out.drop_duplicates('country').reset_index(drop=True)
    raise ValueError('Could not parse Trading Economics public 10-year bond table')


def fetch_bond_yields() -> pd.DataFrame:
    return parse_bonds_html(_get(BONDS_URL).text)


def get_public_data() -> tuple[dict, dict]:
    """Four sources fetched concurrently, with source-specific transparent fallbacks."""
    from concurrent.futures import ThreadPoolExecutor
    specs = {
        'betas': (fetch_betas, lambda:pd.read_csv(DATA_DIR/'betas_2026_01.csv'), BETAS_URL,'January 2026'),
        'ratings': (fetch_bbb_spread, lambda:0.0111, RATINGS_URL,'January 2026'),
        'taxes': (fetch_tax_rates, lambda:pd.read_csv(DATA_DIR/'tax_rates_2026.csv'), OECD_PAGE,'2026'),
        'bonds': (fetch_bond_yields, lambda:pd.read_csv(DATA_DIR/'bond_yields_2026_11_16.csv'), BONDS_URL,'16 November 2026 snapshot'),
    }
    datasets, meta = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {name:pool.submit(fn) for name, (fn,_,_,_) in specs.items()}
        for name, (fn, snapshot_fn, url, snapshot_date) in specs.items():
            try:
                datasets[name] = jobs[name].result()
                meta[name] = dict(status='LIVE FETCH', date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), url=url, warning='')
            except Exception as exc:
                datasets[name] = snapshot_fn()
                meta[name] = dict(status='DATED SNAPSHOT', date=snapshot_date, url=url,
                                  warning=f'Live fetch unavailable ({type(exc).__name__}). Verify the displayed source data before submitting.')
    return datasets, meta
