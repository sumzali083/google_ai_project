"""Smart Portfolio Agent — Google ADK + MongoDB MCP + Gemini 2.5 Flash via Vertex AI."""

import asyncio
import os
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
try:
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
except ImportError:
    StdioConnectionParams = None
from google.genai import types

from tools import market_data, portfolio_analysis, mongodb_client as mongo

load_dotenv()

USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-39a25ac1-734b-42d5-996")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
MCP_COMMAND = "npx.cmd" if os.name == "nt" else "mongodb-mcp-server"
MCP_ARGS = ["-y", "mongodb-mcp-server"] if os.name == "nt" else []

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION

_SYSTEM = """You are a Smart Portfolio Agent — an expert AI financial assistant built on Google Cloud.

You have access to:
- Live stock prices and company fundamentals (get_stock_price, get_stock_info)
- Recent stock headlines (get_stock_news)
- Full portfolio analytics: P&L, allocation, risk (analyse_portfolio)
- S&P 500 benchmark comparison (compare_to_benchmark)
- Portfolio snapshot saving for performance tracking (save_portfolio_snapshot)
- Portfolio action tools for holdings and watchlist updates
- Portfolio rules management (get_portfolio_rules, set_portfolio_rule, delete_portfolio_rule)
- Pre-trade consequence preview (preview_trade)
- MongoDB MCP tools for database-backed memory and inspection

Rules:
- Always fetch live data with tools — never invent prices or values
- Be direct and quantitative: lead with numbers, then explanation
- Flag concentration risk when any stock or sector exceeds 20% of portfolio
- When users say "add X shares of TICKER at $Y", use add_holding
- When users ask "what if I buy X?" or "should I add X shares?", call preview_trade first
- When users say "set a rule", "cap X sector at Y%", or "no position over X%", call set_portfolio_rule
- After any trade, call get_portfolio_rules and warn the user if any rule is now breached
- When adding to watchlist, capture the current price with get_stock_price as the reference
- If the user confirms a previously discussed ticker, share count, or price, use the conversation context
- Do not give personalised financial advice or tell the user what they must buy
- For investment recommendations, provide educational watchlist ideas, risk tradeoffs, and ask the user to decide
- Format clearly: use bullet points and bold numbers for readability"""


# ── Native Python tools ────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """Get current price, day change %, and market cap for a stock ticker."""
    return market_data.get_price(ticker.upper())


def get_stock_info(ticker: str) -> dict:
    """Get company fundamentals: sector, P/E ratio, beta, 52-week high/low."""
    return market_data.get_info(ticker.upper())


def get_stock_news(ticker: str) -> dict:
    """Get recent news headlines for a stock ticker."""
    return market_data.get_news(ticker.upper())


def add_holding(ticker: str, shares: float, avg_cost: float, sector: str = "Unknown") -> dict:
    """Add or update a portfolio holding in MongoDB."""
    mongo.upsert_holding(USER_ID, ticker.upper(), shares, avg_cost, sector)
    return {
        "status": "ok",
        "ticker": ticker.upper(),
        "shares": shares,
        "avg_cost": avg_cost,
        "sector": sector,
    }


def remove_holding(ticker: str) -> dict:
    """Remove a portfolio holding from MongoDB."""
    mongo.delete_holding(USER_ID, ticker.upper())
    return {"status": "ok", "ticker": ticker.upper()}


def add_to_watchlist(ticker: str, note: str = "") -> dict:
    """Add a ticker to the user's MongoDB-backed watchlist. Always fetches current price as reference."""
    price = market_data.get_price(ticker.upper()).get("price", 0)
    mongo.add_to_watchlist(USER_ID, ticker.upper(), note, added_price=price)
    return {"status": "ok", "ticker": ticker.upper(), "note": note, "added_price": price}


def get_watchlist() -> dict:
    """Get the user's MongoDB-backed watchlist."""
    return {"watchlist": mongo.get_watchlist(USER_ID)}


def analyse_portfolio() -> dict:
    """Compute full portfolio analysis: allocation, P&L per position, concentration risks."""
    holdings = mongo.get_holdings(USER_ID)
    if not holdings:
        return {"error": "No holdings found. Add stocks first."}
    prices = market_data.get_prices([h["ticker"] for h in holdings])
    return {
        "allocation": portfolio_analysis.compute_allocation(holdings, prices),
        "pnl": portfolio_analysis.compute_pnl(holdings, prices),
        "risks": portfolio_analysis.concentration_risk(
            portfolio_analysis.compute_allocation(holdings, prices)
        ),
    }


def compare_to_benchmark() -> dict:
    """Compare total portfolio return % against the S&P 500 (SPY) today."""
    holdings = mongo.get_holdings(USER_ID)
    if not holdings:
        return {"error": "No holdings to compare."}
    prices = market_data.get_prices([h["ticker"] for h in holdings])
    total_cost = sum(h["shares"] * h["avg_cost"] for h in holdings)
    total_value = sum(h["shares"] * prices[h["ticker"]] for h in holdings)
    portfolio_return = round((total_value - total_cost) / total_cost * 100, 2) if total_cost else 0
    spy = market_data.get_price("SPY")
    return {
        "portfolio_total_return_pct": portfolio_return,
        "spy_day_change_pct": spy.get("change_pct", 0),
        "portfolio_value": round(total_value, 2),
        "outperforming_spy": portfolio_return > spy.get("change_pct", 0),
    }


def preview_trade(ticker: str, shares: float, price: float) -> dict:
    """Preview the portfolio impact of buying shares at a given price before executing.
    Returns new diversification score, position weight, sector changes, and any rule breaches."""
    holdings = mongo.get_holdings(USER_ID)
    prices = market_data.get_prices([h["ticker"] for h in holdings])
    current_alloc = portfolio_analysis.compute_allocation(holdings, prices) if holdings else {"total_value": 0, "by_sector": [], "by_ticker": {}}

    def hhi_score(sectors):
        if not sectors:
            return 0
        return round((1 - sum((s["weight_pct"] / 100) ** 2 for s in sectors)) * 100)

    current_score = hhi_score(current_alloc.get("by_sector", []))

    new_holdings = [dict(h) for h in holdings]
    existing = next((h for h in new_holdings if h["ticker"] == ticker.upper()), None)
    if existing:
        total = existing["shares"] + shares
        existing["avg_cost"] = (existing["shares"] * existing["avg_cost"] + shares * price) / total
        existing["shares"] = total
    else:
        info = market_data.get_info(ticker.upper())
        new_holdings.append({"ticker": ticker.upper(), "shares": shares, "avg_cost": price,
                              "sector": info.get("sector", "Unknown"), "user_id": USER_ID})

    new_prices = {**prices, ticker.upper(): price}
    new_alloc  = portfolio_analysis.compute_allocation(new_holdings, new_prices)
    new_score  = hhi_score(new_alloc.get("by_sector", []))
    new_risks  = portfolio_analysis.concentration_risk(new_alloc)

    position_value = shares * price
    weight = round(position_value / new_alloc["total_value"] * 100, 1) if new_alloc["total_value"] else 0

    rule_alerts = []
    for rule in mongo.get_rules(USER_ID):
        rt, params = rule.get("rule_type"), rule.get("params", {})
        if rt == "sector_max":
            sector_weights = {s["sector"]: s["weight_pct"] for s in new_alloc.get("by_sector", [])}
            current = sector_weights.get(params.get("sector", ""), 0)
            if current > params.get("max_pct", 100):
                rule_alerts.append(f"⚠ Rule breached: {rule['label']} ({current:.1f}% > {params['max_pct']}%)")
        elif rt == "position_max":
            ticker_weights = {t: d["weight_pct"] for t, d in new_alloc.get("by_ticker", {}).items()}
            worst = max(ticker_weights.values(), default=0)
            if worst > params.get("max_pct", 100):
                rule_alerts.append(f"⚠ Rule breached: {rule['label']} ({worst:.1f}% > {params['max_pct']}%)")

    return {
        "cost": round(position_value, 2),
        "position_weight_pct": weight,
        "current_diversification_score": current_score,
        "new_diversification_score": new_score,
        "score_delta": new_score - current_score,
        "new_total_value": round(new_alloc["total_value"], 2),
        "new_sector_allocation": new_alloc.get("by_sector", []),
        "new_concentration_risks": new_risks,
        "rule_breaches": rule_alerts,
    }


def get_portfolio_rules() -> dict:
    """Get all portfolio rules the user has set (sector limits, position limits, etc.)."""
    return {"rules": mongo.get_rules(USER_ID)}


def set_portfolio_rule(rule_type: str, label: str, params: dict) -> dict:
    """Store a portfolio rule in MongoDB.
    rule_type: 'sector_max' (params: {sector, max_pct}), 'position_max' (params: {max_pct}), 'min_sectors' (params: {min_count})
    Example: set_portfolio_rule('sector_max', 'Tech cap 40%', {'sector': 'Technology', 'max_pct': 40})"""
    mongo.upsert_rule(USER_ID, rule_type, label, params)
    return {"status": "ok", "label": label, "rule_type": rule_type, "params": params}


def delete_portfolio_rule(label: str) -> dict:
    """Delete a portfolio rule by its label."""
    mongo.delete_rule(USER_ID, label)
    return {"status": "ok", "deleted": label}


def save_portfolio_snapshot() -> dict:
    """Save today's portfolio value to MongoDB for historical performance tracking."""
    holdings = mongo.get_holdings(USER_ID)
    if not holdings:
        return {"error": "No holdings to snapshot."}
    prices = market_data.get_prices([h["ticker"] for h in holdings])
    total_value = round(sum(h["shares"] * prices[h["ticker"]] for h in holdings), 2)
    total_cost = round(sum(h["shares"] * h["avg_cost"] for h in holdings), 2)
    mongo.save_snapshot(USER_ID, total_value, total_cost)
    return {"status": "ok", "value_saved": total_value, "timestamp": datetime.now(timezone.utc).isoformat()}


# ── ADK setup — initialised once at startup ────────────────────────────────────

_session_service = InMemorySessionService()
_runner: Runner | None = None
_session_id: str | None = None
_loop = asyncio.new_event_loop()
_bg_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_bg_thread.start()


async def _init():
    global _runner, _session_id

    server_params = StdioServerParameters(
        command=MCP_COMMAND,
        args=MCP_ARGS,
        env={**os.environ, "MDB_MCP_CONNECTION_STRING": MONGODB_URI},
    )
    connection_params = (
        StdioConnectionParams(server_params=server_params, timeout=30)
        if StdioConnectionParams
        else server_params
    )

    mongo_mcp = MCPToolset(
        connection_params=connection_params,
        tool_filter=["find", "findOne", "insertOne", "updateOne", "deleteOne",
                     "listCollections", "listDatabases", "createIndex"],
    )

    agent = LlmAgent(
        model="gemini-2.5-flash",
        name="portfolio_agent",
        description="AI-powered stock portfolio tracker and analyser",
        instruction=_SYSTEM,
        tools=[
            get_stock_price,
            get_stock_info,
            get_stock_news,
            add_holding,
            remove_holding,
            add_to_watchlist,
            get_watchlist,
            analyse_portfolio,
            compare_to_benchmark,
            save_portfolio_snapshot,
            preview_trade,
            get_portfolio_rules,
            set_portfolio_rule,
            delete_portfolio_rule,
            mongo_mcp,
        ],
    )

    _runner = Runner(agent=agent, app_name="portfolio_app", session_service=_session_service)
    session = await _session_service.create_session(app_name="portfolio_app", user_id=USER_ID)
    _session_id = session.id


asyncio.run_coroutine_threadsafe(_init(), _loop).result(timeout=90)


# ── Public interface ───────────────────────────────────────────────────────────

async def _run_async(user_message: str) -> str:
    content = types.Content(role="user", parts=[types.Part(text=user_message)])
    final_text = "I couldn't generate a response. Please try again."
    async for event in _runner.run_async(
        user_id=USER_ID, session_id=_session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            texts = [p.text for p in event.content.parts if hasattr(p, "text") and p.text]
            if texts:
                final_text = "\n".join(texts)
    return final_text


def run(user_message: str) -> str:
    future = asyncio.run_coroutine_threadsafe(_run_async(user_message), _loop)
    return future.result(timeout=120)
