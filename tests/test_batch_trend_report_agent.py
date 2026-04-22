"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Unit tests for six-month trend batch report agent.
"""

from __future__ import annotations

import json

import pytest

from agent import batch_trend_report_agent


def test_previous_full_months_uses_six_months_before_reference() -> None:
    assert batch_trend_report_agent._previous_full_months("2026-04") == [
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
    ]


def test_generate_report_uses_llm_trend_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_compartment_summary(**kwargs):
        start_day = kwargs["start_day"]
        month = start_day[:7]
        amounts = {
            "2025-10": 10.0,
            "2025-11": 12.0,
            "2025-12": 14.0,
            "2026-01": 16.0,
            "2026-02": 18.0,
            "2026-03": 20.0,
        }
        return {
            "items": [
                {"compartmentName": "Finance", "amount": amounts[month]},
                {"compartmentName": "Dev", "amount": 5.0},
            ]
        }

    def fake_service_summary(**kwargs):
        start_day = kwargs["start_day"]
        month = start_day[:7]
        amounts = {
            "2025-10": 30.0,
            "2025-11": 31.0,
            "2025-12": 32.0,
            "2026-01": 33.0,
            "2026-02": 34.0,
            "2026-03": 35.0,
        }
        return {
            "items": [
                {"service": "Compute", "amount": amounts[month]},
                {"service": "Storage", "amount": 1.0},
            ]
        }

    class FakeLlm:
        def invoke(self, _prompt: str):
            return {
                "content": json.dumps(
                    {
                        "compartments": [
                            {
                                "name": "Finance",
                                "trend": "growing",
                                "is_growing": True,
                                "growth_pct": 100.0,
                                "reason": "Steady increase month over month.",
                            }
                        ],
                        "services": [
                            {
                                "name": "Compute",
                                "trend": "growing",
                                "is_growing": True,
                                "growth_pct": 16.67,
                                "reason": "Linear growth over the period.",
                            }
                        ],
                    }
                )
            }

    monkeypatch.setattr(
        batch_trend_report_agent,
        "get_usage_summary_by_compartment",
        fake_compartment_summary,
    )
    monkeypatch.setattr(
        batch_trend_report_agent,
        "get_usage_summary_by_service",
        fake_service_summary,
    )
    monkeypatch.setattr(
        batch_trend_report_agent,
        "create_chat_oci_genai",
        lambda: FakeLlm(),
    )

    agent = batch_trend_report_agent.BatchTrendReportAgent()
    report = agent.generate_report(reference_month="2026-04", top_n=1)

    assert "OCI Consumption Trend Report" in report
    assert "Top 1 Compartments - Trend Analysis" in report
    assert "Top 1 Services - Trend Analysis" in report
    assert "| 1 | Finance |" in report
    assert "| 1 | Compute |" in report
    assert "100.00%" in report
    assert "16.67%" in report


def test_generate_report_falls_back_when_llm_output_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_compartment_summary(**_kwargs):
        return {"items": [{"compartmentName": "Ops", "amount": 10.0}]}

    def fake_service_summary(**_kwargs):
        return {"items": [{"service": "Database", "amount": 5.0}]}

    class FakeInvalidLlm:
        def invoke(self, _prompt: str):
            return "not a json response"

    monkeypatch.setattr(
        batch_trend_report_agent,
        "get_usage_summary_by_compartment",
        fake_compartment_summary,
    )
    monkeypatch.setattr(
        batch_trend_report_agent,
        "get_usage_summary_by_service",
        fake_service_summary,
    )
    monkeypatch.setattr(
        batch_trend_report_agent,
        "create_chat_oci_genai",
        lambda: FakeInvalidLlm(),
    )

    agent = batch_trend_report_agent.BatchTrendReportAgent()
    report = agent.generate_report(reference_month="2026-04", top_n=1)

    assert "| 1 | Ops |" in report
    assert "| 1 | Database |" in report
    assert "0.00%" in report
