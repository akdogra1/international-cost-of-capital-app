"""Pure, independently testable finance calculations. All rates are decimals (0.065 = 6.5%)."""
from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True)
class CapitalCosts:
    unlevered_beta: float
    levered_beta: float
    tax_rate: float
    debt_share: float
    equity_risk_premium: float
    us_gov_yield: float
    foreign_gov_yield: float
    usd_bbb_spread: float
    foreign_bbb_spread_auto: float
    foreign_bbb_spread_used: float
    usd_equity_cost: float
    foreign_equity_cost: float
    usd_debt_cost: float
    foreign_debt_cost: float
    usd_wacc: float
    foreign_wacc: float

    def to_dict(self):
        return asdict(self)


def compute_costs(
    unlevered_beta: float,
    tax_rate: float,
    debt_share: float,
    equity_risk_premium: float,
    us_gov_yield: float,
    foreign_gov_yield: float,
    usd_bbb_spread: float,
    foreign_bbb_spread_override: float | None = None,
) -> CapitalCosts:
    """Calculate USD and foreign-currency project capital costs.

    Formula choice pending confirmation against class handout:
    - Hamada: BL = BU * [1 + (1-T) * D/E].
    - CAPM: Ke(currency) = local government yield + BL * same USD ERP.
    - USD debt: US government yield + USD Baa2/BBB default spread.
    - Foreign currency default spread: USD spread * (1+rf_foreign)/(1+rf_US).
      This is the spread implied by converting the whole USD debt return using
      a government yield ratio (relative yield / Fisher parity approximation).
    - WACC = (E/V)*Ke + (D/V)*Kd*(1-T).
    """
    numbers = [unlevered_beta, tax_rate, debt_share, equity_risk_premium,
               us_gov_yield, foreign_gov_yield, usd_bbb_spread]
    if foreign_bbb_spread_override is not None:
        numbers.append(foreign_bbb_spread_override)
    if not all(isfinite(float(x)) for x in numbers):
        raise ValueError("All input values must be finite.")
    if unlevered_beta < 0:
        raise ValueError("Unlevered beta must be nonnegative.")
    if not 0 <= tax_rate <= 1:
        raise ValueError("Tax rate must be between 0% and 100%.")
    if not 0 <= debt_share < 1:
        raise ValueError("Debt share must be at least 0% and less than 100%.")
    if equity_risk_premium < 0 or usd_bbb_spread < 0:
        raise ValueError("ERP and BBB spread must be nonnegative.")
    if foreign_bbb_spread_override is not None and foreign_bbb_spread_override < 0:
        raise ValueError("Foreign BBB spread cannot be negative.")
    if us_gov_yield <= -1 or foreign_gov_yield <= -1:
        raise ValueError("Government bond yields must be above -100%.")

    d_to_e = debt_share / (1 - debt_share)
    levered_beta = unlevered_beta * (1 + (1 - tax_rate) * d_to_e)
    usd_equity = us_gov_yield + levered_beta * equity_risk_premium
    foreign_equity = foreign_gov_yield + levered_beta * equity_risk_premium
    usd_debt = us_gov_yield + usd_bbb_spread
    auto_foreign_spread = usd_bbb_spread * (1 + foreign_gov_yield) / (1 + us_gov_yield)
    foreign_spread = auto_foreign_spread if foreign_bbb_spread_override is None else foreign_bbb_spread_override
    foreign_debt = foreign_gov_yield + foreign_spread
    usd_wacc = (1 - debt_share) * usd_equity + debt_share * usd_debt * (1 - tax_rate)
    foreign_wacc = (1 - debt_share) * foreign_equity + debt_share * foreign_debt * (1 - tax_rate)

    return CapitalCosts(
        unlevered_beta, levered_beta, tax_rate, debt_share, equity_risk_premium,
        us_gov_yield, foreign_gov_yield, usd_bbb_spread, auto_foreign_spread,
        foreign_spread, usd_equity, foreign_equity, usd_debt, foreign_debt,
        usd_wacc, foreign_wacc,
    )


def verify_invariants(**inputs) -> dict[str, bool]:
    """Three explicit checks required by the assignment."""
    from dataclasses import replace
    from math import isclose
    base = compute_costs(**inputs)
    unchanged = {**inputs, "foreign_bbb_spread_override": None}
    equal_yields = compute_costs(**{**unchanged, "foreign_gov_yield": inputs["us_gov_yield"]})
    no_debt = compute_costs(**{**unchanged, "debt_share": 0.0})
    custom_spread = compute_costs(**{**inputs, "foreign_bbb_spread_override": 0.0275})
    close = lambda a, b: isclose(a, b, rel_tol=0, abs_tol=1e-11)
    return {
        "Equal yields imply identical currency results (auto spread)": (
            close(equal_yields.usd_equity_cost, equal_yields.foreign_equity_cost)
            and close(equal_yields.usd_debt_cost, equal_yields.foreign_debt_cost)
            and close(equal_yields.usd_wacc, equal_yields.foreign_wacc)
        ),
        "Zero debt makes WACC equal cost of equity": (
            close(no_debt.usd_wacc, no_debt.usd_equity_cost)
            and close(no_debt.foreign_wacc, no_debt.foreign_equity_cost)
        ),
        "Foreign spread override leaves USD costs unchanged": (
            close(base.usd_equity_cost, custom_spread.usd_equity_cost)
            and close(base.usd_debt_cost, custom_spread.usd_debt_cost)
            and close(base.usd_wacc, custom_spread.usd_wacc)
        ),
    }
