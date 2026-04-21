"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Unit tests for MCP consumption tool argument normalization.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = PROJECT_ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import mcp_consumption


def test_tool_usage_summary_by_service_for_compartment_accepts_camel_case(
    monkeypatch,
) -> None:
    captured = {}

    def fake_usage_summary_by_service_for_compartment(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        mcp_consumption,
        "usage_summary_by_service_for_compartment",
        fake_usage_summary_by_service_for_compartment,
    )

    result = mcp_consumption.tool_usage_summary_by_service_for_compartment(
        startDay="2026-04-01",
        endDayInclusive="2026-04-21",
        compartment="lsaetta",
        queryType="COST",
        includeSubcompartments=True,
        maxCompartmentDepth=7,
        configProfile="DEFAULT",
    )

    assert result == {"ok": True}
    assert captured == {
        "start_day": "2026-04-01",
        "end_day_inclusive": "2026-04-21",
        "compartment": "lsaetta",
        "query_type": "COST",
        "include_subcompartments": True,
        "max_compartment_depth": 7,
        "config_profile": "DEFAULT",
    }


def test_tool_get_usage_summary_by_service_accepts_camel_case(monkeypatch) -> None:
    captured = {}

    def fake_get_usage_summary_by_service(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        mcp_consumption,
        "get_usage_summary_by_service",
        fake_get_usage_summary_by_service,
    )

    result = mcp_consumption.tool_get_usage_summary_by_service(
        startDay="2026-04-01",
        endDayInclusive="2026-04-21",
        queryType="USAGE",
    )

    assert result == {"ok": True}
    assert captured == {
        "start_day": "2026-04-01",
        "end_day_inclusive": "2026-04-21",
        "query_type": "USAGE",
    }


def test_tool_get_usage_summary_by_service_missing_args_returns_structured_error() -> None:
    result = mcp_consumption.tool_get_usage_summary_by_service()

    assert result["error_type"] == "missing_arguments"
    assert result["tool"] == "tool_get_usage_summary_by_service"
    assert set(result["missing_fields"]) == {"start_day", "end_day_inclusive"}
