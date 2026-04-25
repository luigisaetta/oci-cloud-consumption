"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Interactive rich CLI menu to run batch agents and save markdown reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
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
from common.month_utils import (  # pylint: disable=wrong-import-position
    months_between as _months_between,
    normalize_month as _normalize_month,
)
from utils.report_output_utils import (  # pylint: disable=wrong-import-position
    OBJECT_STORAGE_BUCKET_ENV,
    OBJECT_STORAGE_PREFIX_ENV,
    SavedReport,
    build_object_name,
    save_report_to_local,
    save_report_to_object_storage,
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


@dataclass
class OutputOptions:
    """Report persistence options collected by the menu."""

    destination: str
    local_path: Optional[Path] = None
    bucket_name: Optional[str] = None
    object_name: Optional[str] = None


def _normalize_auth_type_choice(auth_type_choice: str) -> Optional[str]:
    """Normalize and validate auth type selection from CLI input."""
    normalized = (auth_type_choice or "").strip().upper()
    if normalized in {"", "NONE"}:
        return None
    if normalized not in {"AUTO", "API_KEY", "RESOURCE_PRINCIPAL"}:
        raise ValueError(
            "Invalid auth type. Allowed values: AUTO, API_KEY, RESOURCE_PRINCIPAL, NONE."
        )
    return normalized


def _normalize_output_destination(destination: str) -> str:
    """Normalize and validate output destination selection."""
    normalized = (destination or "").strip().lower()
    if normalized not in {"local", "object_storage"}:
        raise ValueError("Invalid output destination. Use local or object_storage.")
    return normalized


def _save_report(
    markdown: str,
    output_options: OutputOptions,
    *,
    config_profile: str,
    auth_type: Optional[str],
) -> SavedReport:
    """Persist markdown output to the selected destination."""
    if output_options.destination == "local":
        if output_options.local_path is None:
            raise ValueError("Local output path is required.")
        return save_report_to_local(markdown, output_options.local_path)

    if not output_options.object_name:
        raise ValueError("Object Storage object name is required.")
    return save_report_to_object_storage(
        markdown,
        bucket_name=output_options.bucket_name,
        object_name=output_options.object_name,
        config_profile=config_profile,
        auth_type=auth_type,
    )


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
    auth_type_choice = Prompt.ask(
        "Auth type",
        choices=["AUTO", "API_KEY", "RESOURCE_PRINCIPAL", "NONE"],
        default="NONE",
        show_choices=True,
        case_sensitive=False,
    ).strip()
    auth_type = _normalize_auth_type_choice(auth_type_choice)

    return RunOptions(
        query_type=query_type,
        top_n=top_n,
        profile=profile,
        auth_type=auth_type,
    )


def _collect_output_options(default_filename: str) -> OutputOptions:
    """Collect destination-specific report output options."""
    destination = _normalize_output_destination(
        Prompt.ask(
            "Output destination",
            choices=["local", "object_storage"],
            default="local",
            show_choices=True,
        )
    )
    if destination == "local":
        output_path = Path(
            Prompt.ask("Output file", default=str(OUTPUT_DIR / default_filename))
        )
        return OutputOptions(destination=destination, local_path=output_path)

    env_bucket = os.getenv(OBJECT_STORAGE_BUCKET_ENV, "").strip()
    if env_bucket:
        bucket_name = Prompt.ask("Object Storage bucket", default=env_bucket)
    else:
        bucket_name = Prompt.ask("Object Storage bucket")

    object_prefix = Prompt.ask(
        "Object prefix",
        default=os.getenv(OBJECT_STORAGE_PREFIX_ENV, "").strip(),
    )
    object_name = Prompt.ask(
        "Object name",
        default=build_object_name(default_filename, prefix=object_prefix),
    )
    return OutputOptions(
        destination=destination,
        bucket_name=bucket_name,
        object_name=object_name,
    )


def _preview_plan(rows: List[Tuple[str, str]]) -> None:
    """Show execution plan as a compact table."""
    table = Table(title="Run Preview")
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    for key, value in rows:
        table.add_row(key, value)
    console.print(table)


def _format_output_location(output_options: OutputOptions) -> str:
    """Format output options for the preview table."""
    if output_options.destination == "local":
        return str(output_options.local_path)
    return f"oci://{output_options.bucket_name}/{output_options.object_name}"


def _show_markdown_preview(markdown: str, max_lines: int = 14) -> None:
    """Show first lines of generated markdown."""
    lines = markdown.splitlines()
    preview = "\n".join(lines[:max_lines]).strip() or "<empty file>"
    console.print(
        Panel(
            preview,
            title=f"Report Preview ({min(len(lines), max_lines)} lines)",
            border_style="green",
        )
    )


def _run_monthly(agent: BatchConsumptionReportAgent) -> None:
    """Run monthly report flow."""
    console.print("\n[bold]Monthly report wizard[/bold]")
    month = _normalize_month(Prompt.ask("Target month (YYYY-MM or MM-YYYY)"))
    options = _collect_common_options()
    default_name = _default_monthly_filename(month)
    output_options = _collect_output_options(default_name)

    _preview_plan(
        [
            ("Job", "Monthly report"),
            ("Month", month),
            ("Query type", options.query_type),
            ("Top N", str(options.top_n)),
            ("Profile", options.profile),
            ("Auth type", options.auth_type or "<auto>"),
            ("Output", _format_output_location(output_options)),
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
        saved = _save_report(
            markdown,
            output_options,
            config_profile=options.profile,
            auth_type=options.auth_type,
        )

    console.print(f"\n[bold green]Report generated:[/bold green] {saved.location}\n")
    _show_markdown_preview(markdown)
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
    output_options = _collect_output_options(default_name)

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
            ("Output", _format_output_location(output_options)),
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
        markdown = "\n".join(report_lines).strip() + "\n"
        saved = _save_report(
            markdown,
            output_options,
            config_profile=options.profile,
            auth_type=options.auth_type,
        )

    console.print(
        f"\n[bold green]Range report generated:[/bold green] {saved.location}\n"
    )
    _show_markdown_preview(markdown)
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
    output_options = _collect_output_options(default_name)

    _preview_plan(
        [
            ("Job", "Trend report"),
            ("Reference month", reference_month),
            ("Analysis window", "Previous 6 full months"),
            ("Query type", options.query_type),
            ("Top N", str(options.top_n)),
            ("Profile", options.profile),
            ("Auth type", options.auth_type or "<auto>"),
            ("Output", _format_output_location(output_options)),
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
        saved = _save_report(
            markdown,
            output_options,
            config_profile=options.profile,
            auth_type=options.auth_type,
        )

    console.print(
        f"\n[bold green]Trend report generated:[/bold green] {saved.location}\n"
    )
    _show_markdown_preview(markdown)
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
