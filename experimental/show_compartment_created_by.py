"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: CLI experiment to resolve a compartment by name and print
OracleMandatory.CreatedBy tag.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from oci.exceptions import ServiceError

# Ensure project root imports work when running as script from repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from utils.oci_utils import (  # pylint: disable=wrong-import-position
    make_identity_client,
    make_oci_client,
    resolve_compartment_id,
)


def get_defined_tag_value(
    compartment_name: str,
    config_profile: Optional[str],
    auth_type: Optional[str],
    namespace: str,
    tag_key: str,
) -> tuple[str, Optional[str]]:
    """Resolve compartment and return requested defined tag value.

    Args:
        compartment_name: Exact compartment name or OCID.
        config_profile: OCI CLI profile used for authentication.
        auth_type: Auth strategy (`AUTO`, `API_KEY`, `RESOURCE_PRINCIPAL`).
        namespace: Defined tag namespace.
        tag_key: Defined tag key.

    Returns:
        Tuple (resolved_compartment_id, tag_value_or_none).
    """
    _usage_client, cfg = make_oci_client(
        config_profile=config_profile,
        auth_type=auth_type,
    )
    tenancy_id = cfg["tenancy"]
    identity_client = make_identity_client(cfg, tenancy_id)

    compartment_id = resolve_compartment_id(
        identity_client, tenancy_id, compartment_name
    )
    compartment = identity_client.get_compartment(compartment_id).data

    defined_tags = compartment.defined_tags or {}
    namespace_tags = defined_tags.get(namespace) or {}
    return compartment_id, namespace_tags.get(tag_key)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the compartment tag lookup script."""
    parser = argparse.ArgumentParser(
        description=(
            "Read a defined tag from an OCI compartment resolved by exact name or OCID."
        )
    )
    parser.add_argument(
        "compartment",
        help="Compartment exact name or compartment OCID.",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("OCI_CONFIG_PROFILE"),
        help=(
            "OCI config profile name (default: OCI_CONFIG_PROFILE env var; "
            "if unavailable, fallback auth may be used)."
        ),
    )
    parser.add_argument(
        "--namespace",
        default="OracleMandatory",
        help="Defined tag namespace (default: OracleMandatory).",
    )
    parser.add_argument(
        "--tag-key",
        default="CreatedBy",
        help="Defined tag key (default: CreatedBy).",
    )
    parser.add_argument(
        "--auth-type",
        default=os.getenv("OCI_AUTH_TYPE", "AUTO"),
        help=(
            "Auth strategy: AUTO, API_KEY, RESOURCE_PRINCIPAL "
            "(default from OCI_AUTH_TYPE or AUTO)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Run the CLI flow and print the requested compartment tag value."""
    args = parse_args()

    try:
        compartment_id, tag_value = get_defined_tag_value(
            compartment_name=args.compartment,
            config_profile=args.profile,
            auth_type=args.auth_type,
            namespace=args.namespace,
            tag_key=args.tag_key,
        )
    except (ValueError, KeyError, ServiceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Compartment input: {args.compartment}")
    print(f"Resolved compartment OCID: {compartment_id}")
    print(f"Tag namespace: {args.namespace}")
    print(f"Tag key: {args.tag_key}")
    print(f"Auth type: {args.auth_type}")
    if tag_value is None:
        print("Tag value: <NOT SET>")
        return 2

    print(f"Tag value: {tag_value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
