"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Unit tests for batch CLI menu helper utilities.
"""

# pylint: disable=missing-function-docstring,protected-access

from pathlib import Path

import pytest

from cli import batch_menu
from utils.report_output_utils import SavedReport


def test_normalize_auth_type_choice_accepts_valid_values() -> None:
    assert batch_menu._normalize_auth_type_choice("auto") == "AUTO"
    assert batch_menu._normalize_auth_type_choice("API_KEY") == "API_KEY"
    assert (
        batch_menu._normalize_auth_type_choice("resource_principal")
        == "RESOURCE_PRINCIPAL"
    )


def test_normalize_auth_type_choice_maps_none_to_null() -> None:
    assert batch_menu._normalize_auth_type_choice("none") is None
    assert batch_menu._normalize_auth_type_choice("") is None


def test_normalize_auth_type_choice_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid auth type"):
        batch_menu._normalize_auth_type_choice("IAM_TOKEN")


def test_normalize_output_destination_accepts_valid_values() -> None:
    assert batch_menu._normalize_output_destination("local") == "local"
    assert (
        batch_menu._normalize_output_destination("OBJECT_STORAGE") == "object_storage"
    )


def test_normalize_output_destination_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid output destination"):
        batch_menu._normalize_output_destination("stdout")


def test_format_output_location_for_local_path() -> None:
    options = batch_menu.OutputOptions(
        destination="local",
        local_path=Path("reports/out.md"),
    )

    assert batch_menu._format_output_location(options) == "reports/out.md"


def test_save_report_to_object_storage_uses_output_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_save(markdown, **kwargs):
        captured["markdown"] = markdown
        captured.update(kwargs)
        return SavedReport(
            destination="object_storage",
            location="oci://bucket/reports/out.md",
        )

    monkeypatch.setattr(batch_menu, "save_report_to_object_storage", fake_save)
    options = batch_menu.OutputOptions(
        destination="object_storage",
        bucket_name="bucket",
        object_name="reports/out.md",
    )

    saved = batch_menu._save_report(
        "# Report",
        options,
        config_profile="DEFAULT",
        auth_type="API_KEY",
    )

    assert saved.location == "oci://bucket/reports/out.md"
    assert captured["markdown"] == "# Report"
    assert captured["bucket_name"] == "bucket"
    assert captured["object_name"] == "reports/out.md"
    assert captured["config_profile"] == "DEFAULT"
    assert captured["auth_type"] == "API_KEY"
