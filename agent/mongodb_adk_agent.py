"""ADK entrypoint that connects Gemini to MongoDB through MongoDB MCP.

This file is provided for the Google Cloud Rapid Agent Hackathon compliance path:
Google ADK / Agent Builder ecosystem + Gemini + MongoDB MCP Server.
The Flask dashboard uses agent/agent.py for the web demo, while this root_agent
can be run with ADK tooling or deployed to Agent Engine.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from mcp import StdioServerParameters

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
MONGODB_URI = os.environ.get("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("Set MONGODB_URI before running the ADK MongoDB MCP agent.")

root_agent = Agent(
    model=MODEL,
    name="smart_portfolio_mongodb_mcp_agent",
    instruction=(
        "You are Smart Portfolio Agent. Use MongoDB MCP tools to inspect and "
        "manage the portfolio_agent database. Help users understand holdings, "
        "watchlists, transactions, concentration risk, and portfolio memory. "
        "Avoid destructive database operations."
    ),
    tools=[
        MCPToolset(
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "mongodb-mcp-server"],
                env={
                    "MDB_MCP_CONNECTION_STRING": MONGODB_URI,
                    "MDB_MCP_DISABLED_TOOLS": "drop-database,drop-collection,delete-many",
                },
            )
        )
    ],
)
