"""Smart Portfolio Agent — powered by Gemini via Vertex AI (google-genai SDK)."""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools import market_data, portfolio_analysis, mongodb_client

load_dotenv()

USER_ID = os.environ.get("DEFAULT_USER_ID", "demo_user")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

if not PROJECT_ID:
    raise RuntimeError("Set GOOGLE_CLOUD_PROJECT in your .env file.")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

_TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(name="get_portfolio", description="Get the user's current holdings from MongoDB.", parameters=types.Schema(type=types.Type.OBJECT, properties={})),
    types.FunctionDeclaration(name="get_price", description="Get current stock price and day change.", parameters=types.Schema(type=types.Type.OBJECT, properties={"ticker": types.Schema(type=types.Type.STRING)}, required=["ticker"])),
    types.FunctionDeclaration(name="get_stock_info", description="Get company details: sector, P/E, beta, 52-week range.", parameters=types.Schema(type=types.Type.OBJECT, properties={"ticker": types.Schema(type=types.Type.STRING)}, required=["ticker"])),
    types.FunctionDeclaration(name="analyse_portfolio", description="Compute portfolio allocation, P&L, and risk.", parameters=types.Schema(type=types.Type.OBJECT, properties={})),
    types.FunctionDeclaration(name="add_holding", description="Add or update a holding in the portfolio.", parameters=types.Schema(type=types.Type.OBJECT, properties={"ticker": types.Schema(type=types.Type.STRING), "shares": types.Schema(type=types.Type.NUMBER), "avg_cost": types.Schema(type=types.Type.NUMBER), "sector": types.Schema(type=types.Type.STRING)}, required=["ticker", "shares", "avg_cost"])),
    types.FunctionDeclaration(name="remove_holding", description="Remove a stock from the portfolio.", parameters=types.Schema(type=types.Type.OBJECT, properties={"ticker": types.Schema(type=types.Type.STRING)}, required=["ticker"])),
    types.FunctionDeclaration(name="get_watchlist", description="Get the user's watchlist.", parameters=types.Schema(type=types.Type.OBJECT, properties={})),
    types.FunctionDeclaration(name="add_to_watchlist", description="Add a ticker to the watchlist.", parameters=types.Schema(type=types.Type.OBJECT, properties={"ticker": types.Schema(type=types.Type.STRING), "note": types.Schema(type=types.Type.STRING)}, required=["ticker"])),
])

_SYSTEM = """You are a Smart Portfolio Agent — a knowledgeable, concise financial assistant.
You help users track their stock portfolio, analyse risk, monitor P&L, and make data-driven decisions.
Always use the available tools to fetch live data before giving advice.
Be direct, use numbers, and flag risks clearly. Never make up prices."""


def _dispatch(name: str, args: dict) -> str:
    if name == "get_portfolio":
        return json.dumps(mongodb_client.get_holdings(USER_ID))
    if name == "get_price":
        return json.dumps(market_data.get_price(args["ticker"]))
    if name == "get_stock_info":
        return json.dumps(market_data.get_info(args["ticker"]))
    if name == "analyse_portfolio":
        holdings = mongodb_client.get_holdings(USER_ID)
        if not holdings:
            return json.dumps({"error": "No holdings found."})
        prices = {h["ticker"]: market_data.get_price(h["ticker"]).get("price", 0) for h in holdings}
        allocation = portfolio_analysis.compute_allocation(holdings, prices)
        pnl = portfolio_analysis.compute_pnl(holdings, prices)
        risks = portfolio_analysis.concentration_risk(allocation)
        return json.dumps({"allocation": allocation, "pnl": pnl, "risks": risks})
    if name == "add_holding":
        mongodb_client.upsert_holding(USER_ID, args["ticker"], args["shares"], args["avg_cost"], args.get("sector", "Unknown"))
        return json.dumps({"status": "ok", "ticker": args["ticker"]})
    if name == "remove_holding":
        mongodb_client.delete_holding(USER_ID, args["ticker"])
        return json.dumps({"status": "ok"})
    if name == "get_watchlist":
        return json.dumps(mongodb_client.get_watchlist(USER_ID))
    if name == "add_to_watchlist":
        mongodb_client.add_to_watchlist(USER_ID, args["ticker"], args.get("note", ""))
        return json.dumps({"status": "ok"})
    return json.dumps({"error": f"Unknown tool: {name}"})


def run(user_message: str) -> str:
    config = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        tools=[_TOOLS],
    )
    contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]

    while True:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )
        candidate = response.candidates[0]
        contents.append(candidate.content)

        fn_calls = [p.function_call for p in candidate.content.parts if p.function_call]
        if not fn_calls:
            break

        tool_parts = []
        for fc in fn_calls:
            try:
                result = _dispatch(fc.name, dict(fc.args))
            except Exception as exc:
                result = json.dumps({"error": f"{fc.name} failed: {exc}"})
            tool_parts.append(types.Part(function_response=types.FunctionResponse(name=fc.name, response={"result": result})))
        contents.append(types.Content(role="user", parts=tool_parts))

    return response.text
