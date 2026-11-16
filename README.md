# International Cost of Capital — Streamlit app

A classroom-ready interactive calculator for the cost of equity, pre-tax cost of debt and weighted-average cost of capital (WACC) in U.S. dollars and a target country's currency.

## Required submission functionality

- **Defaults**: `Software (System & Application)`, `United States`, U.S. corporate tax rate, `ERP = 6.5%`, `debt / total financing = 30%`.
- **Public data sources**: Damodaran's U.S. **unlevered** industry beta table, his **Baa2/BBB for large nonfinancial firms** spread, OECD combined **statutory corporate** rates and Trading Economics 10-year sovereign yields.
- **Source refresh** button, dated source audit trail and clearly labeled offline snapshots.
- Industry + target country selectors; adjustable ERP and debt share; U.S. versus selected country project tax selector.
- Manual overrides for industry beta, U.S. and target corporate taxes, the U.S. and target 10-year yields, U.S. BBB spread, and target BBB spread.
- When target BBB override is off, its value is **computed automatically** from the USD spread and both sovereign yields.
- Side-by-side equity costs, debt costs, WACC, charts, all-industry comparison and downloadable CSV/JSON results.
- Automated tests for the three invariants specified in the assignment.

## Install and run

Use Python 3.10 or newer (3.11 recommended). Inside the project folder:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

To run the verification suite:

```bash
python -m unittest -v test_finance.py
```

## Put on GitHub and Streamlit

1. Create a new GitHub repository, e.g. `international-cost-of-capital`. You can upload the contents of **this folder** directly using **Add file > Upload files** on GitHub. Keep `app.py`, `finance.py`, `data_sources.py`, `requirements.txt`, `README.md`, and the `data/` folder in the repository root. Alternatively, use Git:

   ```bash
   git init
   git add .
   git commit -m "Build international cost of capital calculator"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/international-cost-of-capital.git
   git push -u origin main
   ```

2. Go to [Streamlit Community Cloud](https://share.streamlit.io/), connect GitHub, click **Create app > Yup, I have an app**, choose the repository and `main` branch; use `app.py` as the main file. Click **Deploy**.
3. In the deployed app, click **Refresh data**, confirm the audit trail, test USD versus India or another country, exercise the overrides, and download a CSV.
4. Copy the repository link and `.streamlit.app` link into your submission document and attach AI-conversation screenshots (include what you personally tested).

Official Streamlit deploy directions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Financial formulas implemented

All input rates are converted to **decimals** in the calculation engine. The same `tax_rate`, `debt_share` and `equity_risk_premium` are used in both currencies:

```
D/E             = debt_share / (1 - debt_share)
levered_beta    = unlevered_beta * [1 + (1 - tax_rate) * D/E]
USD_equity      = US_10y_yield + levered_beta * ERP
Foreign_equity  = foreign_10y_yield + levered_beta * ERP
USD_debt        = US_10y_yield + USD_BBB_spread
foreign_spread  = USD_BBB_spread * (1 + foreign_10y_yield) / (1 + US_10y_yield)
Foreign_debt    = foreign_10y_yield + foreign_spread
USD_WACC        = (1-debt_share)*USD_equity + debt_share*USD_debt*(1-tax_rate)
Foreign_WACC    = (1-debt_share)*Foreign_equity + debt_share*Foreign_debt*(1-tax_rate)
```

The final foreign spread can be overwritten manually; this **does not** affect any USD result.

**Important classroom qualification:** The assignment screenshot says formulas will be provided in class. This implementation chooses the additive, same-ERP CAPM in each currency and a relative-bond-factor conversion of the USD BBB spread. The class may have a different convention (such as Fisher translation of the entire equity return). Confirm the exact class formulas before submitting.

## Independent numerical verification (2026 reference snapshot)

Example: Software (System & Application), project modeled in USD vs INR; project tax uses U.S. combined statutory rate.

| Input | Value | Source vintage |
|---|---:|---|
| Unlevered beta | 1.23 | Damodaran Jan 2026 |
| U.S. BBB spread | 1.11% | Damodaran Jan 2026 |
| U.S. combined statutory CIT | 25.53% | OECD 2026 |
| U.S. 10-year yield | 5.14% | Trading Economics Nov 16, 2026 snapshot |
| India 10-year yield | 7.32% | Trading Economics Nov 16, 2026 snapshot |
| ERP | 6.50% | Assignment default |
| D/V | 30.00% | Assignment default |

Calculation independent from the app:

- D/E = `0.30 / 0.70 = 0.4285714286`.
- Levered beta = `1.23 * [1 + (1 - 0.2553)*0.4285714286] = 1.6225632857`.
- USD cost of equity = `0.0514 + 1.6225632857*0.065 = 15.6866613571%`.
- USD debt cost = `0.0514+0.0111 = 6.2500000000%`.
- **USD WACC = `0.70*0.156866613571 + 0.30*0.0625*(1-0.2553)` = `12.37697545%`.**
- Auto foreign spread = `0.0111*(1.0732/1.0514) = 1.1330150276%`.
- India-currency equity cost = `0.0732+1.6225632857*0.065 = 17.8666613571%`.
- India-currency debt cost = `0.0732+0.011330150276 = 8.4530150276%`.
- **India-currency WACC = `14.3951510373%`.**

These equations are also in the separately provided **Excel independent verification** workbook. It contains live formulas and three test scenarios.

## Invariant checks

1. Equal government yields, with foreign spread override off, cause both equity costs, both debt costs and both WACCs to match.
2. Zero debt makes WACC equal the cost of equity in each currency.
3. Manually changing the foreign BBB spread does not change the USD equity, debt or WACC results.

Run `python -m unittest -v test_finance.py`; the tests work offline without requesting any third-party data.

## Source data and limitations

- **Betas:** https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html (January 2026). HTML parser is used first; `.xls` is the fallback download.
- **BBB default spread:** https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html (January 2026, Baa2/BBB, large non-financial service firms).
- **Taxes:** https://www.oecd.org/en/data/datasets/corporate-income-tax-rates-database.html; fetched through the OECD SDMX CSV API, retaining the latest available year for each country and the combined statutory general-government rate.
- **Sovereign yields:** https://tradingeconomics.com/country-list/government-bond-10y; public HTML table, not a private API.

The app fetches all four sources concurrently, caches results for one hour, and displays a **dated snapshot** clearly when the source cannot be reached. The bundled January 2026 beta snapshot covers 94 source industry rows, with 56 published country bond yields from the 16 November 2026 Trading Economics reference page. The bundled OECD fallback contains **only the verified 2026 U.S. statutory rate**. The selected-country tax can be used when live OECD data are available, or entered manually when not. This avoids making up foreign tax rates.

**Risks:** Website layouts, anti-scraping defenses and OECD API schemas can change. The entire app was tested for Python syntax, offline source fallbacks and calculation invariants in the build environment; live fetches and Streamlit deployment require testing in a network-connected environment. Bond yields change daily, so do not cite a fallback as a current quote. High-country-risk sovereign yields are not always clean risk-free proxies.

## Project files

- `app.py` — Streamlit controls, visualizations, results, source audit and downloads
- `finance.py` — side-effect-free WACC calculations
- `data_sources.py` — source retrieval, parsers, cache-friendly data structure and snapshot fallback
- `data/` — dated backup data files (explicitly labeled in the UI)
- `test_finance.py` — unit tests for formulas, parsing and assignment invariants
- `requirements.txt` — deployment dependencies
