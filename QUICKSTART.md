# Quickstart

This guide provides baseline setup and run instructions for the entire
`oci-cloud-consumption` project.
It will be updated as the project evolves.

## 1) Create Conda Environment

```bash
conda create -y -n oci-cloud-consumption python=3.11
conda activate oci-cloud-consumption
```

## 2) Install Required Libraries

Core runtime dependencies:

```bash
pip install -r requirements.txt
```

Developer tooling (install only if you plan to modify code and align with
repository quality standards):

```bash
pip install -r requirements-dev.txt
```

## 3) Create Local Environment File

```bash
cp .env.sample .env
```

Then edit `.env` with your real OCI values where needed.

## 4) Run the MCP Server (`mcp_consumption`)

Recommended startup (uvicorn + ASGI app):

```bash
uvicorn mcp_consumption:app --app-dir mcp --host 127.0.0.1 --port 8000
```

Custom host/port/path:

```bash
MCP_PATH=/mcp uvicorn mcp_consumption:app --app-dir mcp --host 127.0.0.1 --port 8000
```

Alternative startup (FastMCP runner):

```bash
python mcp/mcp_consumption.py
```

## 5) Run the Agent API (FastAPI)

```bash
uvicorn api.agent_api:app --host 127.0.0.1 --port 8100 --reload
```

Optional CORS override for Next.js clients:

```bash
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 uvicorn api.agent_api:app --host 127.0.0.1 --port 8100 --reload
```

## 6) Available MCP Tools

The server exposes these four public consumption tools:
- `tool_get_usage_summary_by_service`
- `tool_get_usage_summary_by_compartment`
- `tool_fetch_consumption_by_compartment`
- `tool_usage_summary_by_service_for_compartment`

## 7) Run Monthly Batch Report Agent

Generate monthly top-10 report by compartment and service:

```bash
python agent/batch_report_agent.py 2026-04
```

Save the report to a local file:

```bash
python agent/batch_report_agent.py 2026-04 --output-target local
```

Save the report to OCI Object Storage:

```bash
OCI_OBJECT_STORAGE_BUCKET_NAME=my-report-bucket \
python agent/batch_report_agent.py 2026-04 --output-target object_storage
```

Accepted month formats:
- `YYYY-MM` (for example `2026-04`)
- `MM-YYYY` (for example `04-2026`)

## Notes

- OCI authentication follows the backend logic in `utils/oci_utils.py`:
  config profile first, then resource-principal fallback.
- Batch Object Storage output uses `OCI_OBJECT_STORAGE_BUCKET_NAME` unless
  `--bucket-name` is passed, and can use `OCI_OBJECT_STORAGE_REPORT_PREFIX`.
- Date parameters are expected in ISO format (`YYYY-MM-DD`).
- MCP server list consumed by the agent is defined in `config/mcp_servers.json`.
