"""International Cost of Capital -- Streamlit assignment app.
Run: streamlit run app.py
"""
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from data_sources import (
    BETAS_URL, BONDS_URL, OECD_PAGE, RATINGS_URL,
    get_public_data,
)
from finance import compute_costs, verify_invariants

st.set_page_config(page_title='International Cost of Capital', page_icon='🌐', layout='wide')
st.markdown('''<style>
.block-container {padding-top:1.6rem; max-width:1450px}
h1, h2, h3 {letter-spacing:-.025em}
[data-testid="stMetric"] {background-color:rgba(120,130,160,.065);padding:15px;border-radius:11px;border:1px solid rgba(120,130,160,.17)}
.kicker {color:#527AB4;letter-spacing:.08em;text-transform:uppercase;font-size:.75rem;font-weight:700}
.note {color:#748198;font-size:.86rem}
</style>''', unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    return get_public_data()


def pct(value):
    return f'{value*100:.3f}%'


def manual_input(label: str, slug: str, source: float | None, min_value: float = 0.0,
                 max_value: float = 100.0, precision: int = 2):
    """Values are supplied in percentage points except beta."""
    on = st.checkbox(f'Override {label}', key=f'check_{slug}', value=False)
    if on:
        default = float(source) if source is not None else 0.0
        return st.number_input(f'{label} (manual)', min_value=min_value,
                               max_value=max_value, value=default,
                               step=0.01 if precision == 2 else 0.1,
                               format=f'%.{precision}f', key=f'input_{slug}')
    return source


head_a, head_b = st.columns([5, 1])
with head_a:
    st.markdown('<div class="kicker">Project finance · international valuation</div>', unsafe_allow_html=True)
    st.title('International Cost of Capital')
    st.caption('Compare the same project in USD and your selected country’s currency. Sources and vintages are visible below.')
with head_b:
    st.write('')
    if st.button('↻ Refresh data', type='primary', use_container_width=True,
                 help='Refetches public pages and clears the one-hour cached data'):
        st.cache_data.clear()
        st.rerun()

with st.spinner('Loading public market and tax data…'):
    data, meta = load_data()

betas_df = data['betas'].copy()
bonds_df = data['bonds'].copy()
taxes_df = data['taxes'].copy()

industries = sorted(betas_df['industry'].dropna().astype(str).unique().tolist())
countries = sorted(set(bonds_df['country'].dropna().astype(str).unique()) | {'United States'})
DEFAULT_INDUSTRY = 'Software (System & Application)'
CURRENCY_CODES = {
    'Australia':'AUD','Austria':'EUR','Belgium':'EUR','Brazil':'BRL','Bulgaria':'BGN',
    'Canada':'CAD','Chile':'CLP','China':'CNY','Colombia':'COP','Croatia':'EUR',
    'Czech Republic':'CZK','Denmark':'DKK','Euro area':'EUR','Finland':'EUR','France':'EUR',
    'Germany':'EUR','Greece':'EUR','Hong Kong':'HKD','Hungary':'HUF','Iceland':'ISK',
    'India':'INR','Indonesia':'IDR','Ireland':'EUR','Israel':'ILS','Italy':'EUR',
    'Japan':'JPY','Kenya':'KES','Lithuania':'EUR','Malaysia':'MYR','Mexico':'MXN',
    'Netherlands':'EUR','New Zealand':'NZD','Nigeria':'NGN','Norway':'NOK',
    'Pakistan':'PKR','Peru':'PEN','Philippines':'PHP','Poland':'PLN','Portugal':'EUR',
    'Romania':'RON','Russia':'RUB','Singapore':'SGD','Slovakia':'EUR','Slovenia':'EUR',
    'South Africa':'ZAR','South Korea':'KRW','Spain':'EUR','Sweden':'SEK',
    'Switzerland':'CHF','Taiwan':'TWD','Thailand':'THB','Turkey':'TRY',
    'United Kingdom':'GBP','United States':'USD','Vietnam':'VND','Zambia':'ZMW',
}


with st.sidebar:
    st.header('Project settings')
    industry = st.selectbox('Industry', industries,
        index=industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0)
    country = st.selectbox('Target country', countries,
        index=countries.index('United States'))
    erp_pct = st.slider('Equity risk premium (%)', 0.0, 20.0, 6.5, step=0.1,
                        help='The same ERP is used for the USD and target-currency CAPM calculations.')
    debt_pct = st.slider('Debt financing (D/V, %)', 0, 95, 30, step=1,
                         help='Debt share is D/(D+E). The slider excludes 100% debt because Hamada D/E would be undefined.')
    currency_code = CURRENCY_CODES.get(country, 'local currency')
    st.caption(f'Selected currency: **{currency_code}**')
    selected_tax = st.radio('Use project corporate tax rate from',
                           ['United States', 'Target country'], horizontal=True)
    st.caption('The chosen tax rate is used in BOTH currency calculations.')

industry_beta = float(betas_df.loc[betas_df['industry'] == industry,'unlevered_beta'].iloc[0])


def selected_rate(df, country_name, value_col):
    matches = df.loc[df['country'] == country_name, value_col]
    return float(matches.iloc[0]) if len(matches) else None

us_tax_pct = selected_rate(taxes_df, 'United States', 'tax_pct')
foreign_tax_pct = selected_rate(taxes_df, country, 'tax_pct')
us_yield_pct = selected_rate(bonds_df, 'United States', 'yield_pct')
foreign_yield_pct = selected_rate(bonds_df, country, 'yield_pct')
if country == 'United States':
    foreign_tax_pct = us_tax_pct
    foreign_yield_pct = us_yield_pct
usd_bbb_spread_pct = float(data['ratings']) * 100

with st.expander('Manual data overrides', expanded=False):
    st.caption('Check any field to replace its retrieved/snapshot value. All rate inputs here are percentages, not decimals.')
    ov1, ov2 = st.columns(2)
    with ov1:
        override_beta = st.checkbox('Override unlevered beta', key='manual_beta_enable')
        beta = st.number_input('Unlevered beta', min_value=0.0, max_value=20.0,
            value=industry_beta, step=0.01, format='%.3f', key=f'manual_beta_{industry}') if override_beta else industry_beta
        us_tax_pct = manual_input('U.S. corporate tax rate (%)', 'us_tax', us_tax_pct)
        us_yield_pct = manual_input('U.S. 10-year government yield (%)', 'us_yield', us_yield_pct,
                                  min_value=-10.0, max_value=100.0)
        usd_bbb_spread_pct = manual_input('USD BBB spread (%)', 'usd_spread', usd_bbb_spread_pct)
    with ov2:
        target_tax_key = f'foreign_tax_{country}'
        if country == 'United States':
            st.caption('Target country is the U.S. — the U.S. tax and bond yield values above apply.')
        else:
            foreign_tax_pct = manual_input(f'{country} tax rate (%)', target_tax_key, foreign_tax_pct)
            foreign_yield_pct = manual_input(f'{country} 10-year yield (%)',
                                            f'foreign_yield_{country}', foreign_yield_pct,
                                            min_value=-10.0, max_value=100.0)
        spread_ov = st.checkbox('Override target-currency BBB spread', key='manual_foreign_spread_enable',
                                help='When off, this spread is calculated from the USD BBB spread and the two bond yields.')
        foreign_spread_override_pct = st.number_input('Target-currency BBB spread (%)',
            min_value=0.0, max_value=100.0, value=usd_bbb_spread_pct, step=0.01,
            format='%.3f', key='manual_foreign_spread') if spread_ov else None

# A U.S. target represents the same currency by default. A target-currency spread
# override may intentionally create a different borrowing assumption for testing.
if country == 'United States':
    foreign_yield_pct = us_yield_pct
    foreign_tax_pct = us_tax_pct

if us_yield_pct is None:
    st.error('U.S. 10-year yield unavailable: enter a manual value under Data overrides.'); st.stop()
if foreign_yield_pct is None:
    st.error('Selected country 10-year yield unavailable: enter a manual value under Data overrides.'); st.stop()
if us_tax_pct is None:
    st.error('U.S. statutory tax rate unavailable: enter a manual value under Data overrides.'); st.stop()
if selected_tax == 'Target country' and foreign_tax_pct is None:
    st.error(f'OECD tax rate is unavailable for {country}. Enable its manual tax override before using its tax rate.'); st.stop()

tax_pct = us_tax_pct if selected_tax == 'United States' else foreign_tax_pct
params = dict(unlevered_beta=beta,
              tax_rate=tax_pct/100,
              debt_share=debt_pct/100,
              equity_risk_premium=erp_pct/100,
              us_gov_yield=us_yield_pct/100,
              foreign_gov_yield=foreign_yield_pct/100,
              usd_bbb_spread=usd_bbb_spread_pct/100,
              foreign_bbb_spread_override=None if foreign_spread_override_pct is None else foreign_spread_override_pct/100)

try:
    result = compute_costs(**params)
except ValueError as e:
    st.error(f'Invalid input: {e}'); st.stop()

outdated_sources = [name for name,record in meta.items() if record['status'] != 'LIVE FETCH']
if outdated_sources:
    st.warning('Some sources could not be fetched live. Displayed values include **dated reference snapshots**, '
               'not current market observations. Use **Refresh data** and check the source table before submitting.')

# Primary side-by-side result
st.subheader('Results for your project')
a, b = st.columns(2, gap='large')
for col, caption, iso, equity, debt, wacc, yield_value, spread_value in [
    (a, 'United States', 'USD', result.usd_equity_cost, result.usd_debt_cost,
     result.usd_wacc, result.us_gov_yield, result.usd_bbb_spread),
    (b, country, currency_code,
     result.foreign_equity_cost, result.foreign_debt_cost, result.foreign_wacc,
     result.foreign_gov_yield, result.foreign_bbb_spread_used),
]:
    with col:
        st.markdown(f'#### {caption} · {iso}')
        st.metric('WACC', pct(wacc))
        mc1, mc2 = st.columns(2)
        mc1.metric('Cost of equity', pct(equity))
        mc2.metric('Pre-tax cost of debt', pct(debt))
        st.caption(f'10-year bond yield: **{pct(yield_value)}**  ·  BBB spread: **{pct(spread_value)}**')

st.markdown('##### Currency difference')
st.caption(f'Target-currency WACC minus USD WACC: **{(result.foreign_wacc-result.usd_wacc)*100:+.3f} percentage points**. '
           'These are discount rates in different currency units; compare projects to same-currency cash flows.')

row1,row2,row3,row4 = st.columns(4)
row1.metric('Unlevered beta', f'{result.unlevered_beta:.3f}')
row2.metric('Relevered beta', f'{result.levered_beta:.3f}')
row3.metric('Common project tax rate', pct(result.tax_rate), selected_tax)
row4.metric('Auto foreign BBB spread', pct(result.foreign_bbb_spread_auto),
            'overridden' if spread_ov else 'used')

chart_rows = pd.DataFrame({
    'Measure':['Cost of equity','Pre-tax cost of debt','WACC'],
    'USD':[result.usd_equity_cost*100,result.usd_debt_cost*100,result.usd_wacc*100],
    'Target currency':[result.foreign_equity_cost*100,result.foreign_debt_cost*100,result.foreign_wacc*100],
}).set_index('Measure')
st.bar_chart(chart_rows, x_label='', y_label='Annual discount rate (%)', horizontal=True)

with st.expander('Show formulas and assumptions', expanded=True):
    st.markdown(r'''
**1. Relever the industry beta with the selected project tax and debt share.**

$$\beta_L = \beta_U\left(1+(1-T)\frac{D/V}{1-D/V}\right)$$

**2. Cost of equity in each currency (same project beta and ERP).**

$$K_{e,USD}=r_{US}+\beta_L\times ERP$$
$$K_{e,F}=r_F+\beta_L\times ERP$$

**3. BBB pre-tax borrowing cost in each currency.**

$$K_{d,USD}=r_{US}+s_{BBB,USD}$$
$$s_{BBB,F}^{auto}=s_{BBB,USD}\left(\frac{1+r_F}{1+r_{US}}\right)$$
$$K_{d,F}=r_F+s_{BBB,F}$$

When the foreign BBB override is enabled, its entered value replaces the calculated
spread **only in the foreign-currency debt cost**.

**4. WACC, using the same project tax rate, debt share, and ERP.**

$$WACC_c=(1-D/V)K_{e,c}+(D/V)K_{d,c}(1-T)$$

**Modeling assumptions:** annual nominal yields; 10-year sovereign yields serve as local-currency
risk-free *proxies*; U.S. industry unlevered beta applies to the project; marginal/combined
statutory tax rather than the industry's historical effective tax rate; BBB credit quality;
no issuance fees, FX hedging cost, additional country-risk premium, or market-value debt
adjustments. Foreign spread translation uses the ratio of bond accumulation factors.
For some emerging countries, a sovereign yield contains credit and liquidity risk, so treating
it as risk-free is an approximation.

**Important:** the assignment says the instructor provides the exact formulas in class.
This app implements a clearly documented same-ERP CAPM and relative-yield-spread model.
Check these conventions against the class handout before final submission.
''')

st.subheader('All-industry comparison')
st.caption(f'Applies the same country, yields, spread, financing mix, ERP, and project tax rate to each Damodaran industry beta. Target WACC is denominated in {currency_code}.')
compare = []
for item in betas_df.itertuples(index=False):
    candidate = float(beta) if item.industry == industry else float(item.unlevered_beta)
    value = compute_costs(**{**params, 'unlevered_beta':candidate})
    compare.append({
        'Industry':item.industry, 'Selected':'●' if item.industry == industry else '',
        'Unlevered beta':candidate, 'Levered beta':value.levered_beta,
        'USD cost of equity (%)':value.usd_equity_cost*100,
        'Target cost of equity (%)':value.foreign_equity_cost*100,
        'USD cost of debt (%)':value.usd_debt_cost*100,
        'Target cost of debt (%)':value.foreign_debt_cost*100,
        'USD WACC (%)':value.usd_wacc*100,
        f'{currency_code} WACC (%)':value.foreign_wacc*100,
    })
compare_df = pd.DataFrame(compare).sort_values('USD WACC (%)').reset_index(drop=True)
col1,col2 = st.columns([2,1])
with col2:
    sort_by = st.selectbox('Sort industries', ['USD WACC (%)', f'{currency_code} WACC (%)', 'Industry'], index=0)
compare_df = compare_df.sort_values(sort_by, ascending=True).reset_index(drop=True)
st.dataframe(compare_df, use_container_width=True, hide_index=True,
             column_config={
                 'Unlevered beta':st.column_config.NumberColumn(format='%.3f'),
                 'Levered beta':st.column_config.NumberColumn(format='%.3f'),
                 **{c:st.column_config.NumberColumn(format='%.3f%%') for c in compare_df.columns if '(%)' in c},
             })

st.subheader('Download your results')
export = {
    'generated_at_utc':datetime.utcnow().isoformat(timespec='seconds')+'Z',
    'industry':industry, 'target_country':country, 'target_currency':currency_code,
    'selected_project_tax_basis':selected_tax,
    'input_rates_are_decimals':True,
    'inputs':params,
    'outputs':result.to_dict(),
    'source_metadata':meta,
    'methodology':'Same-ERP additive CAPM; BBB foreign spread = USD BBB spread * (1+r_foreign)/(1+r_US)',
}
s1,s2,s3 = st.columns(3)
with s1:
    st.download_button('Download scenario JSON', json.dumps(export, indent=2).encode('utf-8'),
                       file_name='international_wacc_scenario.json', mime='application/json', use_container_width=True)
with s2:
    csv = pd.DataFrame([
        {'Currency':'USD','Cost of equity (%)':result.usd_equity_cost*100,
         'Cost of debt (%)':result.usd_debt_cost*100,'WACC (%)':result.usd_wacc*100},
        {'Currency':currency_code,'Cost of equity (%)':result.foreign_equity_cost*100,
         'Cost of debt (%)':result.foreign_debt_cost*100,'WACC (%)':result.foreign_wacc*100},
    ]).to_csv(index=False).encode('utf-8')
    st.download_button('Download project CSV', csv, file_name='project_costs.csv',
                       mime='text/csv', use_container_width=True)
with s3:
    st.download_button('Download all industries CSV', compare_df.to_csv(index=False).encode('utf-8'),
                       file_name='all_industry_wacc.csv', mime='text/csv', use_container_width=True)

st.subheader('Assignment verification')
checks = verify_invariants(**params)
for description, passed in checks.items():
    st.markdown(('✅' if passed else '❌') + ' ' + description)
st.caption('These checks run using the inputs currently selected above. Ten offline unit tests are also included in the repository.')

st.subheader('Source audit trail')
source_labels = {
    'betas':'Damodaran · U.S. industry unlevered betas',
    'ratings':'Damodaran · Baa2/BBB spread (large nonfinancial firms)',
    'taxes':'OECD · combined statutory corporate tax rate',
    'bonds':'Trading Economics · government 10-year yields',
}
trail = []
for key in ['betas','ratings','taxes','bonds']:
    record = meta[key]
    trail.append({'Data set':source_labels[key], 'Status':record['status'],
                  'Fetched at / snapshot vintage':record['date'],
                  'Source':record['url'], 'Warning':record['warning']})
st.dataframe(pd.DataFrame(trail), hide_index=True, use_container_width=True,
             column_config={'Source':st.column_config.LinkColumn('Source URL', display_text='Open source')})

with st.expander('Selected source values and dates'):
    st.write(f'**Damodaran unlevered beta**: {industry} = **{beta:.3f}**; public industry source vintage January 2026; '
             f'[source]({BETAS_URL}).' + (' (manually overridden)' if override_beta else ''))
    st.write(f'**Damodaran BBB borrowing spread**: **{usd_bbb_spread_pct:.3f}%**; public ratings source vintage January 2026; '
             f'[source]({RATINGS_URL}).')
    for cname,taxv in [('United States',us_tax_pct),(country,foreign_tax_pct)]:
        matching = taxes_df.loc[taxes_df['country']==cname,'year']
        vintage = str(int(matching.iloc[0])) if len(matching) else 'manual / unavailable'
        st.write(f'**OECD tax · {cname}**: {"not available" if taxv is None else f"{taxv:.2f}%"} '
                 f'(data year {vintage}); [OECD source]({OECD_PAGE}).')
    for cname,yld in [('United States',us_yield_pct),(country,foreign_yield_pct)]:
        matching = bonds_df.loc[bonds_df['country']==cname,'reference']
        vintage = str(matching.iloc[0]) if len(matching) else 'manual'
        st.write(f'**10-year yield · {cname}**: {yld:.3f}% (source reference {vintage}); '
                 f'[Trading Economics]({BONDS_URL}).')
    st.write('The source audit trail indicates whether figures were fetched live or read from an explicitly dated bundled snapshot.')

st.divider()
st.caption('Educational modeling tool. Do not mix a USD discount rate with foreign-currency cash flows. '
           'Always verify source vintages and the instructor’s provided formulas.')
