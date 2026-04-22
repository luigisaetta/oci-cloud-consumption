# Agents Overview

This folder contains the project agents used for interactive and batch workflows.

## 1) `tool_calling_agent.py`

### What it does
- Runs the interactive OCI assistant using LangChain tool-calling.
- Loads tools from enabled MCP servers.
- Executes multi-step tool calls and returns final answers with execution metadata.

### Typical usage
- Used by the FastAPI service in `api/agent_api.py`.
- Main API endpoints:
  - `POST /agent/invoke`
  - `POST /agent/invoke/stream`

### What it produces
- Final assistant answer.
- Tool execution metadata:
  - MCP servers used
  - MCP server enabled/disabled statuses
  - Tool count
  - Raw message trace (non-stream endpoint)

---

## 2) `batch_report_agent.py`

### What it does
- Runs in batch mode from command line.
- Generates a monthly markdown report with:
  - Top 10 compartments
  - Top 10 services
- Each table includes:
  - Monthly total
  - Percentage of overall monthly total
- The report also shows one overall total in the summary section.

### Typical usage
```bash
python agent/batch_report_agent.py 2026-03
```

Accepted month formats:
- `YYYY-MM` (example: `2026-03`)
- `MM-YYYY` (example: `03-2026`)

Optional arguments:
- `--query-type COST|USAGE`
- `--top-n <int>`
- `--profile <OCI_PROFILE>`
- `--auth-type AUTO|API_KEY|RESOURCE_PRINCIPAL`

### What it produces
- Markdown report printed to stdout.
- Can be redirected to a file:
```bash
python agent/batch_report_agent.py 2026-03 > report_2026-03.md
```

## Where to document agents?

Best practice for this project:
- Keep the detailed operational guide here in `agent/README.md` (closest to code).
- Keep high-level architecture and onboarding references in root `README.md` and `docs/`.
