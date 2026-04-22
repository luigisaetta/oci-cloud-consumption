"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Unit tests for monthly batch report agent.
"""

import pytest

from agent import batch_report_agent


def test_parse_month_year_accepts_yyyy_mm() -> None:
    assert batch_report_agent._parse_month_year("2026-04") == (2026, 4)


def test_parse_month_year_accepts_mm_yyyy() -> None:
    assert batch_report_agent._parse_month_year("04-2026") == (2026, 4)


def test_parse_month_year_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid month_year format"):
        batch_report_agent._parse_month_year("2026/04")


def test_generate_report_builds_top_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        batch_report_agent,
        "get_usage_summary_by_compartment",
        lambda **_kwargs: {
            "items": [
                {"compartmentName": "Finance", "amount": 70.0},
                {"compartmentName": "Dev", "amount": 30.0},
            ],
            "totals": {"amount": 100.0},
        },
    )
    monkeypatch.setattr(
        batch_report_agent,
        "get_usage_summary_by_service",
        lambda **_kwargs: {
            "items": [
                {"service": "Compute", "amount": 80.0},
                {"service": "Object Storage", "amount": 20.0},
            ],
            "totals": {"amount": 100.0},
        },
    )

    agent = batch_report_agent.BatchConsumptionReportAgent()
    report = agent.generate_report("2026-04")

    assert "Top 10 Compartments" in report
    assert "Top 10 Services" in report
    assert "Totale su tutti: **100.00**" in report
    assert "| 1 | Finance | 70.00 | 70.00% | 100.00 |" in report
    assert "| 1 | Compute | 80.00 | 80.00% | 100.00 |" in report
