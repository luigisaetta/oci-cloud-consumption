"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Reusable OCI helper functions for auth, identity, and response normalization.
"""

from typing import Any, Dict, List, Optional, Tuple

import oci
from oci.identity import IdentityClient
from oci.usage_api import UsageapiClient

from utils import get_console_logger

logger = get_console_logger()


def make_oci_client(
    config_profile: Optional[str],
) -> Tuple[UsageapiClient, Dict[str, Any]]:
    """Create an OCI Usage API client using profile config or resource principals.

    Args:
        config_profile: OCI profile name. If unavailable, resource principal auth
            is used.

    Returns:
        Tuple `(UsageapiClient, config_dict)` where config contains at least
        `region` and `tenancy`.
    """
    cfg: Optional[Dict[str, Any]] = None
    try:
        if config_profile:
            cfg = oci.config.from_file(profile_name=config_profile)
    except Exception as exc:  # pragma: no cover - depends on runtime auth context
        logger.warning(
            "Could not load OCI profile '%s', falling back to resource principals: %s",
            config_profile,
            exc,
        )
        cfg = None

    if cfg is not None:
        return UsageapiClient(cfg, timeout=60.0), cfg

    logger.info("Using RESOURCE_PRINCIPAL authentication")
    signer = oci.auth.signers.get_resource_principals_signer()
    cfg = {"region": signer.region, "tenancy": signer.tenancy_id}
    return UsageapiClient(cfg, signer=signer, timeout=60.0), cfg


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
