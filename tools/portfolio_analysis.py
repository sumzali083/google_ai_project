"""Portfolio-level analytics: allocation, risk, performance."""

from collections import defaultdict


def compute_allocation(holdings: list[dict], prices: dict[str, float]) -> list[dict]:
    """
    holdings: [{"ticker": "AAPL", "shares": 10, "sector": "Technology"}, ...]
    prices:   {"AAPL": 180.0, ...}
    Returns allocation by ticker and by sector (% of total value).
    """
    values = {h["ticker"]: h["shares"] * prices.get(h["ticker"], 0) for h in holdings}
    total_value = sum(values.values())
    total = total_value or 1

    sector_totals: dict[str, float] = defaultdict(float)
    by_ticker = []
    for h in holdings:
        val = values[h["ticker"]]
        pct = round(val / total * 100, 2)
        sector_totals[h.get("sector", "Unknown")] += val
        by_ticker.append({"ticker": h["ticker"], "value": round(val, 2), "weight_pct": pct})

    by_sector = [
        {"sector": s, "value": round(v, 2), "weight_pct": round(v / total * 100, 2)}
        for s, v in sector_totals.items()
    ]

    return {"total_value": round(total_value, 2), "by_ticker": by_ticker, "by_sector": by_sector}


def compute_pnl(holdings: list[dict], prices: dict[str, float]) -> list[dict]:
    """
    Returns unrealised P&L per position and overall.
    holdings must include avg_cost field.
    """
    results = []
    total_cost = 0.0
    total_value = 0.0

    for h in holdings:
        price = prices.get(h["ticker"], 0)
        cost = h["shares"] * h["avg_cost"]
        value = h["shares"] * price
        gain = value - cost
        gain_pct = round(gain / cost * 100, 2) if cost else 0

        results.append({
            "ticker": h["ticker"],
            "shares": h["shares"],
            "avg_cost": h["avg_cost"],
            "current_price": price,
            "cost_basis": round(cost, 2),
            "market_value": round(value, 2),
            "unrealised_gain": round(gain, 2),
            "unrealised_gain_pct": gain_pct,
        })
        total_cost += cost
        total_value += value

    overall_gain = total_value - total_cost
    return {
        "positions": results,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_unrealised_gain": round(overall_gain, 2),
        "total_unrealised_gain_pct": round(overall_gain / total_cost * 100, 2) if total_cost else 0,
    }


def concentration_risk(allocation: dict, threshold_pct: float = 20.0) -> list[dict]:
    """Flag any position or sector that exceeds threshold_pct of total portfolio."""
    warnings = []
    for item in allocation["by_ticker"]:
        if item["weight_pct"] >= threshold_pct:
            warnings.append({
                "type": "ticker",
                "name": item["ticker"],
                "weight_pct": item["weight_pct"],
                "message": f"{item['ticker']} is {item['weight_pct']}% of portfolio — above {threshold_pct}% threshold",
            })
    for item in allocation["by_sector"]:
        if item["weight_pct"] >= threshold_pct:
            warnings.append({
                "type": "sector",
                "name": item["sector"],
                "weight_pct": item["weight_pct"],
                "message": f"{item['sector']} sector is {item['weight_pct']}% of portfolio — above {threshold_pct}% threshold",
            })
    return warnings
