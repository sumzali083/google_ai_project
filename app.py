"""Flask API server — bridges the frontend and the Gemini agent."""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

from tools import mongodb_client, market_data, portfolio_analysis

app = Flask(__name__, static_folder="frontend")
CORS(app)

USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    message = body.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    try:
        from agent.agent import run

        reply = run(message)
        return jsonify({"reply": reply})
    except RuntimeError as exc:
        app.logger.exception("Chat endpoint failed with runtime error")
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        app.logger.exception("Chat endpoint failed")
        return jsonify({"error": f"Agent error: {exc}"}), 500


# ── Portfolio ─────────────────────────────────────────────────────────────────

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    holdings = mongodb_client.get_holdings(USER_ID)
    if not holdings:
        return jsonify({"holdings": [], "summary": {}, "allocation_by_sector": [], "risks": [], "rule_alerts": []})

    prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
    allocation = portfolio_analysis.compute_allocation(holdings, prices)
    pnl = portfolio_analysis.compute_pnl(holdings, prices)
    risks = portfolio_analysis.concentration_risk(allocation)
    rule_alerts = _evaluate_rules(allocation)

    return jsonify({
        "holdings": pnl["positions"],
        "summary": {
            "total_value": allocation["total_value"],
            "total_cost": pnl["total_cost"],
            "total_unrealised_gain": pnl["total_unrealised_gain"],
            "total_unrealised_gain_pct": pnl["total_unrealised_gain_pct"],
        },
        "allocation_by_sector": allocation["by_sector"],
        "risks": risks,
        "rule_alerts": rule_alerts,
    })


@app.route("/api/history", methods=["GET"])
def get_history():
    snapshots = mongodb_client.get_snapshots(USER_ID, limit=30)
    snapshots.reverse()
    return jsonify(snapshots)


# ── Watchlist ─────────────────────────────────────────────────────────────────

@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    items = mongodb_client.get_watchlist(USER_ID)
    enriched = []
    for item in items:
        price_data = market_data.get_price(item["ticker"])
        current_price = price_data.get("price", 0)
        added_price = item.get("added_price", 0)
        since_add_pct = None
        if added_price and added_price > 0 and current_price > 0:
            since_add_pct = round((current_price - added_price) / added_price * 100, 2)
        enriched.append({**item, **price_data, "since_add_pct": since_add_pct})
    return jsonify(enriched)


# ── Pre-trade preview ─────────────────────────────────────────────────────────

@app.route("/api/preview-trade", methods=["POST"])
def preview_trade():
    body = request.get_json(force=True)
    ticker = body.get("ticker", "").upper().strip()
    try:
        shares = float(body.get("shares", 0))
        price  = float(body.get("price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "shares and price must be numbers"}), 400

    if not ticker or shares <= 0 or price <= 0:
        return jsonify({"error": "Provide a valid ticker, shares > 0, and price > 0"}), 400

    holdings = mongodb_client.get_holdings(USER_ID)
    prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}

    current_alloc = portfolio_analysis.compute_allocation(holdings, prices) if holdings else {"total_value": 0, "by_sector": [], "by_ticker": []}
    current_score = _hhi_score(current_alloc.get("by_sector", []))

    # Build the hypothetical portfolio
    new_holdings = [dict(h) for h in holdings]
    existing = next((h for h in new_holdings if h["ticker"] == ticker), None)
    if existing:
        total_shares  = existing["shares"] + shares
        existing["avg_cost"] = (existing["shares"] * existing["avg_cost"] + shares * price) / total_shares
        existing["shares"] = total_shares
    else:
        info   = market_data.get_info(ticker)
        sector = info.get("sector", "Unknown")
        new_holdings.append({"ticker": ticker, "shares": shares, "avg_cost": price, "sector": sector, "user_id": USER_ID})

    new_prices = {**prices, ticker: price}
    new_alloc  = portfolio_analysis.compute_allocation(new_holdings, new_prices)
    new_risks  = portfolio_analysis.concentration_risk(new_alloc)
    new_score  = _hhi_score(new_alloc.get("by_sector", []))

    position_value  = round(shares * price, 2)
    position_weight = round(position_value / new_alloc["total_value"] * 100, 1) if new_alloc["total_value"] else 0

    rule_checks = _evaluate_rules(new_alloc)

    return jsonify({
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "cost": position_value,
        "position_weight_pct": position_weight,
        "current_score": current_score,
        "new_score": new_score,
        "score_delta": new_score - current_score,
        "new_total_value": round(new_alloc["total_value"], 2),
        "new_sector_allocation": new_alloc.get("by_sector", []),
        "new_risks": new_risks,
        "rule_checks": rule_checks,
    })


# ── Portfolio Rules ───────────────────────────────────────────────────────────

@app.route("/api/rules", methods=["GET"])
def get_rules():
    holdings = mongodb_client.get_holdings(USER_ID)
    if holdings:
        prices     = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
        allocation = portfolio_analysis.compute_allocation(holdings, prices)
    else:
        allocation = {"by_sector": [], "by_ticker": []}
    alerts = _evaluate_rules(allocation, detailed=True)
    return jsonify(alerts)


@app.route("/api/rules", methods=["POST"])
def save_rule():
    body = request.get_json(force=True)
    rule_type = body.get("rule_type", "").strip()
    label     = body.get("label", "").strip()
    params    = body.get("params", {})
    if not rule_type or not label:
        return jsonify({"error": "rule_type and label are required"}), 400
    mongodb_client.upsert_rule(USER_ID, rule_type, label, params)
    return jsonify({"status": "ok"})


@app.route("/api/rules/<path:label>", methods=["DELETE"])
def delete_rule(label):
    mongodb_client.delete_rule(USER_ID, label)
    return jsonify({"status": "ok"})


# ── Serve frontend ─────────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hhi_score(sectors: list) -> int:
    if not sectors:
        return 0
    hhi = sum((s["weight_pct"] / 100) ** 2 for s in sectors)
    return round((1 - hhi) * 100)


def _evaluate_rules(allocation: dict, detailed: bool = False) -> list:
    rules   = mongodb_client.get_rules(USER_ID)
    sectors = {s["sector"]: s["weight_pct"] for s in allocation.get("by_sector", [])}
    tickers = {d["ticker"]: d["weight_pct"] for d in allocation.get("by_ticker", [])}
    results = []

    for rule in rules:
        rt     = rule.get("rule_type", "")
        params = rule.get("params", {})
        label  = rule.get("label", "")
        status = "ok"
        detail = ""

        if rt == "sector_max":
            sector  = params.get("sector", "")
            max_pct = float(params.get("max_pct", 100))
            current = sectors.get(sector, 0)
            if current > max_pct:
                status = "breached"
                detail = f"{sector} at {current:.1f}% — limit {max_pct:.0f}%"
            elif current > max_pct * 0.85:
                status = "warning"
                detail = f"{sector} at {current:.1f}% — approaching {max_pct:.0f}% limit"
            else:
                detail = f"{sector} at {current:.1f}% — OK"

        elif rt == "position_max":
            max_pct = float(params.get("max_pct", 100))
            worst = max(tickers.items(), key=lambda x: x[1], default=(None, 0))
            if worst[1] > max_pct:
                status = "breached"
                detail = f"{worst[0]} at {worst[1]:.1f}% — limit {max_pct:.0f}%"
            elif worst[1] > max_pct * 0.85:
                status = "warning"
                detail = f"{worst[0]} at {worst[1]:.1f}% — approaching {max_pct:.0f}% limit"
            else:
                detail = f"Largest position {worst[1]:.1f}% — OK"

        elif rt == "min_sectors":
            min_count = int(params.get("min_count", 1))
            actual    = len(sectors)
            if actual < min_count:
                status = "breached"
                detail = f"{actual} sector{'s' if actual != 1 else ''} — need at least {min_count}"
            else:
                detail = f"{actual} sectors — OK"

        entry = {**rule, "status": status, "detail": detail}
        if status in ("breached", "warning") or detailed:
            results.append(entry)

    return results


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
