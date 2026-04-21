"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Utility functions to retrieve and aggregate OCI tenant consumption and usage data.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from oci.usage_api import UsageapiClient
from oci.usage_api.models import Dimension, Filter, RequestSummarizedUsagesDetails

from utils import get_console_logger
from utils.oci_utils import (
    extract_group_value,
    get_opc_request_id,
    make_identity_client,
    make_oci_client,
    resolve_compartment_id,
    resolve_service,
)

logger = get_console_logger()

MAX_COMPARTMENT_DEPTH = 7
VALID_QUERY_TYPES = ("COST", "USAGE")


def _normalize_query_type(query_type: str) -> str:
    """Return a validated and normalized OCI usage query type.

    Args:
        query_type: Requested query type, expected to be `"COST"` or `"USAGE"`.

    Returns:
        Uppercase query type.

    Raises:
        ValueError: If the input is not one of the supported values.
    """
    qt = (query_type or "").strip().upper()
    if qt not in VALID_QUERY_TYPES:
        raise ValueError("query_type must be 'COST' or 'USAGE'")
    return qt


def _to_date(value: date | datetime | str) -> date:
    """Convert an input date-like value into a `date` object.

    Args:
        value: ISO date string (`YYYY-MM-DD`), `date`, or `datetime`.

    Returns:
        Normalized `date` value.

    Raises:
        TypeError: If the type is unsupported.
        ValueError: If the string is not a valid ISO date.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError("Date value must be date, datetime, or ISO date string")


def _to_utc_midnight(value: date | datetime | str) -> str:
    """Convert a date-like input to RFC3339 UTC midnight (`...T00:00:00Z`).

    Args:
        value: ISO date string, `date`, or `datetime`.

    Returns:
        RFC3339 timestamp in UTC at midnight.
    """
    d = _to_date(value)
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _window_start_end_exclusive(
    start_day: date | datetime | str,
    end_day_inclusive: date | datetime | str,
) -> Tuple[str, str]:
    """Build an OCI Usage API time window with an exclusive end bound.

    OCI Usage API expects end timestamps as exclusive bounds. This helper converts
    an inclusive end day into the next UTC midnight.

    Args:
        start_day: Start day (inclusive).
        end_day_inclusive: End day (inclusive).

    Returns:
        Tuple `(start_inclusive, end_exclusive)` as RFC3339 strings.

    Raises:
        ValueError: If start day is after end day.
    """
    start_date = _to_date(start_day)
    end_date = _to_date(end_day_inclusive)
    if start_date > end_date:
        raise ValueError("start_day must be <= end_day_inclusive")

    start = _to_utc_midnight(start_date)
    end_exclusive = _to_utc_midnight(end_date + timedelta(days=1))
    return start, end_exclusive


def _round_or_none(value: Any, ndigits: int = 2) -> Optional[float]:
    """Round numeric values while preserving `None`.

    Args:
        value: Input numeric value.
        ndigits: Decimal places.

    Returns:
        Rounded float, or `None` if input is `None`.
    """
    return round(float(value), ndigits) if value is not None else None


def _effective_depth(include_sub: bool, max_depth: int) -> int:
    """Calculate effective compartment depth within OCI-supported limits.

    Args:
        include_sub: Whether to include sub-compartments.
        max_depth: Requested max depth.

    Returns:
        Depth value in `[1, MAX_COMPARTMENT_DEPTH]`.
    """
    if not include_sub:
        return 1
    return max(1, min(int(max_depth), MAX_COMPARTMENT_DEPTH))


def _build_usage_summary_output(
    *,
    start: str,
    end_exclusive: str,
    query_type: str,
    group_by: List[str],
    response: Any,
    region: Optional[str],
) -> Dict[str, Any]:
    """Aggregate OCI summarized usage response into a stable structured output.

    Args:
        start: Start timestamp (inclusive).
        end_exclusive: End timestamp (exclusive).
        query_type: `COST` or `USAGE`.
        group_by: Grouping keys used by the API request.
        response: OCI SDK response object.
        region: OCI region.

    Returns:
        Structured summary payload with period, items, totals, and metadata.
    """
    items_raw = getattr(response.data, "items", []) or []

    buckets: Dict[tuple, Dict[str, Any]] = {}
    total_amount = 0.0
    total_qty = 0.0

    for item in items_raw:
        key_values = tuple(extract_group_value(item, key) for key in group_by)
        amount = float(getattr(item, "computed_amount", 0.0) or 0.0)
        quantity = float(getattr(item, "computed_quantity", 0.0) or 0.0)

        if key_values not in buckets:
            buckets[key_values] = {
                "group": {k: v for k, v in zip(group_by, key_values)},
                "amount": 0.0,
                "quantity": 0.0,
            }

        buckets[key_values]["amount"] += amount
        buckets[key_values]["quantity"] += quantity
        total_amount += amount
        total_qty += quantity

    items: List[Dict[str, Any]] = []
    for agg in buckets.values():
        row: Dict[str, Any] = {k: v for k, v in agg["group"].items()}
        if len(group_by) == 1 and group_by[0] in ("service", "serviceName"):
            row.setdefault("service", row.get(group_by[0]))
        row["amount"] = _round_or_none(agg["amount"])
        row["quantity"] = _round_or_none(agg["quantity"])
        items.append(row)

    return {
        "period": {
            "start_inclusive": start,
            "end_exclusive": end_exclusive,
            "query_type": query_type,
            "aggregated_over_time": True,
        },
        "group_by": group_by,
        "items": items,
        "totals": {
            "amount": _round_or_none(total_amount),
            "quantity": _round_or_none(total_qty),
        },
        "metadata": {
            "region": region,
            "opc_request_id": get_opc_request_id(response),
        },
    }


def usage_summary_by_service_structured(
    start_day: date | datetime | str,
    end_day_inclusive: date | datetime | str,
    query_type: str = "COST",
) -> Dict[str, Any]:
    """Return tenant-wide OCI usage summary grouped by service.

    Args:
        start_day: Start day (inclusive).
        end_day_inclusive: End day (inclusive).
        query_type: `COST` or `USAGE`.

    Returns:
        Structured summary with one entry per service.
    """
    qt = _normalize_query_type(query_type)
    start, end_exclusive = _window_start_end_exclusive(start_day, end_day_inclusive)

    usage_client, config = make_oci_client("DEFAULT")
    details = RequestSummarizedUsagesDetails(
        tenant_id=config["tenancy"],
        time_usage_started=start,
        time_usage_ended=end_exclusive,
        granularity=RequestSummarizedUsagesDetails.GRANULARITY_DAILY,
        query_type=qt,
        group_by=["service"],
        is_aggregate_by_time=False,
    )
    response = usage_client.request_summarized_usages(details)

    return _build_usage_summary_output(
        start=start,
        end_exclusive=end_exclusive,
        query_type=qt,
        group_by=["service"],
        response=response,
        region=config.get("region"),
    )


def usage_summary_by_compartment_structured(
    start_day: date | datetime | str,
    end_day_inclusive: date | datetime | str,
    query_type: str = "COST",
) -> Dict[str, Any]:
    """Return tenant-wide OCI usage summary grouped by compartment name.

    Args:
        start_day: Start day (inclusive).
        end_day_inclusive: End day (inclusive).
        query_type: `COST` or `USAGE`.

    Returns:
        Structured summary with one entry per compartment.
    """
    qt = _normalize_query_type(query_type)
    start, end_exclusive = _window_start_end_exclusive(start_day, end_day_inclusive)

    usage_client, config = make_oci_client("DEFAULT")
    details = RequestSummarizedUsagesDetails(
        tenant_id=config["tenancy"],
        time_usage_started=start,
        time_usage_ended=end_exclusive,
        granularity=RequestSummarizedUsagesDetails.GRANULARITY_DAILY,
        query_type=qt,
        group_by=["compartmentName"],
        is_aggregate_by_time=False,
        compartment_depth=1,
    )
    response = usage_client.request_summarized_usages(details)

    return _build_usage_summary_output(
        start=start,
        end_exclusive=end_exclusive,
        query_type=qt,
        group_by=["compartmentName"],
        response=response,
        region=config.get("region"),
    )


def _grouped_query(
    client: UsageapiClient,
    tenant_id: str,
    t_start: str,
    t_end_excl: str,
    depth: int,
    query_type: str,
    usage_filter: Optional[Filter],
) -> List[Any]:
    """Execute grouped OCI summarized usage query by compartment and service.

    Args:
        client: OCI usage API client.
        tenant_id: Tenancy OCID.
        t_start: Start timestamp (inclusive).
        t_end_excl: End timestamp (exclusive).
        depth: Compartment traversal depth.
        query_type: `COST` or `USAGE`.
        usage_filter: Optional OCI filter.

    Returns:
        List of OCI result items.
    """
    details = RequestSummarizedUsagesDetails(
        tenant_id=tenant_id,
        granularity=RequestSummarizedUsagesDetails.GRANULARITY_DAILY,
        query_type=query_type,
        is_aggregate_by_time=True,
        time_usage_started=t_start,
        time_usage_ended=t_end_excl,
        filter=usage_filter,
        group_by=["compartmentPath", "compartmentName", "compartmentId", "service"],
        compartment_depth=depth,
    )
    response = client.request_summarized_usages(details)
    return getattr(response.data, "items", []) or []


def _discover_services_union(
    client: UsageapiClient,
    tenant_id: str,
    t_start: str,
    t_end_excl: str,
    depth: int,
) -> List[str]:
    """Discover union of service labels across COST and USAGE queries.

    Args:
        client: OCI usage API client.
        tenant_id: Tenancy OCID.
        t_start: Start timestamp (inclusive).
        t_end_excl: End timestamp (exclusive).
        depth: Compartment traversal depth.

    Returns:
        Sorted unique service labels.
    """
    services = set()
    for query_type in VALID_QUERY_TYPES:
        items = _grouped_query(
            client, tenant_id, t_start, t_end_excl, depth, query_type, None
        )
        for item in items:
            service = getattr(item, "service", None)
            if service:
                services.add(service)
    return sorted(services)


def _transform_grouped_rows(items: List[Any], query_type: str) -> List[Dict[str, Any]]:
    """Transform raw OCI grouped rows into stable API output rows.

    Args:
        items: Raw OCI grouped query result items.
        query_type: `COST` or `USAGE`.

    Returns:
        Sorted list of row dictionaries.
    """
    rows: List[Dict[str, Any]] = []

    for item in items:
        row: Dict[str, Any] = {
            "compartment_path": getattr(item, "compartment_path", None),
            "compartment_name": getattr(item, "compartment_name", None),
            "service": getattr(item, "service", None),
        }
        if query_type == "COST":
            row.update(
                {
                    "computed_amount": round(
                        float(getattr(item, "computed_amount", 0.0) or 0.0), 2
                    ),
                    "currency": getattr(item, "currency", None),
                }
            )
        else:
            row.update(
                {
                    "computed_quantity": float(
                        getattr(item, "computed_quantity", 0.0) or 0.0
                    ),
                    "unit": getattr(item, "unit", None),
                }
            )
        rows.append(row)

    sort_key = "computed_amount" if query_type == "COST" else "computed_quantity"
    rows.sort(key=lambda row: row.get(sort_key, 0.0) or 0.0, reverse=True)
    return rows


def _filter_rows_by_service(
    rows: List[Dict[str, Any]], service: str
) -> List[Dict[str, Any]]:
    """Filter result rows by service name using exact then substring matching.

    Args:
        rows: Candidate rows.
        service: Service value to match.

    Returns:
        Filtered rows.
    """
    service_cf = service.casefold()
    exact = [row for row in rows if row.get("service", "").casefold() == service_cf]
    if exact:
        return exact
    return [row for row in rows if service_cf in row.get("service", "").casefold()]


def _build_debug_payload(
    *,
    rows: List[Dict[str, Any]],
    resolved_service: Optional[str],
    service_candidates: List[str],
    query_used: str,
    filtered_server_side: bool,
    depth: int,
    t_start: str,
    t_end_excl: str,
    service_input: str,
    query_type_requested: str,
    include_subcompartments: bool,
    max_compartment_depth: int,
    config_profile: Optional[str],
    debug: bool,
) -> Dict[str, Any]:
    """Build final output and optionally enrich it with debug metadata.

    Args:
        rows: Result rows.
        resolved_service: Resolved canonical service name, if any.
        service_candidates: Discovered candidate services.
        query_used: Query type used to fetch rows.
        filtered_server_side: Whether filtering happened server side.
        depth: Effective compartment depth.
        t_start: Start timestamp (inclusive).
        t_end_excl: End timestamp (exclusive).
        service_input: Original requested service value.
        query_type_requested: Original requested query type.
        include_subcompartments: Caller preference.
        max_compartment_depth: Caller max depth input.
        config_profile: OCI config profile used by caller.
        debug: If true include debug details.

    Returns:
        Output payload.
    """
    result: Dict[str, Any] = {"rows": rows}
    if not debug:
        return result

    result.update(
        {
            "resolved_service": resolved_service,
            "service_candidates": service_candidates[:50],
            "query_used": query_used,
            "filtered_server_side": filtered_server_side,
            "depth": depth,
            "time_window": {"start": t_start, "end_exclusive": t_end_excl},
            "input": {
                "service": service_input,
                "query_type_requested": query_type_requested,
                "include_subcompartments": include_subcompartments,
                "max_compartment_depth": max_compartment_depth,
                "config_profile": config_profile,
            },
        }
    )
    return result


def fetch_consumption_by_compartment(
    day_start: date | datetime | str,
    day_end: date | datetime | str,
    service: str,
    *,
    query_type: str = "COST",
    include_subcompartments: bool = True,
    max_compartment_depth: int = 7,
    config_profile: Optional[str] = "DEFAULT",
    debug: bool = False,
) -> Dict[str, Any]:
    """Fetch compartment-level usage rows filtered by service.

    The function first tries server-side filtering when a unique service label can
    be resolved from discovered OCI services. If needed, it falls back to client-side
    filtering and can also retry with the alternate query type (`COST`/`USAGE`).

    Args:
        day_start: Start day (inclusive).
        day_end: End day (inclusive).
        service: Service label (exact or partial).
        query_type: Preferred query type, `COST` or `USAGE`.
        include_subcompartments: Whether sub-compartments should be included.
        max_compartment_depth: Max traversal depth from 1 to 7.
        config_profile: OCI profile name or `None` to force resource principals.
        debug: If true returns additional diagnostic metadata.

    Returns:
        Dictionary with `rows` and optional debug fields.

    Raises:
        ValueError: On invalid input values.
        RuntimeError: When tenancy context cannot be resolved.
    """
    if not service or not service.strip():
        raise ValueError("service must be a non-empty string")

    qt = _normalize_query_type(query_type)
    if not 1 <= int(max_compartment_depth) <= MAX_COMPARTMENT_DEPTH:
        raise ValueError(
            f"max_compartment_depth must be between 1 and {MAX_COMPARTMENT_DEPTH}"
        )

    client, cfg = make_oci_client(config_profile)
    tenant_id = cfg.get("tenancy")
    if not tenant_id:
        raise RuntimeError("Cannot determine tenancy OCID (check auth).")

    t_start, t_end_excl = _window_start_end_exclusive(day_start, day_end)
    depth = _effective_depth(include_subcompartments, int(max_compartment_depth))

    candidates = _discover_services_union(client, tenant_id, t_start, t_end_excl, depth)
    resolved_service = resolve_service(service, candidates)
    effective_service_filter = resolved_service or service

    if resolved_service:
        usage_filter = Filter(
            operator="AND",
            dimensions=[Dimension(key="service", value=resolved_service)],
        )
        items = _grouped_query(
            client,
            tenant_id,
            t_start,
            t_end_excl,
            depth,
            qt,
            usage_filter,
        )
        rows = _transform_grouped_rows(items, qt)
        if rows:
            return _build_debug_payload(
                rows=rows,
                resolved_service=resolved_service,
                service_candidates=candidates,
                query_used=qt,
                filtered_server_side=True,
                depth=depth,
                t_start=t_start,
                t_end_excl=t_end_excl,
                service_input=service,
                query_type_requested=qt,
                include_subcompartments=include_subcompartments,
                max_compartment_depth=max_compartment_depth,
                config_profile=config_profile,
                debug=debug,
            )

        alt = "USAGE" if qt == "COST" else "COST"
        items_alt = _grouped_query(
            client,
            tenant_id,
            t_start,
            t_end_excl,
            depth,
            alt,
            usage_filter,
        )
        rows_alt = _transform_grouped_rows(items_alt, alt)
        if rows_alt:
            return _build_debug_payload(
                rows=rows_alt,
                resolved_service=resolved_service,
                service_candidates=candidates,
                query_used=alt,
                filtered_server_side=True,
                depth=depth,
                t_start=t_start,
                t_end_excl=t_end_excl,
                service_input=service,
                query_type_requested=qt,
                include_subcompartments=include_subcompartments,
                max_compartment_depth=max_compartment_depth,
                config_profile=config_profile,
                debug=debug,
            )

    items_all = _grouped_query(client, tenant_id, t_start, t_end_excl, depth, qt, None)
    rows_all = _transform_grouped_rows(items_all, qt)
    subset = _filter_rows_by_service(rows_all, effective_service_filter)
    if subset:
        return _build_debug_payload(
            rows=subset,
            resolved_service=resolved_service,
            service_candidates=candidates,
            query_used=qt,
            filtered_server_side=False,
            depth=depth,
            t_start=t_start,
            t_end_excl=t_end_excl,
            service_input=service,
            query_type_requested=qt,
            include_subcompartments=include_subcompartments,
            max_compartment_depth=max_compartment_depth,
            config_profile=config_profile,
            debug=debug,
        )

    alt = "USAGE" if qt == "COST" else "COST"
    items_all_alt = _grouped_query(
        client,
        tenant_id,
        t_start,
        t_end_excl,
        depth,
        alt,
        None,
    )
    rows_all_alt = _transform_grouped_rows(items_all_alt, alt)
    subset_alt = _filter_rows_by_service(rows_all_alt, effective_service_filter)

    return _build_debug_payload(
        rows=subset_alt,
        resolved_service=resolved_service,
        service_candidates=candidates,
        query_used=alt,
        filtered_server_side=False,
        depth=depth,
        t_start=t_start,
        t_end_excl=t_end_excl,
        service_input=service,
        query_type_requested=qt,
        include_subcompartments=include_subcompartments,
        max_compartment_depth=max_compartment_depth,
        config_profile=config_profile,
        debug=debug,
    )


def usage_summary_by_service_for_compartment(
    start_day: date | datetime | str,
    end_day_inclusive: date | datetime | str,
    compartment: str,
    *,
    query_type: str = "COST",
    include_subcompartments: bool = True,
    max_compartment_depth: int = 7,
    config_profile: Optional[str] = "DEFAULT",
) -> Dict[str, Any]:
    """Return service breakdown for a specific compartment over a time window.

    Args:
        start_day: Start day (inclusive).
        end_day_inclusive: End day (inclusive).
        compartment: Compartment OCID or exact compartment name.
        query_type: `COST` or `USAGE`.
        include_subcompartments: Whether sub-compartments are included.
        max_compartment_depth: Max depth in range 1..7.
        config_profile: OCI profile name or `None` for resource principals.

    Returns:
        Structured service summary scoped to the resolved compartment.

    Raises:
        ValueError: On invalid inputs or unresolved compartment.
        RuntimeError: When tenancy context cannot be resolved.
    """
    qt = _normalize_query_type(query_type)
    if not 1 <= int(max_compartment_depth) <= MAX_COMPARTMENT_DEPTH:
        raise ValueError(
            f"max_compartment_depth must be between 1 and {MAX_COMPARTMENT_DEPTH}"
        )
    if not compartment or not compartment.strip():
        raise ValueError("compartment must be a non-empty string")

    start, end_exclusive = _window_start_end_exclusive(start_day, end_day_inclusive)
    depth = _effective_depth(include_subcompartments, int(max_compartment_depth))

    usage_client, cfg = make_oci_client(config_profile)
    tenancy_id = cfg.get("tenancy")
    if not tenancy_id:
        raise RuntimeError("Cannot determine tenancy OCID (check auth).")

    identity_client = make_identity_client(cfg, tenancy_id)
    compartment_id = resolve_compartment_id(identity_client, tenancy_id, compartment)

    usage_filter = Filter(
        operator="AND",
        dimensions=[Dimension(key="compartmentId", value=compartment_id)],
    )
    details = RequestSummarizedUsagesDetails(
        tenant_id=tenancy_id,
        time_usage_started=start,
        time_usage_ended=end_exclusive,
        granularity=RequestSummarizedUsagesDetails.GRANULARITY_DAILY,
        query_type=qt,
        group_by=["service"],
        is_aggregate_by_time=False,
        filter=usage_filter,
        compartment_depth=depth,
    )

    response = usage_client.request_summarized_usages(details)
    items = getattr(response.data, "items", []) or []

    buckets: Dict[str, Dict[str, Any]] = {}
    total_amount = 0.0
    total_qty = 0.0
    currency_seen = None
    unit_seen = None

    for item in items:
        service = extract_group_value(item, "service") or "UNKNOWN"
        buckets.setdefault(
            service, {"service": service, "amount": 0.0, "quantity": 0.0}
        )

        if qt == "COST":
            value = float(getattr(item, "computed_amount", 0.0) or 0.0)
            buckets[service]["amount"] += value
            total_amount += value
            currency_seen = currency_seen or getattr(item, "currency", None)
        else:
            value = float(getattr(item, "computed_quantity", 0.0) or 0.0)
            buckets[service]["quantity"] += value
            total_qty += value
            unit_seen = unit_seen or getattr(item, "unit", None)

    rows: List[Dict[str, Any]] = []
    denominator = total_amount if qt == "COST" else total_qty
    for service, aggregate in buckets.items():
        base = aggregate["amount"] if qt == "COST" else aggregate["quantity"]
        rows.append(
            {
                "service": service,
                "amount": _round_or_none(aggregate["amount"]) if qt == "COST" else None,
                "quantity": (
                    _round_or_none(aggregate["quantity"]) if qt == "USAGE" else None
                ),
                "currency": currency_seen if qt == "COST" else None,
                "unit": unit_seen if qt == "USAGE" else None,
                "share_pct": _round_or_none(
                    (base / denominator * 100.0) if denominator else 0.0
                ),
            }
        )

    sort_key = "amount" if qt == "COST" else "quantity"
    rows.sort(key=lambda row: (row.get(sort_key) or 0.0), reverse=True)

    return {
        "period": {
            "start_inclusive": start,
            "end_exclusive": end_exclusive,
            "query_type": qt,
            "aggregated_over_time": True,
        },
        "scope": {
            "compartment_input": compartment,
            "resolved_compartment_id": compartment_id,
            "include_subcompartments": include_subcompartments,
            "depth": depth,
        },
        "group_by": ["service"],
        "items": rows,
        "totals": {
            "amount": _round_or_none(total_amount) if qt == "COST" else None,
            "quantity": _round_or_none(total_qty) if qt == "USAGE" else None,
        },
        "metadata": {
            "region": cfg.get("region"),
            "opc_request_id": get_opc_request_id(response),
        },
    }
