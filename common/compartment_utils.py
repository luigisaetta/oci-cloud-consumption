"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Helpers to resolve OCI compartment owner tag values in a reusable way.
"""

from typing import Optional

from utils.oci_utils import (
    make_identity_client,
    make_oci_client,
    resolve_compartment_id,
)


def _normalize_created_by(tag_value: str) -> str:
    """Normalize OCI CreatedBy value for user-facing output."""
    prefix = "oracleidentitycloudservice/"
    suffix = "@oracle.com"
    if tag_value.startswith(prefix) and tag_value.endswith(suffix):
        return tag_value[len(prefix) : -len(suffix)]
    return tag_value


def get_compartment_owner(
    compartment_name: str,
    *,
    config_profile: Optional[str] = None,
    auth_type: Optional[str] = None,
    namespace: str = "OracleMandatory",
    tag_key: str = "CreatedBy",
) -> str:
    """Return normalized compartment owner tag value or `not_found` on failures.

    Args:
        compartment_name: Compartment exact name or OCID.
        config_profile: OCI profile name for API key auth.
        auth_type: Auth strategy (`AUTO`, `API_KEY`, `RESOURCE_PRINCIPAL`).
        namespace: Defined tag namespace containing owner metadata.
        tag_key: Defined tag key containing owner metadata.

    Returns:
        Normalized owner value, or `not_found` when tag/data cannot be resolved.
    """
    try:
        _usage_client, cfg = make_oci_client(
            config_profile=config_profile,
            auth_type=auth_type,
        )
        tenancy_id = cfg["tenancy"]
        identity_client = make_identity_client(cfg, tenancy_id)
        compartment_id = resolve_compartment_id(
            identity_client,
            tenancy_id,
            compartment_name,
        )
        compartment = identity_client.get_compartment(compartment_id).data
        defined_tags = compartment.defined_tags or {}
        namespace_tags = defined_tags.get(namespace) or {}
        tag_value = namespace_tags.get(tag_key)
        if not tag_value:
            return "not_found"
        return _normalize_created_by(tag_value)
    except Exception:  # pylint: disable=broad-exception-caught
        return "not_found"
