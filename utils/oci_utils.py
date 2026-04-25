"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Reusable OCI helper functions for auth, identity, and response normalization.
"""

# pylint: disable=broad-exception-caught

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import oci
from dotenv import load_dotenv
from oci.identity import IdentityClient
from oci.usage_api import UsageapiClient

from utils import get_console_logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

logger = get_console_logger()

VALID_AUTH_TYPES = ("AUTO", "API_KEY", "RESOURCE_PRINCIPAL")


def _normalize_auth_type(auth_type: Optional[str]) -> str:
    """Normalize and validate OCI authentication strategy.

    Accepted values are `AUTO`, `API_KEY`/`USER_PRINCIPAL`,
    and `RESOURCE_PRINCIPAL`.
    """
    raw_value = auth_type
    if raw_value is None:
        raw_value = os.getenv("OCI_AUTH_TYPE", "AUTO")

    normalized = (raw_value or "AUTO").strip().upper().replace("-", "_")
    if normalized == "USER_PRINCIPAL":
        normalized = "API_KEY"

    if normalized not in VALID_AUTH_TYPES:
        raise ValueError(
            "auth_type must be one of AUTO, API_KEY (or USER_PRINCIPAL), "
            "RESOURCE_PRINCIPAL"
        )
    return normalized


def _resolve_profile_name(config_profile: Optional[str]) -> str:
    """Resolve OCI profile name from explicit value, env var, or default."""
    explicit = (config_profile or "").strip()
    if explicit:
        return explicit

    env_profile = (os.getenv("OCI_CONFIG_PROFILE") or "").strip()
    if env_profile:
        return env_profile

    return "DEFAULT"


def _resolve_oci_region() -> str:
    """Resolve OCI region exclusively from `.env`/environment configuration."""
    env_region = (os.getenv("OCI_REGION") or "").strip()
    if not env_region:
        raise RuntimeError(
            "OCI_REGION must be set in .env or the process environment. "
            "The region is not read from the OCI profile."
        )
    return env_region


def make_oci_config(
    config_profile: Optional[str],
    *,
    auth_type: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    """Create shared OCI config and optional signer for SDK clients.

    The OCI region is always taken from `OCI_REGION`, loaded from `.env` when
    available. Profile files are used only for API key credentials and tenancy.
    """
    strategy = _normalize_auth_type(auth_type)
    env_region = _resolve_oci_region()

    if strategy == "RESOURCE_PRINCIPAL":
        logger.info("Using RESOURCE_PRINCIPAL authentication")
        signer = oci.auth.signers.get_resource_principals_signer()
        cfg = {"region": env_region, "tenancy": signer.tenancy_id}
        return cfg, signer

    profile_name = _resolve_profile_name(config_profile)

    try:
        cfg = oci.config.from_file(profile_name=profile_name)
        cfg["region"] = env_region
        return cfg, None
    except (
        Exception
    ) as exc:  # pragma: no cover  # pylint: disable=broad-exception-caught
        if strategy == "API_KEY":
            raise RuntimeError(
                f"Could not load OCI profile '{profile_name}' for API_KEY auth: {exc}"
            ) from exc

        logger.warning(
            "Could not load OCI profile '%s', falling back to resource principals: %s",
            profile_name,
            exc,
        )
        logger.info("Using RESOURCE_PRINCIPAL authentication")
        signer = oci.auth.signers.get_resource_principals_signer()
        cfg = {"region": env_region, "tenancy": signer.tenancy_id}
        return cfg, signer


def _build_resource_principal_client() -> Tuple[UsageapiClient, Dict[str, Any]]:
    """Create Usage API client with resource principal authentication."""
    logger.info("Using RESOURCE_PRINCIPAL authentication")
    signer = oci.auth.signers.get_resource_principals_signer()
    cfg = {"region": _resolve_oci_region(), "tenancy": signer.tenancy_id}
    return UsageapiClient(cfg, signer=signer, timeout=60.0), cfg


def make_oci_client(
    config_profile: Optional[str],
    *,
    auth_type: Optional[str] = None,
) -> Tuple[UsageapiClient, Dict[str, Any]]:
    """Create an OCI Usage API client using profile config or resource principals.

    Args:
        config_profile: OCI profile name.
        auth_type: Authentication strategy. Supported values:
            `AUTO`, `API_KEY`/`USER_PRINCIPAL`, `RESOURCE_PRINCIPAL`.

    Returns:
        Tuple `(UsageapiClient, config_dict)` where config contains at least
        `region` and `tenancy`.
    """
    cfg, signer = make_oci_config(config_profile, auth_type=auth_type)
    if signer is not None:
        return UsageapiClient(cfg, signer=signer, timeout=60.0), cfg
    return UsageapiClient(cfg, timeout=60.0), cfg


def make_identity_client(cfg: Dict[str, Any], tenancy_id: str) -> IdentityClient:
    """Create OCI Identity client consistent with current authentication mode.

    Args:
        cfg: Configuration dictionary returned by `make_oci_client`.
        tenancy_id: Tenancy OCID.

    Returns:
        Configured `IdentityClient`.
    """
    if "user" in cfg:
        return IdentityClient(cfg)

    signer = oci.auth.signers.get_resource_principals_signer()
    return IdentityClient(
        {"region": cfg["region"], "tenancy": tenancy_id},
        signer=signer,
    )


def resolve_compartment_id(
    id_client: IdentityClient,
    tenancy_id: str,
    compartment: str,
) -> str:
    """Resolve compartment input (OCID or exact name) into a compartment OCID.

    Args:
        id_client: OCI identity client.
        tenancy_id: Tenancy OCID.
        compartment: Compartment OCID or exact compartment name.

    Returns:
        Resolved compartment OCID.

    Raises:
        ValueError: If name is not found or is ambiguous.
    """
    if compartment.startswith("ocid1.compartment."):
        return compartment

    tenancy = id_client.get_tenancy(tenancy_id).data
    if tenancy.name == compartment:
        return tenancy_id

    compartments = oci.pagination.list_call_get_all_results(
        id_client.list_compartments,
        tenancy_id,
        access_level="ACCESSIBLE",
        compartment_id_in_subtree=True,
    ).data

    exact = [item for item in compartments if item.name == compartment]
    if len(exact) == 1:
        return exact[0].id
    if len(exact) > 1:
        raise ValueError(f"Multiple compartments named '{compartment}'. Use OCID.")

    raise ValueError(
        f"Compartment '{compartment}' not found among accessible compartments."
    )


def resolve_service(requested: str, available: List[str]) -> Optional[str]:
    """Resolve a requested service label against discovered OCI service names.

    Args:
        requested: Service filter entered by user.
        available: Available service names from OCI results.

    Returns:
        Exact or unambiguous substring match; otherwise `None`.
    """
    requested_cf = requested.casefold()

    for service in available:
        if service.casefold() == requested_cf:
            return service

    candidates = [
        service for service in available if requested_cf in service.casefold()
    ]
    if len(candidates) == 1:
        return candidates[0]

    return None


def get_opc_request_id(response: Any) -> Optional[str]:
    """Extract `opc-request-id` from an OCI SDK response when available.

    Args:
        response: OCI SDK response object.

    Returns:
        Request id string or `None`.
    """
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    return headers.get("opc-request-id")


def extract_group_value(item: Any, key: str) -> Any:
    """Extract a grouping value from OCI response items by tolerant key mapping.

    Args:
        item: OCI response item.
        key: Group key expected by caller.

    Returns:
        Matched attribute value or `None`.
    """
    mapping = {
        "service": ["service", "service_name"],
        "serviceName": ["service", "service_name"],
        "region": ["region"],
        "compartmentName": ["compartment_name"],
        "resourceId": ["resource_id"],
        "skuPartNumber": ["sku_part_number"],
        "skuName": ["sku_name"],
    }
    for attr in mapping.get(key, [key]):
        if hasattr(item, attr):
            return getattr(item, attr)
    return getattr(item, key, None)
