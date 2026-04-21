"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: FastMCP v2 server exposing OCI consumption analysis tools over streamable HTTP.
"""

import os
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, Optional

from fastmcp import FastMCP
from dotenv import load_dotenv
from pydantic import Field

# Ensure project root is available for local imports when this file is executed
# as a script (e.g. `python mcp/mcp_consumption.py`).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load project environment variables (for example OCI_REGION) when running
# the MCP server standalone via uvicorn/python.
load_dotenv(PROJECT_ROOT / ".env")

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


def _coalesce(value: Any, alias: Any, field_name: str) -> Any:
    """Return the first non-None value between canonical and alias inputs.

    Args:
        value: Canonical snake_case value provided by caller.
        alias: Optional camelCase alias value provided by caller.
        field_name: Human-readable parameter name used for validation errors.

    Returns:
        The selected non-None value.

    """
    selected = value if value is not None else alias
    _ = field_name
    return selected


def _missing_arguments_response(
    tool_name: str,
    missing_fields: list[str],
) -> Dict[str, Any]:
    """Build a structured error payload for missing required tool arguments.

    Args:
        tool_name: Name of the tool receiving invalid input.
        missing_fields: Required fields that were not provided.

    Returns:
        Dictionary describing the validation issue in a model-readable form.
    """
    return {
        "error_type": "missing_arguments",
        "tool": tool_name,
        "missing_fields": missing_fields,
        "message": (
            "Missing required arguments. "
            "Accepted aliases include snake_case and camelCase forms."
        ),
    }


@server.tool
def tool_get_usage_summary_by_service(
    start_day: Optional[str] = None,
    end_day_inclusive: Optional[str] = None,
    query_type: Optional[str] = "COST",
    startDay: Optional[str] = None,
    endDayInclusive: Optional[str] = None,
    queryType: Optional[str] = None,
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
    resolved_start_day = _coalesce(start_day, startDay, "start_day")
    resolved_end_day = _coalesce(end_day_inclusive, endDayInclusive, "end_day_inclusive")
    missing_fields = []
    if not resolved_start_day:
        missing_fields.append("start_day")
    if not resolved_end_day:
        missing_fields.append("end_day_inclusive")
    if missing_fields:
        return _missing_arguments_response(
            "tool_get_usage_summary_by_service",
            missing_fields,
        )

    resolved_query_type = query_type if queryType is None else queryType
    if resolved_query_type is None:
        resolved_query_type = "COST"

    return get_usage_summary_by_service(
        start_day=resolved_start_day,
        end_day_inclusive=resolved_end_day,
        query_type=resolved_query_type,
    )


@server.tool
def tool_get_usage_summary_by_compartment(
    start_day: Optional[str] = None,
    end_day_inclusive: Optional[str] = None,
    query_type: Optional[str] = "COST",
    startDay: Optional[str] = None,
    endDayInclusive: Optional[str] = None,
    queryType: Optional[str] = None,
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
    resolved_start_day = _coalesce(start_day, startDay, "start_day")
    resolved_end_day = _coalesce(end_day_inclusive, endDayInclusive, "end_day_inclusive")
    missing_fields = []
    if not resolved_start_day:
        missing_fields.append("start_day")
    if not resolved_end_day:
        missing_fields.append("end_day_inclusive")
    if missing_fields:
        return _missing_arguments_response(
            "tool_get_usage_summary_by_compartment",
            missing_fields,
        )

    resolved_query_type = query_type if queryType is None else queryType
    if resolved_query_type is None:
        resolved_query_type = "COST"

    return get_usage_summary_by_compartment(
        start_day=resolved_start_day,
        end_day_inclusive=resolved_end_day,
        query_type=resolved_query_type,
    )


@server.tool
def tool_fetch_consumption_by_compartment(
    day_start: Optional[str] = None,
    day_end: Optional[str] = None,
    service: Optional[str] = None,
    query_type: Optional[str] = "COST",
    include_subcompartments: Optional[bool] = True,
    max_compartment_depth: Annotated[Optional[int], Field(ge=1, le=7)] = 7,
    config_profile: Optional[str] = "DEFAULT",
    debug: bool = False,
    dayStart: Optional[str] = None,
    dayEnd: Optional[str] = None,
    queryType: Optional[str] = None,
    includeSubcompartments: Optional[bool] = None,
    maxCompartmentDepth: Annotated[Optional[int], Field(ge=1, le=7)] = None,
    configProfile: Optional[str] = None,
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
    resolved_day_start = _coalesce(day_start, dayStart, "day_start")
    resolved_day_end = _coalesce(day_end, dayEnd, "day_end")
    resolved_service = _coalesce(service, None, "service")
    missing_fields = []
    if not resolved_day_start:
        missing_fields.append("day_start")
    if not resolved_day_end:
        missing_fields.append("day_end")
    if not resolved_service:
        missing_fields.append("service")
    if missing_fields:
        return _missing_arguments_response(
            "tool_fetch_consumption_by_compartment",
            missing_fields,
        )

    resolved_query_type = query_type if queryType is None else queryType
    if resolved_query_type is None:
        resolved_query_type = "COST"
    resolved_include_subcompartments = (
        include_subcompartments
        if includeSubcompartments is None
        else includeSubcompartments
    )
    if resolved_include_subcompartments is None:
        resolved_include_subcompartments = True
    resolved_max_compartment_depth = (
        max_compartment_depth
        if maxCompartmentDepth is None
        else maxCompartmentDepth
    )
    if resolved_max_compartment_depth is None:
        resolved_max_compartment_depth = 7
    resolved_config_profile = (
        config_profile if configProfile is None else configProfile
    )

    return fetch_consumption_by_compartment(
        day_start=resolved_day_start,
        day_end=resolved_day_end,
        service=resolved_service,
        query_type=resolved_query_type,
        include_subcompartments=resolved_include_subcompartments,
        max_compartment_depth=resolved_max_compartment_depth,
        config_profile=resolved_config_profile,
        debug=debug,
    )


@server.tool
def tool_usage_summary_by_service_for_compartment(
    start_day: Optional[str] = None,
    end_day_inclusive: Optional[str] = None,
    compartment: Optional[str] = None,
    query_type: Optional[str] = "COST",
    include_subcompartments: Optional[bool] = True,
    max_compartment_depth: Annotated[Optional[int], Field(ge=1, le=7)] = 7,
    config_profile: Optional[str] = "DEFAULT",
    startDay: Optional[str] = None,
    endDayInclusive: Optional[str] = None,
    queryType: Optional[str] = None,
    includeSubcompartments: Optional[bool] = None,
    maxCompartmentDepth: Annotated[Optional[int], Field(ge=1, le=7)] = None,
    configProfile: Optional[str] = None,
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
    resolved_start_day = _coalesce(start_day, startDay, "start_day")
    resolved_end_day = _coalesce(end_day_inclusive, endDayInclusive, "end_day_inclusive")
    resolved_compartment = _coalesce(compartment, None, "compartment")
    missing_fields = []
    if not resolved_start_day:
        missing_fields.append("start_day")
    if not resolved_end_day:
        missing_fields.append("end_day_inclusive")
    if not resolved_compartment:
        missing_fields.append("compartment")
    if missing_fields:
        return _missing_arguments_response(
            "tool_usage_summary_by_service_for_compartment",
            missing_fields,
        )

    resolved_query_type = query_type if queryType is None else queryType
    if resolved_query_type is None:
        resolved_query_type = "COST"
    resolved_include_subcompartments = (
        include_subcompartments
        if includeSubcompartments is None
        else includeSubcompartments
    )
    if resolved_include_subcompartments is None:
        resolved_include_subcompartments = True
    resolved_max_compartment_depth = (
        max_compartment_depth
        if maxCompartmentDepth is None
        else maxCompartmentDepth
    )
    if resolved_max_compartment_depth is None:
        resolved_max_compartment_depth = 7
    resolved_config_profile = (
        config_profile if configProfile is None else configProfile
    )

    return usage_summary_by_service_for_compartment(
        start_day=resolved_start_day,
        end_day_inclusive=resolved_end_day,
        compartment=resolved_compartment,
        query_type=resolved_query_type,
        include_subcompartments=resolved_include_subcompartments,
        max_compartment_depth=resolved_max_compartment_depth,
        config_profile=resolved_config_profile,
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
