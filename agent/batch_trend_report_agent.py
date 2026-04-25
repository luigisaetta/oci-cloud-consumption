"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Batch agent generating six-month OCI trend reports on top compartments
and services, with LLM-based trend interpretation.
"""

# pylint: disable=too-many-locals

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Ensure project root is importable when the script is executed directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load project .env so OCI_REGION / auth settings are honored in CLI mode.
load_dotenv(PROJECT_ROOT / ".env")

from utils.consumption_utils import (  # pylint: disable=wrong-import-position
    get_usage_summary_by_compartment,
    get_usage_summary_by_service,
)
from utils import (  # pylint: disable=wrong-import-position
    emit_structured_log,
    get_console_logger,
)
from utils.oci_model import (  # pylint: disable=wrong-import-position
    create_chat_oci_genai,
)
from utils.report_output_utils import (  # pylint: disable=wrong-import-position
    add_report_output_arguments,
    save_report_from_args,
)
from common.month_utils import (  # pylint: disable=wrong-import-position
    format_month as _format_month,
    month_window as _month_window,
    parse_month_year as _parse_month_year,
    previous_full_months as _previous_full_months,
)

logger = get_console_logger(name="BatchTrendReportAgent")


@dataclass
class TrendSeries:
    """One ranked trend series for a label over multiple months."""

    label: str
    monthly_values: List[float]
    total_period: float


@dataclass
class TrendInsight:
    """Trend classification and growth metrics."""

    trend: str
    is_growing: bool
    growth_pct: Optional[float]
    reason: str


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


def _extract_amounts(
    items: List[Dict[str, Any]], *, label_keys: List[str]
) -> Dict[str, float]:
    """Convert API rows into `{label: amount}` map."""
    out: Dict[str, float] = {}
    for row in items:
        label = _row_label(row, label_keys, fallback="<unknown>")
        out[label] = out.get(label, 0.0) + _to_float(row.get("amount"))
    return out


def _select_top_series(
    month_maps: List[Dict[str, float]], top_n: int
) -> List[TrendSeries]:
    """Build top-N series based on total over all selected months."""
    totals: Dict[str, float] = {}
    for month_map in month_maps:
        for label, value in month_map.items():
            totals[label] = totals.get(label, 0.0) + _to_float(value)

    top_labels = [
        item[0]
        for item in sorted(totals.items(), key=lambda item: item[1], reverse=True)[
            :top_n
        ]
    ]
    series: List[TrendSeries] = []
    for label in top_labels:
        monthly_values = [
            round(_to_float(month_map.get(label, 0.0)), 2) for month_map in month_maps
        ]
        series.append(
            TrendSeries(
                label=label,
                monthly_values=monthly_values,
                total_period=round(sum(monthly_values), 2),
            )
        )
    return series


def _extract_text_from_model_output(model_output: Any) -> str:
    """Extract textual content from model output structures."""
    content = getattr(model_output, "content", model_output)
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract first valid JSON object from text."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _round_optional(value: Optional[float]) -> Optional[float]:
    """Round float if present."""
    if value is None:
        return None
    return round(float(value), 2)


def _fallback_insight(values: List[float]) -> TrendInsight:
    """Deterministic fallback trend interpretation."""
    if not values:
        return TrendInsight(
            trend="stable",
            is_growing=False,
            growth_pct=0.0,
            reason="No monthly values available.",
        )

    first = _to_float(values[0])
    last = _to_float(values[-1])
    growth_pct: Optional[float]
    if first > 0:
        growth_pct = ((last - first) / first) * 100.0
    elif last > 0:
        growth_pct = None
    else:
        growth_pct = 0.0

    non_decreasing = all(
        values[index] <= values[index + 1] for index in range(len(values) - 1)
    )
    non_increasing = all(
        values[index] >= values[index + 1] for index in range(len(values) - 1)
    )

    if non_decreasing and any(
        values[index] < values[index + 1] for index in range(len(values) - 1)
    ):
        trend = "growing"
    elif non_increasing and any(
        values[index] > values[index + 1] for index in range(len(values) - 1)
    ):
        trend = "declining"
    elif abs(last - first) <= 0.01:
        trend = "stable"
    else:
        trend = "volatile"

    is_growing = trend == "growing" or (growth_pct is not None and growth_pct > 0.0)
    return TrendInsight(
        trend=trend,
        is_growing=is_growing,
        growth_pct=_round_optional(growth_pct),
        reason="Fallback trend analysis (LLM output unavailable or invalid).",
    )


def _render_trend_section(
    title: str, months: List[str], rows: List[Tuple[int, TrendSeries, TrendInsight]]
) -> List[str]:
    """Render markdown table for trend section."""
    header_months = " / ".join(months)
    lines = [f"## {title}", "", f"Months (oldest -> latest): `{header_months}`", ""]
    lines.append("| # | Name | 6M Total | Monthly Values | Trend | Growth % |")
    lines.append("|---:|---|---:|---|---|---:|")
    if not rows:
        lines.append("| 1 | <no data> | 0.00 | - | stable | 0.00% |")
    else:
        for rank, series, insight in rows:
            values_text = ", ".join(f"{value:.2f}" for value in series.monthly_values)
            growth_text = "n/a"
            if insight.growth_pct is not None:
                growth_text = f"{insight.growth_pct:.2f}%"
            lines.append(
                f"| {rank} | {series.label} | {series.total_period:.2f} | {values_text} | "
                f"{insight.trend} | {growth_text} |"
            )
    lines.append("")
    return lines


def _default_trend_filename(reference_month: str) -> str:
    """Build canonical default filename for trend reports."""
    return f"trend-report-last6-until-{reference_month}.md"


class BatchTrendReportAgent:  # pylint: disable=too-few-public-methods,too-many-arguments
    """Batch agent generating trend analysis for top compartments and services."""

    def __init__(self) -> None:
        """Initialize trend agent and LLM client."""
        self.llm = create_chat_oci_genai()

    @staticmethod
    def _log_agent_event(
        *,
        operation: str,
        status: str,
        error_details: str = "",
        **extra: Any,
    ) -> None:
        """Emit structured logs for batch trend observability."""
        emit_structured_log(
            logger,
            component="agent",
            operation=operation,
            status=status,
            error_details=error_details,
            **extra,
        )

    def _analyze_with_llm(
        self,
        *,
        months: List[str],
        compartment_series: List[TrendSeries],
        service_series: List[TrendSeries],
    ) -> Dict[str, Dict[str, TrendInsight]]:
        """Run LLM-based trend analysis returning insights keyed by label."""
        payload = {
            "months": months,
            "compartments": [
                {"name": row.label, "values": row.monthly_values}
                for row in compartment_series
            ],
            "services": [
                {"name": row.label, "values": row.monthly_values}
                for row in service_series
            ],
        }
        prompt = (
            "You are an OCI consumption trend analyst.\n"
            "Analyze the 6-month time series and identify if each item has a growing trend.\n"
            "Return JSON only with this schema:\n"
            "{\n"
            '  "compartments": [{"name": str, "trend": str, "is_growing": bool, '
            '"growth_pct": number|null, "reason": str}],\n'
            '  "services": [{"name": str, "trend": str, "is_growing": bool, '
            '"growth_pct": number|null, "reason": str}]\n'
            "}\n"
            "Rules:\n"
            "- trend must be one of: growing, stable, declining, volatile.\n"
            "- growth_pct should represent percentage change from first to last month "
            "when meaningful.\n"
            "- Keep reasons short (max 20 words).\n\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=True)}"
        )
        try:
            raw = self.llm.invoke(prompt)
        except Exception as exc:  # pragma: no cover - runtime integration behavior
            self._log_agent_event(
                operation="llm_invoke",
                status="failure",
                error_details=str(exc),
                months_count=len(months),
                compartments_count=len(compartment_series),
                services_count=len(service_series),
            )
            raise

        self._log_agent_event(
            operation="llm_invoke",
            status="success",
            months_count=len(months),
            compartments_count=len(compartment_series),
            services_count=len(service_series),
        )
        parsed = _extract_json_object(_extract_text_from_model_output(raw))
        if not parsed:
            self._log_agent_event(
                operation="llm_parse",
                status="failure",
                error_details="invalid_or_empty_json_response",
            )
            return {"compartments": {}, "services": {}}

        def normalize(section_name: str) -> Dict[str, TrendInsight]:
            section = parsed.get(section_name, [])
            if not isinstance(section, list):
                return {}
            out: Dict[str, TrendInsight] = {}
            for item in section:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                trend = str(item.get("trend") or "stable").strip().lower()
                if trend not in {"growing", "stable", "declining", "volatile"}:
                    trend = "stable"
                is_growing = bool(item.get("is_growing", trend == "growing"))
                growth_value = item.get("growth_pct")
                growth_pct = (
                    _round_optional(_to_float(growth_value))
                    if growth_value is not None
                    else None
                )
                reason = str(item.get("reason") or "LLM trend analysis.").strip()
                out[name] = TrendInsight(
                    trend=trend,
                    is_growing=is_growing,
                    growth_pct=growth_pct,
                    reason=reason,
                )
            return out

        return {
            "compartments": normalize("compartments"),
            "services": normalize("services"),
        }

    def generate_report(
        self,
        *,
        reference_month: Optional[str] = None,
        query_type: str = "COST",
        top_n: int = 10,
        config_profile: Optional[str] = "DEFAULT",
        auth_type: Optional[str] = None,
    ) -> str:
        """Generate trend report on six full months prior to reference month."""
        if top_n < 1:
            raise ValueError("top_n must be >= 1.")

        if reference_month:
            reference = _format_month(*_parse_month_year(reference_month))
        else:
            today = date.today()
            reference = _format_month(today.year, today.month)

        months = _previous_full_months(reference, count=6)
        compartment_maps: List[Dict[str, float]] = []
        service_maps: List[Dict[str, float]] = []

        for month in months:
            start_day, end_day = _month_window(month)
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
            compartment_maps.append(
                _extract_amounts(
                    by_compartment.get("items", []),
                    label_keys=["compartmentName", "compartment_name"],
                )
            )
            service_maps.append(
                _extract_amounts(
                    by_service.get("items", []),
                    label_keys=["service", "serviceName", "service_name"],
                )
            )

        top_compartments = _select_top_series(compartment_maps, top_n=top_n)
        top_services = _select_top_series(service_maps, top_n=top_n)
        llm_insights = self._analyze_with_llm(
            months=months,
            compartment_series=top_compartments,
            service_series=top_services,
        )

        compartment_rows: List[Tuple[int, TrendSeries, TrendInsight]] = []
        for rank, series in enumerate(top_compartments, start=1):
            insight = llm_insights.get("compartments", {}).get(series.label)
            compartment_rows.append(
                (rank, series, insight or _fallback_insight(series.monthly_values))
            )

        service_rows: List[Tuple[int, TrendSeries, TrendInsight]] = []
        for rank, series in enumerate(top_services, start=1):
            insight = llm_insights.get("services", {}).get(series.label)
            service_rows.append(
                (rank, series, insight or _fallback_insight(series.monthly_values))
            )

        report_lines: List[str] = []
        report_lines.append("# OCI Consumption Trend Report (Last 6 Full Months)")
        report_lines.append("")
        report_lines.append(f"- Reference month (execution moment): `{reference}`")
        report_lines.append(
            f"- Analyzed months: `{months[0]}` to `{months[-1]}` "
            "(6 full months before reference month)"
        )
        report_lines.append(f"- Query type: `{query_type}`")
        report_lines.append(f"- Top N: `{top_n}`")
        report_lines.append("")
        report_lines.extend(
            _render_trend_section(
                f"Top {top_n} Compartments - Trend Analysis",
                months,
                compartment_rows,
            )
        )
        report_lines.extend(
            _render_trend_section(
                f"Top {top_n} Services - Trend Analysis",
                months,
                service_rows,
            )
        )
        return "\n".join(report_lines).strip() + "\n"


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for trend report generation."""
    parser = argparse.ArgumentParser(
        description="Generate OCI six-month trend report by compartment and service."
    )
    parser.add_argument(
        "--reference-month",
        default=None,
        help="Reference month in format YYYY-MM or MM-YYYY (default: current month).",
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
    add_report_output_arguments(parser)
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = _parse_args()
    if args.top_n < 1:
        print("ERROR: --top-n must be >= 1")
        return 1
    try:
        agent = BatchTrendReportAgent()
        report = agent.generate_report(
            reference_month=args.reference_month,
            query_type=args.query_type,
            top_n=args.top_n,
            config_profile=args.profile,
            auth_type=args.auth_type,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"ERROR: {exc}")
        return 1

    if args.reference_month:
        reference = _format_month(*_parse_month_year(args.reference_month))
    else:
        today = date.today()
        reference = _format_month(today.year, today.month)
    default_filename = _default_trend_filename(reference)

    saved = save_report_from_args(report, args, default_filename=default_filename)
    if saved is None:
        print(report, end="")
        return 0

    print(f"Report saved to {saved.location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
