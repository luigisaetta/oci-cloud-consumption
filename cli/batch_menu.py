"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Interactive CLI menu to run batch agents and save markdown reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Optional, Tuple

# Ensure project root imports work when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.batch_report_agent import (  # pylint: disable=wrong-import-position
    BatchConsumptionReportAgent,
)

OUTPUT_DIR = Path("reports")


@dataclass
class RunOptions:
    """Runtime options shared across batch report executions."""

    query_type: str = "COST"
    top_n: int = 10
    profile: str = "DEFAULT"
    auth_type: Optional[str] = None


def _parse_month(month_value: str) -> Tuple[int, int]:
    """Parse a month string in format YYYY-MM or MM-YYYY."""
    raw = (month_value or "").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError("Invalid month format. Use YYYY-MM or MM-YYYY.")

    a, b = parts[0], parts[1]
    if len(a) == 4 and len(b) == 2:
        year, month = int(a), int(b)
    elif len(a) == 2 and len(b) == 4:
        year, month = int(b), int(a)
    else:
        raise ValueError("Invalid month format. Use YYYY-MM or MM-YYYY.")

    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")
    return year, month


def _format_month(year: int, month: int) -> str:
    """Format month as YYYY-MM."""
    return f"{year:04d}-{month:02d}"


def _months_between(start_month: str, end_month: str) -> List[str]:
    """Return inclusive list of months between two endpoints."""
    start_year, start_num = _parse_month(start_month)
    end_year, end_num = _parse_month(end_month)
    start_key = start_year * 12 + start_num
    end_key = end_year * 12 + end_num
    if start_key > end_key:
        raise ValueError("Start month must be <= end month.")

    out: List[str] = []
    current_year, current_month = start_year, start_num
    while current_year * 12 + current_month <= end_key:
        out.append(_format_month(current_year, current_month))
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    return out


def _ask(prompt: str, default: Optional[str] = None) -> str:
    """Read one input value with optional default."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if not value and default is not None:
        return default
    return value


def _print_header() -> None:
    """Render a compact visual header."""
    print("")
    print("==============================================")
    print(" OCI Cloud Consumption - Batch Menu")
    print("==============================================")
    print("")


def _print_menu() -> None:
    """Render menu options."""
    print("[1] Monthly report")
    print("[2] Range report")
    print("[0] Exit")
    print("")


def _collect_common_options() -> RunOptions:
    """Collect shared options for batch report generation."""
    query_type = _ask("Query type (COST or USAGE)", "COST").upper()
    if query_type not in {"COST", "USAGE"}:
        raise ValueError("query_type must be COST or USAGE.")

    top_n_raw = _ask("Top N rows", "10")
    top_n = int(top_n_raw)
    if top_n < 1:
        raise ValueError("Top N must be >= 1.")

    profile = _ask("OCI profile", "DEFAULT")
    auth_type_raw = _ask("Auth type (AUTO/API_KEY/RESOURCE_PRINCIPAL or empty)", "")
    auth_type = auth_type_raw or None

    return RunOptions(
        query_type=query_type,
        top_n=top_n,
        profile=profile,
        auth_type=auth_type,
    )


def _save_report(markdown: str, output_path: Path) -> None:
    """Persist markdown output to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def _monthly_report_flow(agent: BatchConsumptionReportAgent) -> None:
    """Run monthly report flow."""
    month = _ask("Target month (YYYY-MM or MM-YYYY)")
    options = _collect_common_options()
    default_name = f"monthly-report-{month.replace('-', '')}.md"
    output_raw = _ask("Output file", str(OUTPUT_DIR / default_name))
    output_path = Path(output_raw)

    markdown = agent.generate_report(
        month_year=month,
        query_type=options.query_type,
        top_n=options.top_n,
        config_profile=options.profile,
        auth_type=options.auth_type,
    )
    _save_report(markdown, output_path)
    print("")
    print(f"Report generated: {output_path}")
    print("")


def _range_report_flow(agent: BatchConsumptionReportAgent) -> None:
    """Run range report flow by stitching monthly report outputs."""
    start_month = _ask("Start month (YYYY-MM or MM-YYYY)")
    end_month = _ask("End month (YYYY-MM or MM-YYYY)")
    options = _collect_common_options()

    month_list = _months_between(start_month, end_month)
    normalized_start = month_list[0]
    normalized_end = month_list[-1]
    default_name = (
        f"range-report-{normalized_start.replace('-', '')}-to-"
        f"{normalized_end.replace('-', '')}.md"
    )
    output_raw = _ask("Output file", str(OUTPUT_DIR / default_name))
    output_path = Path(output_raw)

    report_lines: List[str] = []
    report_lines.append("# OCI Consumption Range Report")
    report_lines.append("")
    report_lines.append(f"- Period: `{normalized_start}` to `{normalized_end}`")
    report_lines.append(f"- Months included: **{len(month_list)}**")
    report_lines.append(
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`"
    )
    report_lines.append("")

    for index, month in enumerate(month_list, start=1):
        report_lines.append(f"## Monthly Report {index}: {month}")
        report_lines.append("")
        report_lines.append(
            agent.generate_report(
                month_year=month,
                query_type=options.query_type,
                top_n=options.top_n,
                config_profile=options.profile,
                auth_type=options.auth_type,
            ).strip()
        )
        report_lines.append("")

    _save_report("\n".join(report_lines).strip() + "\n", output_path)
    print("")
    print(f"Range report generated: {output_path}")
    print("")


def main() -> int:
    """Entry point for batch interactive menu."""
    agent = BatchConsumptionReportAgent()
    while True:
        _print_header()
        _print_menu()
        choice = _ask("Select option", "1")
        try:
            if choice == "0":
                print("Goodbye.")
                return 0
            if choice == "1":
                _monthly_report_flow(agent)
            elif choice == "2":
                _range_report_flow(agent)
            else:
                print("")
                print("Invalid option. Please select 0, 1, or 2.")
                print("")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print("")
            print(f"ERROR: {exc}")
            print("")


if __name__ == "__main__":
    raise SystemExit(main())
