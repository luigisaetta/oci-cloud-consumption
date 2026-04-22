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

from dotenv import load_dotenv

# Ensure project root imports work when running as script from repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from common.compartment_utils import (  # pylint: disable=wrong-import-position
    get_compartment_owner,
)


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

    print(f"Compartment input: {args.compartment}")
    print(f"Tag namespace: {args.namespace}")
    print(f"Tag key: {args.tag_key}")
    value = get_compartment_owner(
        args.compartment,
        config_profile=args.profile,
        auth_type=args.auth_type,
        namespace=args.namespace,
        tag_key=args.tag_key,
    )
    print(f"Tag value: {value}")
    return 0 if value != "not_found" else 2


if __name__ == "__main__":
    raise SystemExit(main())
