# Smart Portfolio Agent

Smart Portfolio Agent is a Gemini-powered web agent for tracking a stock portfolio. Users can chat with the agent to add holdings, remove holdings, manage a watchlist, fetch live prices, calculate unrealised profit/loss, and identify concentration risk.

Built for the Google Cloud Rapid Agent Hackathon MongoDB track.

## Why It Is an Agent

The app moves beyond Q&A. Gemini interprets natural-language goals, chooses tools, updates MongoDB-backed portfolio memory, fetches market data, and returns an explanation grounded in current holdings.

Example prompts:

- `Add 2 shares of MSFT at 400 in the Technology sector`
- `Remove AAPL from my portfolio`
- `Add TSLA to my watchlist with note: monitor volatility`
- `What are my biggest risks?`
- `Analyse my full portfolio`

## Hackathon Compliance

| Requirement | Implementation |
| --- | --- |
| Google Cloud AI | Gemini on Vertex AI using Application Default Credentials |
| Agent Builder ecosystem | ADK-compatible entrypoint in `agent/mongodb_adk_agent.py` |
| Partner MCP integration | MongoDB MCP Server configuration and ADK `McpToolset` integration |
| Partner track | MongoDB Atlas stores portfolio memory |
| Web platform | Flask dashboard and API |
| Hosted project | Designed for Google Cloud Run |
| Open source | MIT license in `LICENSE` |

## Architecture

```text
Browser dashboard
  -> Flask API
  -> Gemini on Vertex AI
  -> Portfolio tools
  -> MongoDB Atlas + live market data
```

ADK/MCP compliance path:

```text
Google ADK / Agent Builder
  -> Gemini
  -> MongoDB MCP Server
  -> MongoDB Atlas portfolio_agent database
```

## Features

- Dark dashboard with holdings, P&L, sector allocation, and concentration risks.
- Gemini chat agent with tool calling.
- MongoDB Atlas persistence for holdings, transactions, snapshots, and watchlist.
- MongoDB MCP Server integration files for the partner track.
- Live price lookup through free market-data providers.
- Cloud Run-ready Dockerfile.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Agent reasoning | Gemini on Vertex AI |
| Agent framework | Google ADK / Agent Builder-compatible entrypoint |
| Partner integration | MongoDB MCP Server |
| Database | MongoDB Atlas |
| Market data | yfinance with HTTP fallbacks |
| Backend | Flask + Gunicorn |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Hosting | Google Cloud Run |

## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 20+ for `npx` and MongoDB MCP Server
- Google Cloud project with Vertex AI enabled
- Application Default Credentials configured
- MongoDB Atlas cluster

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and set:

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_CLOUD_LOCATION=us-central1
MONGODB_URI=mongodb+srv://user:password@cluster.example.mongodb.net/portfolio_agent?retryWrites=true&w=majority
DEFAULT_USER_ID=demo_user
GEMINI_MODEL=gemini-2.5-flash
```

Authenticate locally:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 4. Run The Web App

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8080
```

### 5. Run The ADK / MongoDB MCP Agent

The ADK entrypoint is `agent/mongodb_adk_agent.py`. It connects Gemini to MongoDB through the official MongoDB MCP Server.

```bash
adk run adk_portfolio_agent
```

See `docs/MONGODB_MCP.md` for MCP setup details.

## Cloud Run Deploy

Store secrets outside source control:

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

The Cloud Run service account must have permission to call Vertex AI and access Secret Manager.

## Project Structure

```text
app.py                     Flask API server
agent/agent.py             Web demo Gemini tool-calling loop
agent/mongodb_adk_agent.py ADK + MongoDB MCP entrypoint
tools/mongodb_client.py    Portfolio persistence
tools/market_data.py       Market data wrappers
tools/portfolio_analysis.py P&L and risk calculations
frontend/index.html        Dashboard UI
mcp/mongodb-mcp.json       MongoDB MCP configuration example
docs/MONGODB_MCP.md        MCP setup notes
docs/DEVPOST_SUBMISSION.md Devpost checklist and demo script
Dockerfile                 Cloud Run container
LICENSE                    MIT license
```

## Notes

This project is for hackathon demonstration purposes and is not financial advice.

## License

MIT
