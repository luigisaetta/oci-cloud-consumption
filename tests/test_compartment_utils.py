"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Unit tests for reusable compartment owner tag helpers.
"""

from types import SimpleNamespace

import pytest

from common import compartment_utils


def test_get_compartment_owner_normalizes_oracle_identity_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compartment_utils,
        "make_oci_client",
        lambda **_kwargs: (
            object(),
            {"tenancy": "ocid1.tenancy.oc1..t", "region": "eu-milan-1"},
        ),
    )
    monkeypatch.setattr(
        compartment_utils,
        "make_identity_client",
        lambda *_args, **_kwargs: SimpleNamespace(
            get_compartment=lambda _compartment_id: SimpleNamespace(
                data=SimpleNamespace(
                    defined_tags={
                        "OracleMandatory": {
                            "CreatedBy": (
                                "oracleidentitycloudservice/" "luigi.saetta@oracle.com"
                            )
                        }
                    }
                )
            )
        ),
    )
    monkeypatch.setattr(
        compartment_utils,
        "resolve_compartment_id",
        lambda *_args, **_kwargs: "ocid1.compartment.oc1..resolved",
    )

    value = compartment_utils.get_compartment_owner("Finance")
    assert value == "luigi.saetta"


def test_get_compartment_owner_returns_not_found_when_tag_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compartment_utils,
        "make_oci_client",
        lambda **_kwargs: (
            object(),
            {"tenancy": "ocid1.tenancy.oc1..t", "region": "eu-milan-1"},
        ),
    )
    monkeypatch.setattr(
        compartment_utils,
        "make_identity_client",
        lambda *_args, **_kwargs: SimpleNamespace(
            get_compartment=lambda _compartment_id: SimpleNamespace(
                data=SimpleNamespace(defined_tags={})
            )
        ),
    )
    monkeypatch.setattr(
        compartment_utils,
        "resolve_compartment_id",
        lambda *_args, **_kwargs: "ocid1.compartment.oc1..resolved",
    )

    value = compartment_utils.get_compartment_owner("Finance")
    assert value == "not_found"


def test_get_compartment_owner_returns_not_found_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compartment_utils,
        "make_oci_client",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    value = compartment_utils.get_compartment_owner("Finance")
    assert value == "not_found"
