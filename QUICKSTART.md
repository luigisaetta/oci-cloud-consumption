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

## 3) Run the MCP Server (`mcp_consumption`)

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

## 4) Available MCP Tools

The server exposes these four public consumption tools:
- `tool_get_usage_summary_by_service`
- `tool_get_usage_summary_by_compartment`
- `tool_fetch_consumption_by_compartment`
- `tool_usage_summary_by_service_for_compartment`

## Notes

- OCI authentication follows the backend logic in `utils/oci_utils.py`:
  config profile first, then resource-principal fallback.
- Date parameters are expected in ISO format (`YYYY-MM-DD`).
