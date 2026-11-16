"""Run locally: python -m unittest -v test_finance.py"""
import math
import unittest
from finance import compute_costs, verify_invariants
from data_sources import parse_bbb_spread_html, parse_betas_html, parse_oecd_csv, parse_bonds_html

DEFAULT = dict(unlevered_beta=1.23, tax_rate=0.2553, debt_share=0.30,
               equity_risk_premium=0.065, us_gov_yield=0.0514,
               foreign_gov_yield=0.0732, usd_bbb_spread=0.0111,
               foreign_bbb_spread_override=None)


class CapitalCostTests(unittest.TestCase):
    def test_independent_us_formula(self):
        result = compute_costs(**DEFAULT)
        self.assertAlmostEqual(result.levered_beta, 1.6225632857142858, places=12)
        self.assertAlmostEqual(result.usd_equity_cost, 0.15686661357142856, places=12)
        self.assertAlmostEqual(result.usd_debt_cost, 0.0625, places=12)
        self.assertAlmostEqual(result.usd_wacc, 0.1237697545, places=12)

    def test_equal_gov_yields(self):
        x = compute_costs(**{**DEFAULT, 'foreign_gov_yield':DEFAULT['us_gov_yield']})
        self.assertAlmostEqual(x.usd_equity_cost, x.foreign_equity_cost, places=12)
        self.assertAlmostEqual(x.usd_debt_cost, x.foreign_debt_cost, places=12)
        self.assertAlmostEqual(x.usd_wacc, x.foreign_wacc, places=12)

    def test_zero_debt(self):
        x = compute_costs(**{**DEFAULT,'debt_share':0.0})
        self.assertAlmostEqual(x.usd_equity_cost, x.usd_wacc, places=12)
        self.assertAlmostEqual(x.foreign_equity_cost, x.foreign_wacc, places=12)

    def test_foreign_override_does_not_change_usd(self):
        original = compute_costs(**DEFAULT)
        changed = compute_costs(**{**DEFAULT,'foreign_bbb_spread_override':0.04})
        for name in ['usd_equity_cost','usd_debt_cost','usd_wacc']:
            self.assertAlmostEqual(getattr(original,name),getattr(changed,name),places=12)
        self.assertNotAlmostEqual(original.foreign_wacc,changed.foreign_wacc,places=8)

    def test_all_invariants(self):
        self.assertTrue(all(verify_invariants(**DEFAULT).values()))

    def test_reject_full_debt(self):
        with self.assertRaises(ValueError):
            compute_costs(**{**DEFAULT,'debt_share':1})

    def test_bbb_parser(self):
        html='<table><tr><td>2.5</td><td>2.99</td><td>Baa2/BBB</td><td>1.11%</td><td>0.9</td></tr></table>'
        self.assertEqual(parse_bbb_spread_html(html), 0.0111)

    def test_beta_parser(self):
        rows = ''.join(f'<tr><td>Sector {i}</td><td>{i+0.50}</td></tr>' for i in range(20))
        html = '<table><tr><th>Industry Name</th><th>Unlevered beta</th></tr>'+rows+'</table>'
        self.assertEqual(len(parse_betas_html(html)), 20)

    def test_tax_parser(self):
        csv = 'REF_AREA,TIME_PERIOD,OBS_VALUE,MEASURE,TARGETING,INSTITUTIONAL_SECTOR\nUSA,2026,25.53,CIT_C,ST,S13\nUSA,2025,25.57,CIT_C,ST,S13\nIND,2026,22.00,CIT_C,ST,S13\nUSA,2026,21.00,CIT_C,ST,S1311\n'
        df = parse_oecd_csv(csv)
        self.assertEqual(float(df.loc[df.country=='United States','tax_pct'].iloc[0]),25.53)
        self.assertEqual(len(df),2)

    def test_bond_parser(self):
        rows = ''.join(f'<tr><td>Country {i}</td><td>5.5</td><td>Nov/26</td></tr>' for i in range(16))
        html='<table><tr><th>Country</th><th>Last</th><th>Reference</th></tr>'+rows+'<tr><td>United States</td><td>5.14</td><td>Nov/26</td></tr></table>'
        df = parse_bonds_html(html)
        self.assertEqual(float(df.loc[df.country=='United States','yield_pct'].iloc[0]), 5.14)

if __name__ == '__main__':
    unittest.main()
