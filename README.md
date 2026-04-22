# OCI Cloud Consumption

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen.svg)](https://github.com/pylint-dev/pylint)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-0A9EDC.svg)](https://docs.pytest.org/)

> **AI-driven operational control for OCI tenant consumption**  
> `oci-cloud-consumption` is a focused platform for OCI tenant administrators who need clear visibility, proactive governance, and continuous control over cloud usage and cost.

---

## Why This Project
Managing cloud consumption is not only about reporting spend. It is about making faster decisions, preventing policy violations, and reacting early to anomalous patterns.

This project provides an AI-native approach to FinOps and governance on OCI through:
- an **interactive assistant** for consumption exploration and analysis;
- a set of **batch agents** for reporting, policy monitoring, and alerts;
- a **Python API layer** built on OCI SDK as the canonical data-access backbone;
- **remote access through MCP** for controlled integration with external clients.

---

## Core Capabilities

### 1. Interactive Assistant
- Query and analyze OCI consumption data in natural language.
- Explore trends, drill into usage/cost behavior, and support root-cause investigation.

### 2. Batch Agent Workflows
- Generate recurring consumption reports.
- Continuously verify policy compliance.
- Trigger alerts on anomalies, threshold breaches, and governance violations.

---

## Architecture Snapshot
- **Data Access Layer:** Python API in this repository, built on OCI Python SDK.
- **Remote Interface:** MCP server exposing the same capabilities to remote clients.
- **Security Model:** JWT-based authentication/authorization via OCI IAM.
- **Access Scope:** Admin-oriented workflows; no unrestricted end-user access.

---

## Specification-Driven Development
Project behavior and constraints are defined by the official specification:
- [Design.md](./Design.md)

All implementation decisions must remain aligned with that specification unless it is explicitly updated.

## Quickstart
- [QUICKSTART.md](./QUICKSTART.md)
- [Agent Guide](./agent/README.md)

## Run Services

Start MCP server (streamable HTTP):

```bash
uvicorn mcp_consumption:app --app-dir mcp --host 127.0.0.1 --port 8000
```

Start Agent API (FastAPI):

```bash
uvicorn api.agent_api:app --host 127.0.0.1 --port 8100 --reload
```

## Web Client

First test client (Next.js):
- [clients/agent-web-test/README.md](./clients/agent-web-test/README.md)
