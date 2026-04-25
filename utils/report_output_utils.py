"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Internal helpers to save generated markdown reports locally or to OCI Object Storage.
"""

# pylint: disable=too-many-arguments

import os
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.object_storage_utils import ObjectStorageUtils

OBJECT_STORAGE_BUCKET_ENV = "OCI_OBJECT_STORAGE_BUCKET_NAME"
OBJECT_STORAGE_PREFIX_ENV = "OCI_OBJECT_STORAGE_REPORT_PREFIX"


@dataclass(frozen=True)
class SavedReport:
    """Metadata for a persisted markdown report."""

    destination: str
    location: str


def build_object_name(filename: str, prefix: Optional[str] = None) -> str:
    """Build an Object Storage object name from optional prefix and file name."""
    clean_filename = str(filename).strip().lstrip("/")
    if not clean_filename:
        raise ValueError("Object Storage object name must not be empty.")

    clean_prefix = (prefix or os.getenv(OBJECT_STORAGE_PREFIX_ENV) or "").strip("/")
    if not clean_prefix:
        return clean_filename
    return f"{clean_prefix}/{clean_filename}"


def resolve_bucket_name(bucket_name: Optional[str] = None) -> str:
    """Resolve Object Storage bucket from explicit value or environment."""
    resolved = (bucket_name or os.getenv(OBJECT_STORAGE_BUCKET_ENV) or "").strip()
    if not resolved:
        raise ValueError(
            "Object Storage bucket name is required. "
            f"Pass --bucket-name or set {OBJECT_STORAGE_BUCKET_ENV}."
        )
    return resolved


def save_report_to_local(markdown: str, output_path: Path) -> SavedReport:
    """Persist markdown report to a local file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return SavedReport(destination="local", location=str(output_path))


def save_report_to_object_storage(
    markdown: str,
    *,
    bucket_name: Optional[str],
    object_name: str,
    config_profile: Optional[str] = "DEFAULT",
    auth_type: Optional[str] = None,
    storage: Optional[ObjectStorageUtils] = None,
) -> SavedReport:
    """Persist markdown report to OCI Object Storage."""
    resolved_bucket = resolve_bucket_name(bucket_name)
    storage_client = storage or ObjectStorageUtils(
        config_profile=config_profile,
        auth_type=auth_type,
    )
    storage_client.write_text_file(
        bucket_name=resolved_bucket,
        object_name=object_name,
        content=markdown,
    )
    return SavedReport(
        destination="object_storage",
        location=f"oci://{resolved_bucket}/{object_name}",
    )


def add_report_output_arguments(parser: ArgumentParser) -> None:
    """Add common report output CLI arguments to a parser."""
    parser.add_argument(
        "--output-target",
        choices=["stdout", "local", "object_storage"],
        default="stdout",
        help="Where to write the report (default: stdout).",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Local output file path when --output-target local.",
    )
    parser.add_argument(
        "--bucket-name",
        default=None,
        help=(
            "OCI Object Storage bucket when --output-target object_storage. "
            f"Defaults to {OBJECT_STORAGE_BUCKET_ENV}."
        ),
    )
    parser.add_argument(
        "--object-name",
        default=None,
        help="Object Storage object name when --output-target object_storage.",
    )
    parser.add_argument(
        "--object-prefix",
        default=None,
        help=(
            "Optional Object Storage object prefix. "
            f"Defaults to {OBJECT_STORAGE_PREFIX_ENV}."
        ),
    )


def save_report_from_args(
    markdown: str,
    args: Namespace,
    *,
    default_filename: str,
) -> Optional[SavedReport]:
    """Persist a report using the common argparse output options."""
    if args.output_target == "stdout":
        return None

    if args.output_target == "local":
        output_path = Path(args.output_file or Path("reports") / default_filename)
        return save_report_to_local(markdown, output_path)

    object_name = args.object_name or build_object_name(
        default_filename,
        prefix=args.object_prefix,
    )
    return save_report_to_object_storage(
        markdown,
        bucket_name=args.bucket_name,
        object_name=object_name,
        config_profile=args.profile,
        auth_type=args.auth_type,
    )
