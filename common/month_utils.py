"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Shared month parsing and normalization helpers used by agents and CLI flows.
"""

import calendar
from datetime import date
from typing import List, Tuple


def parse_month_year(month_value: str) -> Tuple[int, int]:
    """Parse month input supporting `YYYY-MM` or `MM-YYYY`."""
    value = (month_value or "").strip()
    if not value:
        raise ValueError("month must be provided in format YYYY-MM or MM-YYYY.")

    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("Invalid month format. Use YYYY-MM or MM-YYYY.")

    first, second = parts[0], parts[1]
    if len(first) == 4 and len(second) == 2:
        year, month = int(first), int(second)
    elif len(first) == 2 and len(second) == 4:
        month, year = int(first), int(second)
    else:
        raise ValueError("Invalid month format. Use YYYY-MM or MM-YYYY.")

    if year < 1900 or year > 3000:
        raise ValueError("year must be between 1900 and 3000.")
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12.")
    return year, month


def format_month(year: int, month: int) -> str:
    """Return month in canonical format YYYY-MM."""
    return f"{year:04d}-{month:02d}"


def normalize_month(month_value: str) -> str:
    """Normalize input month into canonical YYYY-MM."""
    return format_month(*parse_month_year(month_value))


def month_window(month_value: str) -> Tuple[str, str]:
    """Return month window as start/end inclusive ISO dates."""
    year, month = parse_month_year(month_value)
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start.isoformat(), end.isoformat()


def months_between(start_month: str, end_month: str) -> List[str]:
    """Return inclusive list of normalized months between two endpoints."""
    start_year, start_num = parse_month_year(start_month)
    end_year, end_num = parse_month_year(end_month)
    start_key = start_year * 12 + start_num
    end_key = end_year * 12 + end_num
    if start_key > end_key:
        raise ValueError("Start month must be <= end month.")

    out: List[str] = []
    current_year, current_month = start_year, start_num
    while current_year * 12 + current_month <= end_key:
        out.append(format_month(current_year, current_month))
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    return out


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    """Shift a year-month pair by delta months."""
    index = year * 12 + (month - 1) + delta
    out_year = index // 12
    out_month = index % 12 + 1
    return out_year, out_month


def previous_full_months(reference_month: str, count: int = 6) -> List[str]:
    """Return the previous `count` full months before reference month."""
    year, month = parse_month_year(reference_month)
    months: List[str] = []
    for delta in range(-count, 0):
        out_year, out_month = shift_month(year, month, delta)
        months.append(format_month(out_year, out_month))
    return months
