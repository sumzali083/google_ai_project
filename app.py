"""Flask API server — bridges the frontend and the Gemini agent."""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

load_dotenv()

from agent.agent import run
from tools import mongodb_client, market_data, portfolio_analysis

app = Flask(__name__, static_folder="frontend")
CORS(app)

USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")


# ── Chat endpoint ──────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True)
    message = body.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    try:
        reply = run(message)
        return jsonify({"reply": reply})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": f"Agent error: {exc}"}), 500


# ── Portfolio data endpoints ───────────────────────────────────────────────────

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    holdings = mongodb_client.get_holdings(USER_ID)
    if not holdings:
        return jsonify({"holdings": [], "summary": {}})

    tickers = [h["ticker"] for h in holdings]
    prices = {t: market_data.get_price(t).get("price", 0) for t in tickers}
    allocation = portfolio_analysis.compute_allocation(holdings, prices)
    pnl = portfolio_analysis.compute_pnl(holdings, prices)
    risks = portfolio_analysis.concentration_risk(allocation)

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
    })


@app.route("/api/history", methods=["GET"])
def get_history():
    snapshots = mongodb_client.get_snapshots(USER_ID, limit=30)
    snapshots.reverse()
    return jsonify(snapshots)


@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    items = mongodb_client.get_watchlist(USER_ID)
    enriched = []
    for item in items:
        price_data = market_data.get_price(item["ticker"])
        enriched.append({**item, **price_data})
    return jsonify(enriched)


# ── Serve frontend ─────────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
