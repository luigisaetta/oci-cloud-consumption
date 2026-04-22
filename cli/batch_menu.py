"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Interactive rich CLI menu to run batch agents and save markdown reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

# Ensure project root imports work when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.batch_report_agent import (  # pylint: disable=wrong-import-position
    BatchConsumptionReportAgent,
)
from agent.batch_trend_report_agent import (  # pylint: disable=wrong-import-position
    BatchTrendReportAgent,
)

OUTPUT_DIR = Path("reports")
console = Console()


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

    first, second = parts[0], parts[1]
    if len(first) == 4 and len(second) == 2:
        year, month = int(first), int(second)
    elif len(first) == 2 and len(second) == 4:
        year, month = int(second), int(first)
    else:
        raise ValueError("Invalid month format. Use YYYY-MM or MM-YYYY.")

    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")
    return year, month


def _format_month(year: int, month: int) -> str:
    """Format month as YYYY-MM."""
    return f"{year:04d}-{month:02d}"


def _normalize_month(month_value: str) -> str:
    """Normalize month input into YYYY-MM."""
    year, month = _parse_month(month_value)
    return _format_month(year, month)


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


def _save_report(markdown: str, output_path: Path) -> None:
    """Persist markdown output to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def _default_monthly_filename(month: str) -> str:
    """Build canonical default filename for monthly reports."""
    return f"monthly-report-{month}.md"


def _default_range_filename(start_month: str, end_month: str) -> str:
    """Build canonical default filename for range reports."""
    return f"range-report-{start_month}_to_{end_month}.md"


def _default_trend_filename(reference_month: str) -> str:
    """Build canonical default filename for trend reports."""
    return f"trend-report-last6-until-{reference_month}.md"


def _render_header() -> None:
    """Render top header panel."""
    title = Text("OCI Cloud Consumption - Batch Menu", style="bold cyan")
    subtitle = Text(
        "Interactive runner for monthly and range markdown reports",
        style="dim",
    )
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="blue"))


def _render_main_menu() -> None:
    """Render the main options table."""
    table = Table(title="Available Batch Jobs", show_lines=False)
    table.add_column("Option", style="bold", justify="center", width=8)
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    table.add_row("1", "Monthly report", "Top compartments and services for one month")
    table.add_row(
        "2",
        "Range report",
        "Generate one markdown report containing all months in a range",
    )
    table.add_row(
        "3",
        "Trend report",
        "Analyze previous 6 full months on top compartments and services",
    )
    table.add_row("0", "Exit", "Quit the menu")
    console.print(table)


def _collect_common_options() -> RunOptions:
    """Collect shared options for batch report generation."""
    console.print("\n[bold]Report options[/bold]")
    query_type = Prompt.ask("Query type", choices=["COST", "USAGE"], default="COST")
    top_n = IntPrompt.ask("Top N rows", default=10)
    if top_n < 1:
        raise ValueError("Top N must be >= 1.")

    profile = Prompt.ask("OCI profile", default="DEFAULT")
    auth_type_raw = Prompt.ask(
        "Auth type (AUTO/API_KEY/RESOURCE_PRINCIPAL or empty)",
        default="",
    ).strip()
    auth_type = auth_type_raw or None

    return RunOptions(
        query_type=query_type,
        top_n=top_n,
        profile=profile,
        auth_type=auth_type,
    )


def _preview_plan(rows: List[Tuple[str, str]]) -> None:
    """Show execution plan as a compact table."""
    table = Table(title="Run Preview")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


def _show_saved_file_preview(output_path: Path, max_lines: int = 14) -> None:
    """Show first lines of saved markdown file."""
    try:
        lines = output_path.read_text(encoding="utf-8").splitlines()
    except Exception:  # pylint: disable=broad-exception-caught
        return

    preview = "\n".join(lines[:max_lines]).strip() or "<empty file>"
    console.print(
        Panel(
            preview,
            title=f"Saved Report Preview ({min(len(lines), max_lines)} lines)",
            border_style="green",
        )
    )


def _run_monthly(agent: BatchConsumptionReportAgent) -> None:
    """Run monthly report flow."""
    console.print("\n[bold]Monthly report wizard[/bold]")
    month = _normalize_month(Prompt.ask("Target month (YYYY-MM or MM-YYYY)"))
    options = _collect_common_options()
    default_name = _default_monthly_filename(month)
    output_path = Path(
        Prompt.ask("Output file", default=str(OUTPUT_DIR / default_name))
    )

    _preview_plan(
        [
            ("Job", "Monthly report"),
            ("Month", month),
            ("Query type", options.query_type),
            ("Top N", str(options.top_n)),
            ("Profile", options.profile),
            ("Auth type", options.auth_type or "<auto>"),
            ("Output", str(output_path)),
        ]
    )
    if not Confirm.ask("Run this job now?", default=True):
        console.print("[yellow]Cancelled.[/yellow]\n")
        return

    with console.status("[bold green]Running monthly report...[/bold green]"):
        markdown = agent.generate_report(
            month_year=month,
            query_type=options.query_type,
            top_n=options.top_n,
            config_profile=options.profile,
            auth_type=options.auth_type,
        )
        _save_report(markdown, output_path)

    console.print(f"\n[bold green]Report generated:[/bold green] {output_path}\n")
    _show_saved_file_preview(output_path)
    console.print("")


def _run_range(agent: BatchConsumptionReportAgent) -> None:
    """Run range report flow by stitching monthly report outputs."""
    console.print("\n[bold]Range report wizard[/bold]")
    start_month = _normalize_month(Prompt.ask("Start month (YYYY-MM or MM-YYYY)"))
    end_month = _normalize_month(Prompt.ask("End month (YYYY-MM or MM-YYYY)"))
    options = _collect_common_options()

    month_list = _months_between(start_month, end_month)
    normalized_start = month_list[0]
    normalized_end = month_list[-1]
    default_name = _default_range_filename(normalized_start, normalized_end)
    output_path = Path(
        Prompt.ask("Output file", default=str(OUTPUT_DIR / default_name))
    )

    _preview_plan(
        [
            ("Job", "Range report"),
            ("Start", normalized_start),
            ("End", normalized_end),
            ("Months", str(len(month_list))),
            ("Query type", options.query_type),
            ("Top N", str(options.top_n)),
            ("Profile", options.profile),
            ("Auth type", options.auth_type or "<auto>"),
            ("Output", str(output_path)),
        ]
    )
    if not Confirm.ask("Run this job now?", default=True):
        console.print("[yellow]Cancelled.[/yellow]\n")
        return

    report_lines: List[str] = []
    report_lines.append("# OCI Consumption Range Report")
    report_lines.append("")
    report_lines.append(f"- Period: `{normalized_start}` to `{normalized_end}`")
    report_lines.append(f"- Months included: **{len(month_list)}**")
    report_lines.append(
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`"
    )
    report_lines.append("")

    with console.status("[bold green]Running range report...[/bold green]"):
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

    console.print(f"\n[bold green]Range report generated:[/bold green] {output_path}\n")
    _show_saved_file_preview(output_path)
    console.print("")


def _run_trend(agent: BatchTrendReportAgent) -> None:
    """Run six-month trend report flow."""
    console.print("\n[bold]Trend report wizard[/bold]")
    default_reference = datetime.now().strftime("%Y-%m")
    reference_month = _normalize_month(
        Prompt.ask(
            "Reference month (YYYY-MM or MM-YYYY)",
            default=default_reference,
        )
    )
    options = _collect_common_options()
    default_name = _default_trend_filename(reference_month)
    output_path = Path(
        Prompt.ask("Output file", default=str(OUTPUT_DIR / default_name))
    )

    _preview_plan(
        [
            ("Job", "Trend report"),
            ("Reference month", reference_month),
            ("Analysis window", "Previous 6 full months"),
            ("Query type", options.query_type),
            ("Top N", str(options.top_n)),
            ("Profile", options.profile),
            ("Auth type", options.auth_type or "<auto>"),
            ("Output", str(output_path)),
        ]
    )
    if not Confirm.ask("Run this job now?", default=True):
        console.print("[yellow]Cancelled.[/yellow]\n")
        return

    with console.status("[bold green]Running trend report...[/bold green]"):
        markdown = agent.generate_report(
            reference_month=reference_month,
            query_type=options.query_type,
            top_n=options.top_n,
            config_profile=options.profile,
            auth_type=options.auth_type,
        )
        _save_report(markdown, output_path)

    console.print(f"\n[bold green]Trend report generated:[/bold green] {output_path}\n")
    _show_saved_file_preview(output_path)
    console.print("")


def main() -> int:
    """Entry point for batch interactive menu."""
    agent = BatchConsumptionReportAgent()
    trend_agent = BatchTrendReportAgent()

    while True:
        try:
            console.clear()
            _render_header()
            _render_main_menu()
            choice = Prompt.ask(
                "Select option",
                choices=["0", "1", "2", "3"],
                default="1",
            )
            if choice == "0":
                console.print("\n[bold]Goodbye.[/bold]")
                return 0
            if choice == "1":
                _run_monthly(agent)
            elif choice == "2":
                _run_range(agent)
            elif choice == "3":
                _run_trend(trend_agent)
            Prompt.ask("Press Enter to continue", default="")
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/yellow]")
            return 130
        except Exception as exc:  # pylint: disable=broad-exception-caught
            console.print(f"\n[bold red]ERROR:[/bold red] {exc}\n")
            Prompt.ask("Press Enter to continue", default="")


if __name__ == "__main__":
    raise SystemExit(main())
