"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Unit tests for reusable OCI utility helpers.
"""

from types import SimpleNamespace

import pytest

from utils import oci_utils


def test_resolve_service_exact_case_insensitive() -> None:
    available = ["Compute", "Object Storage"]
    assert oci_utils.resolve_service("compute", available) == "Compute"


def test_resolve_service_unique_substring_match() -> None:
    available = ["Virtual Cloud Network", "Object Storage"]
    assert oci_utils.resolve_service("object", available) == "Object Storage"


def test_resolve_service_ambiguous_returns_none() -> None:
    available = ["Compute", "Compute Management"]
    assert oci_utils.resolve_service("comp", available) is None


def test_get_opc_request_id_present() -> None:
    response = SimpleNamespace(headers={"opc-request-id": "abc-123"})
    assert oci_utils.get_opc_request_id(response) == "abc-123"


def test_get_opc_request_id_missing_headers() -> None:
    response = SimpleNamespace()
    assert oci_utils.get_opc_request_id(response) is None


def test_extract_group_value_from_service_name_alias() -> None:
    item = SimpleNamespace(service_name="Object Storage")
    assert oci_utils.extract_group_value(item, "service") == "Object Storage"


def test_extract_group_value_fallback_direct_attribute() -> None:
    item = SimpleNamespace(region="eu-frankfurt-1")
    assert oci_utils.extract_group_value(item, "region") == "eu-frankfurt-1"


def test_make_oci_client_from_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    def fake_from_file(profile_name: str):
        assert profile_name == "DEFAULT"
        return {"tenancy": "ocid1.tenancy.oc1..aaa", "region": "eu-milan-1"}

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils.oci.config, "from_file", fake_from_file)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)

    client, cfg = oci_utils.make_oci_client("DEFAULT")

    assert isinstance(client, FakeUsageClient)
    assert cfg["region"] == "eu-frankfurt-1"
    assert captured["timeout"] == 60.0
    assert captured["signer"] is None


def test_make_oci_client_from_profile_region_overridden_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_from_file(profile_name: str):
        assert profile_name == "DEFAULT"
        return {"tenancy": "ocid1.tenancy.oc1..aaa", "region": "us-chicago-1"}

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils.oci.config, "from_file", fake_from_file)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    _client, cfg = oci_utils.make_oci_client("DEFAULT")

    assert cfg["region"] == "eu-frankfurt-1"
    assert captured["cfg"]["region"] == "eu-frankfurt-1"


def test_make_oci_client_fallback_to_resource_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.delenv("OCI_AUTH_TYPE", raising=False)
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    def fake_from_file(profile_name: str):
        raise RuntimeError("profile not found")

    class FakeSigner:
        region = "eu-frankfurt-1"
        tenancy_id = "ocid1.tenancy.oc1..rp"

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils.oci.config, "from_file", fake_from_file)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)
    monkeypatch.setattr(
        oci_utils.oci.auth.signers,
        "get_resource_principals_signer",
        lambda: FakeSigner(),
    )

    client, cfg = oci_utils.make_oci_client("DEFAULT", auth_type="AUTO")

    assert isinstance(client, FakeUsageClient)
    assert cfg == {"region": "eu-frankfurt-1", "tenancy": "ocid1.tenancy.oc1..rp"}
    assert captured["timeout"] == 60.0
    assert isinstance(captured["signer"], FakeSigner)


def test_make_oci_client_rp_region_overridden_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.delenv("OCI_AUTH_TYPE", raising=False)

    def fake_from_file(profile_name: str):
        raise RuntimeError("profile not found")

    class FakeSigner:
        region = "us-ashburn-1"
        tenancy_id = "ocid1.tenancy.oc1..rp"

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils.oci.config, "from_file", fake_from_file)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)
    monkeypatch.setattr(
        oci_utils.oci.auth.signers,
        "get_resource_principals_signer",
        lambda: FakeSigner(),
    )
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    _client, cfg = oci_utils.make_oci_client("DEFAULT", auth_type="AUTO")

    assert cfg == {"region": "eu-frankfurt-1", "tenancy": "ocid1.tenancy.oc1..rp"}
    assert captured["cfg"]["region"] == "eu-frankfurt-1"


def test_make_oci_client_api_key_uses_default_profile_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    def fake_from_file(profile_name: str):
        captured["profile_name"] = profile_name
        return {"tenancy": "ocid1.tenancy.oc1..aaa", "region": "eu-milan-1"}

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    monkeypatch.delenv("OCI_CONFIG_PROFILE", raising=False)
    monkeypatch.setattr(oci_utils.oci.config, "from_file", fake_from_file)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)

    _client, cfg = oci_utils.make_oci_client(None, auth_type="API_KEY")

    assert captured["profile_name"] == "DEFAULT"
    assert captured["signer"] is None
    assert cfg["tenancy"] == "ocid1.tenancy.oc1..aaa"
    assert cfg["region"] == "eu-frankfurt-1"


def test_make_oci_client_api_key_raises_without_rp_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")
    monkeypatch.setattr(
        oci_utils.oci.config,
        "from_file",
        lambda profile_name: (_ for _ in ()).throw(RuntimeError("missing profile")),
    )

    with pytest.raises(RuntimeError, match="Could not load OCI profile"):
        oci_utils.make_oci_client("DEFAULT", auth_type="API_KEY")


def test_make_oci_client_resource_principal_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.delenv("OCI_AUTH_TYPE", raising=False)
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")

    class FakeSigner:
        region = "us-ashburn-1"
        tenancy_id = "ocid1.tenancy.oc1..rp"

    class FakeUsageClient:
        def __init__(self, cfg, timeout=None, signer=None):
            captured["cfg"] = cfg
            captured["timeout"] = timeout
            captured["signer"] = signer

    def fail_if_called(_profile_name: str):
        raise AssertionError("from_file should not be called for forced RP auth")

    monkeypatch.setattr(oci_utils.oci.config, "from_file", fail_if_called)
    monkeypatch.setattr(oci_utils, "UsageapiClient", FakeUsageClient)
    monkeypatch.setattr(
        oci_utils.oci.auth.signers,
        "get_resource_principals_signer",
        lambda: FakeSigner(),
    )

    _client, cfg = oci_utils.make_oci_client("DEFAULT", auth_type="RESOURCE_PRINCIPAL")

    assert cfg == {"region": "eu-frankfurt-1", "tenancy": "ocid1.tenancy.oc1..rp"}
    assert isinstance(captured["signer"], FakeSigner)


def test_make_oci_client_requires_region_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OCI_REGION", raising=False)

    with pytest.raises(RuntimeError, match="OCI_REGION must be set"):
        oci_utils.make_oci_client("DEFAULT", auth_type="API_KEY")


def test_make_oci_config_returns_shared_profile_config_and_signer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")
    monkeypatch.setattr(
        oci_utils.oci.config,
        "from_file",
        lambda profile_name: {"tenancy": "tenancy", "region": "profile-region"},
    )

    cfg, signer = oci_utils.make_oci_config("DEFAULT", auth_type="API_KEY")

    assert cfg == {"tenancy": "tenancy", "region": "eu-frankfurt-1"}
    assert signer is None


def test_make_identity_client_with_user_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeIdentityClient:
        def __init__(self, cfg, signer=None):
            captured["cfg"] = cfg
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils, "IdentityClient", FakeIdentityClient)

    cfg = {"user": "ocid1.user.oc1..u", "region": "eu-milan-1"}
    client = oci_utils.make_identity_client(cfg, "ocid1.tenancy.oc1..t")

    assert isinstance(client, FakeIdentityClient)
    assert captured["cfg"] is cfg
    assert captured["signer"] is None


def test_make_identity_client_with_resource_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeSigner:
        pass

    class FakeIdentityClient:
        def __init__(self, cfg, signer=None):
            captured["cfg"] = cfg
            captured["signer"] = signer

    monkeypatch.setattr(oci_utils, "IdentityClient", FakeIdentityClient)
    monkeypatch.setattr(
        oci_utils.oci.auth.signers,
        "get_resource_principals_signer",
        lambda: FakeSigner(),
    )

    client = oci_utils.make_identity_client(
        {"region": "eu-milan-1"},
        "ocid1.tenancy.oc1..ten",
    )

    assert isinstance(client, FakeIdentityClient)
    assert captured["cfg"] == {
        "region": "eu-milan-1",
        "tenancy": "ocid1.tenancy.oc1..ten",
    }
    assert isinstance(captured["signer"], FakeSigner)


def test_resolve_compartment_id_returns_input_ocid() -> None:
    fake_identity = SimpleNamespace()
    ocid = "ocid1.compartment.oc1..abc"
    assert oci_utils.resolve_compartment_id(fake_identity, "ignored", ocid) == ocid


def test_resolve_compartment_id_matches_root_tenancy_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_identity = SimpleNamespace(
        get_tenancy=lambda tenancy_id: SimpleNamespace(
            data=SimpleNamespace(name="ROOT_TENANCY")
        )
    )

    result = oci_utils.resolve_compartment_id(
        fake_identity,
        "ocid1.tenancy.oc1..root",
        "ROOT_TENANCY",
    )
    assert result == "ocid1.tenancy.oc1..root"


def test_resolve_compartment_id_from_unique_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_identity = SimpleNamespace(
        get_tenancy=lambda tenancy_id: SimpleNamespace(
            data=SimpleNamespace(name="ROOT")
        ),
        list_compartments=lambda *_args, **_kwargs: None,
    )

    fake_page = SimpleNamespace(
        data=[
            SimpleNamespace(name="Finance", id="ocid1.compartment.oc1..fin"),
            SimpleNamespace(name="Dev", id="ocid1.compartment.oc1..dev"),
        ]
    )
    monkeypatch.setattr(
        oci_utils.oci.pagination,
        "list_call_get_all_results",
        lambda *args, **kwargs: fake_page,
    )

    result = oci_utils.resolve_compartment_id(
        fake_identity,
        "ocid1.tenancy.oc1..root",
        "Finance",
    )
    assert result == "ocid1.compartment.oc1..fin"


def test_resolve_compartment_id_raises_on_ambiguous_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_identity = SimpleNamespace(
        get_tenancy=lambda tenancy_id: SimpleNamespace(
            data=SimpleNamespace(name="ROOT")
        ),
        list_compartments=lambda *_args, **_kwargs: None,
    )

    fake_page = SimpleNamespace(
        data=[
            SimpleNamespace(name="Shared", id="ocid1.compartment.oc1..a"),
            SimpleNamespace(name="Shared", id="ocid1.compartment.oc1..b"),
        ]
    )
    monkeypatch.setattr(
        oci_utils.oci.pagination,
        "list_call_get_all_results",
        lambda *args, **kwargs: fake_page,
    )

    with pytest.raises(ValueError, match="Multiple compartments named"):
        oci_utils.resolve_compartment_id(
            fake_identity,
            "ocid1.tenancy.oc1..root",
            "Shared",
        )


def test_resolve_compartment_id_raises_on_missing_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_identity = SimpleNamespace(
        get_tenancy=lambda tenancy_id: SimpleNamespace(
            data=SimpleNamespace(name="ROOT")
        ),
        list_compartments=lambda *_args, **_kwargs: None,
    )

    fake_page = SimpleNamespace(
        data=[SimpleNamespace(name="Dev", id="ocid1.compartment.oc1..dev")]
    )
    monkeypatch.setattr(
        oci_utils.oci.pagination,
        "list_call_get_all_results",
        lambda *args, **kwargs: fake_page,
    )

    with pytest.raises(ValueError, match="not found"):
        oci_utils.resolve_compartment_id(
            fake_identity,
            "ocid1.tenancy.oc1..root",
            "Finance",
        )
