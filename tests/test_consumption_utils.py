"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Unit tests for OCI consumption aggregation utilities.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from utils import consumption_utils


def test_normalize_query_type_accepts_valid_values() -> None:
    assert consumption_utils._normalize_query_type("cost") == "COST"
    assert consumption_utils._normalize_query_type("USAGE") == "USAGE"


def test_normalize_query_type_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="query_type must be 'COST' or 'USAGE'"):
        consumption_utils._normalize_query_type("INVALID")


def test_to_date_supports_str_date_datetime() -> None:
    assert consumption_utils._to_date("2026-01-10") == date(2026, 1, 10)
    assert consumption_utils._to_date(date(2026, 1, 11)) == date(2026, 1, 11)
    assert consumption_utils._to_date(datetime(2026, 1, 12, 12, 0, 0)) == date(
        2026,
        1,
        12,
    )


def test_window_start_end_exclusive() -> None:
    start, end_exclusive = consumption_utils._window_start_end_exclusive(
        "2026-01-01",
        "2026-01-03",
    )
    assert start == "2026-01-01T00:00:00Z"
    assert end_exclusive == "2026-01-04T00:00:00Z"


def test_window_start_end_exclusive_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="start_day must be <= end_day_inclusive"):
        consumption_utils._window_start_end_exclusive("2026-01-05", "2026-01-01")


def test_build_usage_summary_output_aggregates_items() -> None:
    response = SimpleNamespace(
        data=SimpleNamespace(
            items=[
                SimpleNamespace(
                    service="Compute",
                    computed_amount=10.0,
                    computed_quantity=2.0,
                ),
                SimpleNamespace(
                    service="Compute",
                    computed_amount=5.5,
                    computed_quantity=1.0,
                ),
                SimpleNamespace(
                    service="Object Storage",
                    computed_amount=3.0,
                    computed_quantity=4.0,
                ),
            ]
        ),
        headers={"opc-request-id": "req-1"},
    )

    output = consumption_utils._build_usage_summary_output(
        start="2026-01-01T00:00:00Z",
        end_exclusive="2026-01-02T00:00:00Z",
        query_type="COST",
        group_by=["service"],
        response=response,
        region="eu-milan-1",
    )

    assert output["totals"]["amount"] == 18.5
    assert output["totals"]["quantity"] == 7.0
    assert output["metadata"]["opc_request_id"] == "req-1"
    services = {item["service"]: item for item in output["items"]}
    assert services["Compute"]["amount"] == 15.5
    assert services["Object Storage"]["amount"] == 3.0


def test_get_usage_summary_by_service(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = SimpleNamespace(
        data=SimpleNamespace(
            items=[
                SimpleNamespace(
                    service="Compute",
                    computed_amount=20.0,
                    computed_quantity=1.0,
                )
            ]
        ),
        headers={"opc-request-id": "req-service"},
    )

    class FakeUsageClient:
        def request_summarized_usages(self, _details):
            return fake_response

    monkeypatch.setattr(
        consumption_utils,
        "make_oci_client",
        lambda _profile: (
            FakeUsageClient(),
            {"tenancy": "ocid1.tenancy.oc1..x", "region": "eu-milan-1"},
        ),
    )

    result = consumption_utils.get_usage_summary_by_service(
        "2026-01-01",
        "2026-01-01",
        query_type="cost",
    )

    assert result["group_by"] == ["service"]
    assert result["totals"]["amount"] == 20.0
    assert result["metadata"]["region"] == "eu-milan-1"


def test_fetch_consumption_by_compartment_rejects_empty_service() -> None:
    with pytest.raises(ValueError, match="service must be a non-empty string"):
        consumption_utils.fetch_consumption_by_compartment(
            "2026-01-01",
            "2026-01-01",
            "  ",
        )


def test_fetch_consumption_by_compartment_server_side_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        consumption_utils,
        "make_oci_client",
        lambda _profile: (
            object(),
            {"tenancy": "ocid1.tenancy.oc1..t", "region": "eu-milan-1"},
        ),
    )
    monkeypatch.setattr(
        consumption_utils,
        "_discover_services_union",
        lambda *_args, **_kwargs: ["Compute"],
    )
    monkeypatch.setattr(consumption_utils, "resolve_service", lambda *_args: "Compute")
    monkeypatch.setattr(
        consumption_utils,
        "_grouped_query",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                compartment_path="/root/dev",
                compartment_name="dev",
                service="Compute",
                computed_amount=12.2,
                currency="USD",
            )
        ],
    )

    result = consumption_utils.fetch_consumption_by_compartment(
        "2026-01-01",
        "2026-01-01",
        "compute",
        query_type="COST",
        debug=True,
    )

    assert result["rows"]
    assert result["filtered_server_side"] is True
    assert result["query_used"] == "COST"


def test_usage_summary_by_service_for_compartment_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="compartment must be a non-empty string"):
        consumption_utils.usage_summary_by_service_for_compartment(
            "2026-01-01",
            "2026-01-01",
            "",
        )


def test_usage_summary_by_service_for_compartment_cost_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_response = SimpleNamespace(
        data=SimpleNamespace(
            items=[
                SimpleNamespace(
                    service="Compute",
                    computed_amount=40.0,
                    computed_quantity=0.0,
                    currency="USD",
                ),
                SimpleNamespace(
                    service="Object Storage",
                    computed_amount=10.0,
                    computed_quantity=0.0,
                    currency="USD",
                ),
            ]
        ),
        headers={"opc-request-id": "req-compartment"},
    )

    class FakeUsageClient:
        def request_summarized_usages(self, _details):
            return fake_response

    monkeypatch.setattr(
        consumption_utils,
        "make_oci_client",
        lambda _profile: (
            FakeUsageClient(),
            {"tenancy": "ocid1.tenancy.oc1..t", "region": "eu-milan-1"},
        ),
    )
    monkeypatch.setattr(
        consumption_utils, "make_identity_client", lambda *_args: object()
    )
    monkeypatch.setattr(
        consumption_utils,
        "resolve_compartment_id",
        lambda *_args: "ocid1.compartment.oc1..resolved",
    )

    result = consumption_utils.usage_summary_by_service_for_compartment(
        "2026-01-01",
        "2026-01-01",
        "Finance",
        query_type="COST",
    )

    assert (
        result["scope"]["resolved_compartment_id"] == "ocid1.compartment.oc1..resolved"
    )
    assert result["totals"]["amount"] == 50.0
    assert result["items"][0]["service"] == "Compute"
    assert result["items"][0]["share_pct"] == 80.0
