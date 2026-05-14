# Smart Portfolio Agent

Smart Portfolio Agent is an AI portfolio co-pilot built for the Google Cloud Rapid Agent Hackathon MongoDB track. It lets users manage a stock portfolio through natural language while Gemini reasons over live market data, MongoDB stores portfolio memory, and a web dashboard shows holdings, risk, watchlists, research ideas, and performance.

This is not a trading or financial-advice app. It is a portfolio analysis and research assistant that helps users understand exposure, concentration risk, watchlist candidates, and the impact of possible trades.

## Unique Selling Point

Most portfolio apps are static dashboards. Smart Portfolio Agent is an action-taking AI workspace:

- Users can say things like `Add 2 shares of MSFT at 400 in the Technology sector`.
- The agent updates MongoDB-backed holdings and watchlists.
- The dashboard recalculates live P&L, sector exposure, diversification score, and risk flags.
- Gemini can generate educational research ideas based on portfolio gaps, not hype or direct buy/sell advice.

## Hackathon Compliance

| Requirement | Implementation |
| --- | --- |
| Google Cloud AI | Gemini 2.5 on Vertex AI using Application Default Credentials |
| Agent Builder ecosystem | Google ADK-based agent in `agent/agent.py` and ADK entrypoint in `adk_portfolio_agent/agent.py` |
| Partner MCP integration | MongoDB MCP Server launched from the ADK toolset |
| Partner track | MongoDB Atlas stores holdings, watchlists, snapshots, and rules |
| Web platform | Flask web app served by Gunicorn |
| Hosted project | Cloud Run-ready Dockerfile |
| Open source | MIT license in `LICENSE` |

## Features

- Natural-language portfolio actions:
  - Add holdings
  - Remove holdings
  - Add tickers to the watchlist
  - Save portfolio snapshots
  - Ask for risks, prices, benchmark comparison, and research ideas
- Overview dashboard:
  - Total value
  - Cost basis
  - Unrealised P&L
  - Return %
  - Diversification score
  - Agent activity status
  - Holdings table
  - Sector allocation chart
  - Performance history chart
  - Concentration risk flags
- Watchlist tab:
  - Live prices
  - Notes
  - Since-added tracking
  - Ask-AI research shortcut
- Insights tab:
  - Most invested stock
  - Best performer
  - Position needing attention
  - Top sector
  - Gemini portfolio analysis
  - AI-generated research ideas
  - Pre-trade preview
  - Portfolio rules
- Safety:
  - Research ideas are framed as educational watchlist candidates.
  - The app avoids direct personalised buy/sell instructions.

## Architecture

```text
Browser dashboard
  -> Flask API
  -> Google ADK agent
  -> Gemini 2.5 on Vertex AI
  -> Python tools + MongoDB MCP Server
  -> MongoDB Atlas + live market data
```

MongoDB is used as the agent memory layer:

```text
MongoDB Atlas
  -> holdings
  -> watchlist
  -> portfolio snapshots
  -> user-defined portfolio rules
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Agent reasoning | Gemini 2.5 via Vertex AI |
| Agent framework | Google ADK |
| Partner integration | MongoDB MCP Server |
| Database | MongoDB Atlas |
| Market data | yfinance with HTTP fallbacks |
| Backend | Flask + Gunicorn |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Hosting | Google Cloud Run |

## Example Prompts

```text
Add 2 shares of MSFT at 400 in the Technology sector
Remove AAPL from my portfolio
Add TSLA to my watchlist with note: monitor volatility
What are my biggest risks?
Compare my portfolio to the S&P 500
Generate research ideas for diversification
Save a portfolio snapshot
Cap Technology at 40%
```

## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js and npm for MongoDB MCP Server
- Google Cloud project with Vertex AI enabled
- Application Default Credentials configured locally
- MongoDB Atlas connection string

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_CLOUD_LOCATION=us-central1
MONGODB_URI=mongodb+srv://user:password@cluster.example.mongodb.net/portfolio_agent?retryWrites=true&w=majority
DEFAULT_USER_ID=demo_user
GEMINI_MODEL=gemini-2.5-flash
```

Authenticate with Google Cloud:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 4. Run Locally

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8080
```

### 5. Optional Demo Data

If you want a richer dashboard before recording the demo:

```bash
python seed_demo.py
```

## MongoDB MCP

The live web app uses Google ADK and launches MongoDB MCP through `agent/agent.py`:

```python
MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "mongodb-mcp-server"],
        env={...}
    )
)
```

On Windows, the app uses `npx.cmd`; on Linux/Cloud Run it uses `npx`.

See `docs/MONGODB_MCP.md` for more notes.

## Cloud Run Deploy

Store the MongoDB URI in Secret Manager:

```bash
gcloud secrets create mongodb-uri --data-file=-
```

Deploy:

```bash
gcloud run deploy smart-portfolio-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,GEMINI_MODEL=gemini-2.5-flash,DEFAULT_USER_ID=demo_user \
  --set-secrets MONGODB_URI=mongodb-uri:latest
```

The Cloud Run service account needs permission to call Vertex AI and access Secret Manager.

## Project Structure

```text
app.py                       Flask API server
agent/agent.py               Main Google ADK + Gemini + MongoDB MCP agent
adk_portfolio_agent/agent.py ADK runner entrypoint
tools/mongodb_client.py      MongoDB persistence helpers
tools/market_data.py         Live market data wrappers
tools/portfolio_analysis.py  P&L, allocation, and concentration risk
frontend/index.html          Dashboard UI
mcp/mongodb-mcp.json         MongoDB MCP configuration example
docs/MONGODB_MCP.md          MCP setup notes
docs/DEVPOST_SUBMISSION.md   Devpost checklist and demo script
Dockerfile                   Cloud Run container
LICENSE                      MIT license
```

## Demo Story

1. Show the overview dashboard with holdings and live risk flags.
2. Ask Gemini to add a new holding.
3. Show the dashboard updating from MongoDB.
4. Ask for biggest risks and benchmark comparison.
5. Open Watchlist and add a ticker with a note.
6. Open Insights and generate research ideas.
7. Mention Vertex AI, Google ADK, MongoDB Atlas, MongoDB MCP, and Cloud Run.

## Disclaimer

Smart Portfolio Agent is for educational and hackathon demonstration purposes only. It does not provide personalised financial advice.

## License

MIT
