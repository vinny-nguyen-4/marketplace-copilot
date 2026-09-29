"""Deterministic pricing math. No AI here on purpose: numbers must be exact."""
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# Approximate referral fees (percent of sale price). Check each marketplace's current fee schedule.
MARKETPLACE_FEES = {"amazon": 0.15, "walmart": 0.15, "ebay": 0.136}


@dataclass
class CostInputs:
    unit_cost: float              # supplier price per unit (USD)
    freight_per_unit: float       # ocean/air freight + last-mile inbound, per unit
    duty_rate: float              # import duty as a fraction of unit cost (e.g. 0.25)
    fulfillment_fee: float        # pick/pack/ship per unit (e.g. FBA fee)
    marketplace: str = "amazon"
    target_margin: float = 0.30   # desired net margin as a fraction of price


def landed_cost(c: CostInputs) -> float:
    """Cost to get one unit into the warehouse, before marketplace fees."""
    return c.unit_cost + c.freight_per_unit + c.unit_cost * c.duty_rate


def fixed_cost(c: CostInputs) -> float:
    return landed_cost(c) + c.fulfillment_fee


def margin_at(price: float, c: CostInputs) -> dict:
    fee_pct = MARKETPLACE_FEES.get(c.marketplace, 0.15)
    referral = price * fee_pct
    total_cost = fixed_cost(c) + referral
    profit = price - total_cost
    return {
        "price": round(price, 2),
        "referral_fee": round(referral, 2),
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "margin": round(profit / price, 4) if price else 0.0,
    }


def price_for_margin(c: CostInputs) -> float:
    """Solve price where (price - fixed - fee%*price) / price = target_margin."""
    fee_pct = MARKETPLACE_FEES.get(c.marketplace, 0.15)
    denom = 1 - fee_pct - c.target_margin
    if denom <= 0:
        raise ValueError("Target margin plus marketplace fee is 100% or more; no price can hit it.")
    return fixed_cost(c) / denom


def market_stats(prices: pd.Series) -> dict:
    p = prices.dropna().astype(float)
    return {
        "count": int(p.count()),
        "min": round(p.min(), 2),
        "p25": round(p.quantile(0.25), 2),
        "median": round(p.median(), 2),
        "p75": round(p.quantile(0.75), 2),
        "max": round(p.max(), 2),
    }


def percentile_of(price: float, prices: pd.Series) -> float:
    """What share of competitors are priced below this price."""
    p = prices.dropna().astype(float)
    return round(float((p < price).mean()), 3) if len(p) else 0.0


def recommend_price(c: CostInputs, competitor_prices: pd.Series) -> dict:
    stats = market_stats(competitor_prices)
    floor_price = price_for_margin(c)

    # Aim for the middle of the market, but never below the price that protects our margin.
    recommended = max(floor_price, stats["median"])
    recommended = np.floor(recommended) + 0.99 if recommended % 1 < 0.99 else recommended  # charm pricing

    if floor_price > stats["p75"]:
        verdict = "Costs are high for this market: target margin requires a price above 75% of competitors."
    elif floor_price > stats["median"]:
        verdict = "Viable, but you'll be priced above the median. Lead with differentiated features."
    else:
        verdict = "Healthy: you can price at the market median and still beat your margin target."

    return {
        "landed_cost": round(landed_cost(c), 2),
        "break_even_price": round(price_for_margin(CostInputs(**{**asdict(c), "target_margin": 0.0})), 2),
        "min_price_for_target_margin": round(floor_price, 2),
        "recommended_price": round(float(recommended), 2),
        "recommended_percentile": percentile_of(recommended, competitor_prices),
        "at_recommended": margin_at(float(recommended), c),
        "market": stats,
        "verdict": verdict,
    }


def scenario_table(c: CostInputs, competitor_prices: pd.Series, steps: int = 7) -> pd.DataFrame:
    """Margin at several price points across the competitive range."""
    stats = market_stats(competitor_prices)
    points = np.linspace(stats["p25"], stats["max"], steps)
    rows = [margin_at(float(p), c) for p in points]
    df = pd.DataFrame(rows)
    df["pct_of_competitors_cheaper"] = [percentile_of(p, competitor_prices) for p in df["price"]]
    return df
