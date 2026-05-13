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
from google.genai import types

from tools import market_data, portfolio_analysis, mongodb_client as mongo

load_dotenv()

USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-39a25ac1-734b-42d5-996")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION

_SYSTEM = """You are a Smart Portfolio Agent — an expert AI financial assistant built on Google Cloud.

You have access to:
- Live stock prices and company fundamentals (get_stock_price, get_stock_info)
- Full portfolio analytics: P&L, allocation, risk (analyse_portfolio)
- S&P 500 benchmark comparison (compare_to_benchmark)
- Portfolio snapshot saving for performance tracking (save_portfolio_snapshot)
- MongoDB tools for managing holdings and watchlist directly

Rules:
- Always fetch live data with tools — never invent prices or values
- Be direct and quantitative: lead with numbers, then explanation
- Flag concentration risk when any stock or sector exceeds 20% of portfolio
- When users say "add X shares of TICKER at $Y", use the MongoDB add_holding tool
- Format clearly: use bullet points and bold numbers for readability"""


# ── Native Python tools ────────────────────────────────────────────────────────

def get_stock_price(ticker: str) -> dict:
    """Get current price, day change %, and market cap for a stock ticker."""
    return market_data.get_price(ticker.upper())


def get_stock_info(ticker: str) -> dict:
    """Get company fundamentals: sector, P/E ratio, beta, 52-week high/low."""
    return market_data.get_info(ticker.upper())


def analyse_portfolio() -> dict:
    """Compute full portfolio analysis: allocation, P&L per position, concentration risks."""
    holdings = mongo.get_holdings(USER_ID)
    if not holdings:
        return {"error": "No holdings found. Add stocks first."}
    prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
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
    prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
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


def save_portfolio_snapshot() -> dict:
    """Save today's portfolio value to MongoDB for historical performance tracking."""
    holdings = mongo.get_holdings(USER_ID)
    if not holdings:
        return {"error": "No holdings to snapshot."}
    prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
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

    mongo_mcp = MCPToolset(
        connection_params=StdioServerParameters(
            command="mongodb-mcp-server",
            args=["--connectionString", MONGODB_URI],
        ),
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
            analyse_portfolio,
            compare_to_benchmark,
            save_portfolio_snapshot,
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
