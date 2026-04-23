"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Unit tests for shared month parsing and normalization utilities.
"""

import pytest

from common import month_utils


def test_parse_month_year_accepts_yyyy_mm() -> None:
    assert month_utils.parse_month_year("2026-04") == (2026, 4)


def test_parse_month_year_accepts_mm_yyyy() -> None:
    assert month_utils.parse_month_year("04-2026") == (2026, 4)


def test_parse_month_year_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="Invalid month format"):
        month_utils.parse_month_year("2026/04")


def test_parse_month_year_rejects_out_of_range_year() -> None:
    with pytest.raises(ValueError, match="year must be between 1900 and 3000"):
        month_utils.parse_month_year("1899-12")


def test_normalize_month_returns_canonical_value() -> None:
    assert month_utils.normalize_month("04-2026") == "2026-04"


def test_months_between_inclusive_range() -> None:
    assert month_utils.months_between("2026-02", "2026-04") == [
        "2026-02",
        "2026-03",
        "2026-04",
    ]


def test_previous_full_months_before_reference() -> None:
    assert month_utils.previous_full_months("2026-04") == [
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
    ]
