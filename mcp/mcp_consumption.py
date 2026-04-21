"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: FastMCP v2 server exposing OCI consumption analysis tools over streamable HTTP.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastmcp import FastMCP

# Ensure project root is available for local imports when this file is executed
# as a script (e.g. `python mcp/mcp_consumption.py`).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.consumption_utils import (
    fetch_consumption_by_compartment,
    get_usage_summary_by_compartment,
    get_usage_summary_by_service,
    usage_summary_by_service_for_compartment,
)

server = FastMCP(
    name="mcp_consumption",
    instructions=(
        "MCP server for OCI tenant consumption analysis. "
        "Provides service and compartment summaries plus service-filtered "
        "consumption exploration tools."
    ),
)

# ASGI app exposed for uvicorn startup.
# Endpoint path can be customized via MCP_PATH (default: /mcp).
app = server.http_app(
    transport="streamable-http",
    path=os.getenv("MCP_PATH", "/mcp"),
)


@server.tool
def tool_get_usage_summary_by_service(
    start_day: str,
    end_day_inclusive: str,
    query_type: str = "COST",
) -> Dict[str, Any]:
    """Return tenant-wide OCI consumption summary grouped by service.

    Use this tool when you need a high-level overview of cloud spend/usage by OCI
    service for a selected period.

    Args:
        start_day: Start day (inclusive) in ISO format `YYYY-MM-DD`.
        end_day_inclusive: End day (inclusive) in ISO format `YYYY-MM-DD`.
        query_type: Metric mode. Use `COST` for currency-based aggregation or
            `USAGE` for quantity-based aggregation.

    Returns:
        Dictionary with:
        - `period`: normalized query window (`start_inclusive`, `end_exclusive`)
        - `group_by`: list with `service`
        - `items`: one aggregated row per service
        - `totals`: overall amount/quantity totals
        - `metadata`: OCI request metadata (for example region and request id)
    """
    return get_usage_summary_by_service(
        start_day=start_day,
        end_day_inclusive=end_day_inclusive,
        query_type=query_type,
    )


@server.tool
def tool_get_usage_summary_by_compartment(
    start_day: str,
    end_day_inclusive: str,
    query_type: str = "COST",
) -> Dict[str, Any]:
    """Return tenant-wide OCI consumption summary grouped by compartment name.

    Use this tool when you want to compare consumption distribution across OCI
    compartments in a selected period.

    Args:
        start_day: Start day (inclusive) in ISO format `YYYY-MM-DD`.
        end_day_inclusive: End day (inclusive) in ISO format `YYYY-MM-DD`.
        query_type: Metric mode. Use `COST` for cost values or `USAGE` for raw
            quantity values.

    Returns:
        Dictionary with:
        - `period`: normalized query window
        - `group_by`: list with `compartmentName`
        - `items`: one aggregated row per compartment
        - `totals`: overall totals
        - `metadata`: OCI request metadata
    """
    return get_usage_summary_by_compartment(
        start_day=start_day,
        end_day_inclusive=end_day_inclusive,
        query_type=query_type,
    )


@server.tool
def tool_fetch_consumption_by_compartment(
    day_start: str,
    day_end: str,
    service: str,
    query_type: str = "COST",
    include_subcompartments: bool = True,
    max_compartment_depth: int = 7,
    config_profile: Optional[str] = "DEFAULT",
    debug: bool = False,
) -> Dict[str, Any]:
    """Fetch compartment-level rows filtered by a target service.

    Use this tool for investigative workflows where you need to isolate one
    service and inspect which compartments are generating the related cost/usage.

    Args:
        day_start: Start day (inclusive) in ISO format `YYYY-MM-DD`.
        day_end: End day (inclusive) in ISO format `YYYY-MM-DD`.
        service: Service label to filter (exact or partial text).
        query_type: Preferred metric mode (`COST` or `USAGE`).
        include_subcompartments: If true, include child compartments.
        max_compartment_depth: Maximum hierarchy depth to inspect (1..7).
        config_profile: OCI profile name; use `None` to force resource-principal
            authentication behavior from the backend.
        debug: If true, include diagnostic fields (service resolution, fallback
            mode, and effective query details).

    Returns:
        Dictionary with:
        - `rows`: filtered compartment/service rows
        - optional debug keys when `debug=True`, including:
          `resolved_service`, `service_candidates`, `query_used`,
          `filtered_server_side`, `depth`, `time_window`, and `input`.
    """
    return fetch_consumption_by_compartment(
        day_start=day_start,
        day_end=day_end,
        service=service,
        query_type=query_type,
        include_subcompartments=include_subcompartments,
        max_compartment_depth=max_compartment_depth,
        config_profile=config_profile,
        debug=debug,
    )


@server.tool
def tool_usage_summary_by_service_for_compartment(
    start_day: str,
    end_day_inclusive: str,
    compartment: str,
    query_type: str = "COST",
    include_subcompartments: bool = True,
    max_compartment_depth: int = 7,
    config_profile: Optional[str] = "DEFAULT",
) -> Dict[str, Any]:
    """Return service breakdown for a specific compartment scope.

    Use this tool when you already know the compartment of interest and need to
    identify which services drive its cost/usage profile.

    Args:
        start_day: Start day (inclusive) in ISO format `YYYY-MM-DD`.
        end_day_inclusive: End day (inclusive) in ISO format `YYYY-MM-DD`.
        compartment: Target compartment OCID or exact compartment name.
        query_type: Metric mode (`COST` or `USAGE`).
        include_subcompartments: If true, include child compartments in scope.
        max_compartment_depth: Maximum hierarchy depth to inspect (1..7).
        config_profile: OCI profile name; use `None` to rely on resource principals.

    Returns:
        Dictionary with:
        - `period`: normalized query window
        - `scope`: resolved compartment metadata
        - `group_by`: list with `service`
        - `items`: aggregated per-service rows with optional share percentage
        - `totals`: global totals for the selected scope
        - `metadata`: OCI request metadata
    """
    return usage_summary_by_service_for_compartment(
        start_day=start_day,
        end_day_inclusive=end_day_inclusive,
        compartment=compartment,
        query_type=query_type,
        include_subcompartments=include_subcompartments,
        max_compartment_depth=max_compartment_depth,
        config_profile=config_profile,
    )


def run_server() -> None:
    """Run the MCP server with FastMCP native runner.

    Note:
        For production-like usage prefer uvicorn startup with the exported
        ASGI `app` object (see QUICKSTART.md).

    Environment variables:
    - `MCP_HOST`: bind host (default: `0.0.0.0`)
    - `MCP_PORT`: bind port (default: `8000`)
    - `MCP_PATH`: MCP endpoint path (default: `/mcp`)
    """
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")

    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        path=path,
        show_banner=True,
    )


if __name__ == "__main__":
    run_server()
