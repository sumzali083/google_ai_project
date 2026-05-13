# Devpost Submission Checklist

## Project

Smart Portfolio Agent is a Gemini-powered portfolio agent that turns natural language into portfolio actions. It stores holdings, watchlists, and portfolio memory in MongoDB Atlas, fetches market prices, calculates P&L and concentration risk, and displays a dark web dashboard.

## Hackathon Fit

- Google Cloud: Gemini on Vertex AI through Application Default Credentials.
- Agent Builder ecosystem: ADK entrypoint in `agent/mongodb_adk_agent.py`.
- Partner track: MongoDB Atlas plus MongoDB MCP Server.
- Web platform: Flask dashboard served on Cloud Run.
- Action beyond chat: add holdings, remove holdings, update watchlist, fetch prices, analyze risk.

## Before Submit

- Public GitHub repository.
- `LICENSE` visible at repository root.
- Hosted Cloud Run URL.
- Demo video under 3 minutes.
- Devpost track: MongoDB.

## Suggested Demo Script

1. Show the dashboard with current holdings and risk.
2. Ask: `Add 2 shares of MSFT at 400 in the Technology sector`.
3. Show MongoDB-backed dashboard update.
4. Ask: `What are my biggest risks?`.
5. Ask: `Add TSLA to my watchlist with note: monitor volatility`.
6. Mention Gemini on Vertex AI, MongoDB Atlas memory, and MongoDB MCP/ADK integration.
