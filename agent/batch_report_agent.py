"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Batch agent generating monthly OCI consumption top-10 reports
by compartment and service.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Ensure project root is importable when the script is executed directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load project .env so OCI_REGION / auth settings are honored in CLI mode.
load_dotenv(PROJECT_ROOT / ".env")

from utils.consumption_utils import (
    get_usage_summary_by_compartment,
    get_usage_summary_by_service,
)
from common.month_utils import month_window, parse_month_year


@dataclass
class RankedEntry:
    """One ranked row in a monthly top list."""

    label: str
    total_month: float
    percentage: float


def _parse_month_year(month_year: str) -> Tuple[int, int]:
    """Parse month-year input supporting `YYYY-MM` or `MM-YYYY`."""
    value = (month_year or "").strip()
    if not value:
        raise ValueError("month_year must be provided in format YYYY-MM or MM-YYYY.")

    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("Invalid month_year format. Use YYYY-MM or MM-YYYY.")

    first, second = parts[0], parts[1]
    if len(first) == 4 and len(second) == 2:
        year, month = int(first), int(second)
    elif len(first) == 2 and len(second) == 4:
        month, year = int(first), int(second)
    else:
        raise ValueError("Invalid month_year format. Use YYYY-MM or MM-YYYY.")

    if year < 1900 or year > 3000:
        raise ValueError("year must be between 1900 and 3000.")
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12.")

    return year, month


def _to_float(value: Any) -> float:
    """Convert a value to float, defaulting to 0.0 for None/invalid."""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row_label(row: Dict[str, Any], keys: List[str], fallback: str) -> str:
    """Extract first available string label from a row."""
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return fallback


def _build_ranked_entries(
    items: List[Dict[str, Any]],
    *,
    label_keys: List[str],
    total_overall: float,
    top_n: int,
) -> List[RankedEntry]:
    """Build sorted top-N entries with percentage over overall total."""
    ranked = sorted(items, key=lambda row: _to_float(row.get("amount")), reverse=True)
    selected = ranked[:top_n]
    entries: List[RankedEntry] = []
    for row in selected:
        total_month = _to_float(row.get("amount"))
        percentage = (total_month / total_overall * 100.0) if total_overall > 0 else 0.0
        entries.append(
            RankedEntry(
                label=_row_label(row, label_keys, fallback="<unknown>"),
                total_month=round(total_month, 2),
                percentage=round(percentage, 2),
            )
        )
    return entries


def _render_section(
    title: str, label_header: str, entries: List[RankedEntry]
) -> List[str]:
    """Render one markdown table section."""
    lines = [f"## {title}", ""]
    lines.append(f"| # | {label_header} | Monthly Total | % of Overall Total |")
    lines.append("|---:|---|---:|---:|")
    if not entries:
        lines.append("| 1 | <no data> | 0.00 | 0.00% |")
    else:
        for index, entry in enumerate(entries, start=1):
            lines.append(
                f"| {index} | {entry.label} | {entry.total_month:.2f} | {entry.percentage:.2f}% |"
            )
    lines.append("")
    return lines


class BatchConsumptionReportAgent:  # pylint: disable=too-few-public-methods,too-many-arguments
    """Batch agent that generates monthly top-10 OCI consumption reports."""

    def generate_report(
        self,
        month_year: str,
        *,
        query_type: str = "COST",
        top_n: int = 10,
        config_profile: Optional[str] = "DEFAULT",
        auth_type: Optional[str] = None,
    ) -> str:
        """Generate monthly report with top compartments and top services."""
        start_day, end_day = month_window(month_year)

        by_compartment = get_usage_summary_by_compartment(
            start_day=start_day,
            end_day_inclusive=end_day,
            query_type=query_type,
            config_profile=config_profile,
            auth_type=auth_type,
        )
        by_service = get_usage_summary_by_service(
            start_day=start_day,
            end_day_inclusive=end_day,
            query_type=query_type,
            config_profile=config_profile,
            auth_type=auth_type,
        )

        overall_total = _to_float((by_service.get("totals") or {}).get("amount"))
        if overall_total <= 0:
            overall_total = _to_float(
                (by_compartment.get("totals") or {}).get("amount")
            )

        compartment_entries = _build_ranked_entries(
            by_compartment.get("items", []),
            label_keys=["compartmentName", "compartment_name"],
            total_overall=overall_total,
            top_n=top_n,
        )
        service_entries = _build_ranked_entries(
            by_service.get("items", []),
            label_keys=["service", "serviceName", "service_name"],
            total_overall=overall_total,
            top_n=top_n,
        )

        report_lines: List[str] = []
        report_lines.append(f"# Monthly OCI Consumption Report ({month_year})")
        report_lines.append("")
        report_lines.append(f"- Query type: `{query_type}`")
        report_lines.append(f"- Time window: `{start_day}` to `{end_day}` (inclusive)")
        report_lines.append(f"- Overall total: **{overall_total:.2f}**")
        report_lines.append("")
        report_lines.extend(
            _render_section(
                f"Top {top_n} Compartments",
                "Compartment",
                compartment_entries,
            )
        )
        report_lines.extend(
            _render_section(
                f"Top {top_n} Services",
                "Service",
                service_entries,
            )
        )
        return "\n".join(report_lines).strip() + "\n"


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for batch report generation."""
    parser = argparse.ArgumentParser(
        description="Generate monthly OCI top-10 report by compartment and service."
    )
    parser.add_argument(
        "month_year",
        help="Target month in format YYYY-MM or MM-YYYY.",
    )
    parser.add_argument(
        "--query-type",
        default="COST",
        choices=["COST", "USAGE"],
        help="Aggregation mode (default: COST).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Top N rows for each section (default: 10).",
    )
    parser.add_argument(
        "--profile",
        default="DEFAULT",
        help="OCI profile name for API key authentication (default: DEFAULT).",
    )
    parser.add_argument(
        "--auth-type",
        default=None,
        help="Auth strategy: AUTO, API_KEY, RESOURCE_PRINCIPAL.",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = _parse_args()
    if args.top_n < 1:
        print("ERROR: --top-n must be >= 1")
        return 1

    try:
        agent = BatchConsumptionReportAgent()
        report = agent.generate_report(
            month_year=args.month_year,
            query_type=args.query_type,
            top_n=args.top_n,
            config_profile=args.profile,
            auth_type=args.auth_type,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"ERROR: {exc}")
        return 1

    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
