# MongoDB MCP Integration

Smart Portfolio Agent targets the MongoDB partner track by using MongoDB Atlas as the portfolio memory layer and by providing an ADK entrypoint that connects to the official MongoDB MCP Server.

## What MCP Adds

The Flask app uses MongoDB directly for the live web demo. The hackathon compliance path is:

```text
Google ADK / Agent Builder
  -> Gemini
  -> MongoDB MCP Server
  -> MongoDB Atlas portfolio_agent database
```

MongoDB MCP gives the agent database tools such as collection discovery, schema inspection, find queries, aggregations, document insertion, updates, indexes, and database statistics.

## Files

- `agent/mongodb_adk_agent.py`: ADK `root_agent` configured with `McpToolset`.
- `mcp/mongodb-mcp.json`: MCP client configuration example.
- `tools/mongodb_client.py`: direct MongoDB operations used by the Flask demo.

## Run Locally

Install Python and Node dependencies:

```powershell
pip install -r requirements.txt
node --version
npx -y mongodb-mcp-server --help
```

Set environment variables:

```powershell
$env:MONGODB_URI="mongodb+srv://user:password@cluster.example.mongodb.net/portfolio_agent?retryWrites=true&w=majority"
$env:GOOGLE_CLOUD_PROJECT="your-google-cloud-project-id"
$env:GOOGLE_CLOUD_LOCATION="us-central1"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

Run the ADK agent:

```powershell
adk run adk_portfolio_agent
```

Or open the ADK web runner if installed:

```powershell
adk web
```

## Safety

The sample MCP configuration disables destructive drop/delete operations:

```text
MDB_MCP_DISABLED_TOOLS=drop-database,drop-collection,delete-many
```

Keep `MONGODB_URI` in `.env`, Secret Manager, or your local shell. Do not commit real credentials.
