"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Unit tests for internal report output persistence helpers.
"""

# pylint: disable=duplicate-code,missing-class-docstring,missing-function-docstring,too-few-public-methods

from pathlib import Path
from types import SimpleNamespace

import pytest

from utils import report_output_utils


def test_build_object_name_without_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(report_output_utils.OBJECT_STORAGE_PREFIX_ENV, raising=False)

    assert report_output_utils.build_object_name("monthly.md") == "monthly.md"


def test_build_object_name_with_explicit_prefix() -> None:
    assert (
        report_output_utils.build_object_name("/monthly.md", prefix="/reports/")
        == "reports/monthly.md"
    )


def test_build_object_name_uses_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        report_output_utils.OBJECT_STORAGE_PREFIX_ENV,
        "batch/reports",
    )

    assert (
        report_output_utils.build_object_name("monthly.md")
        == "batch/reports/monthly.md"
    )


def test_resolve_bucket_name_uses_explicit_value() -> None:
    assert report_output_utils.resolve_bucket_name("bucket") == "bucket"


def test_resolve_bucket_name_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(report_output_utils.OBJECT_STORAGE_BUCKET_ENV, "env-bucket")

    assert report_output_utils.resolve_bucket_name() == "env-bucket"


def test_resolve_bucket_name_requires_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(report_output_utils.OBJECT_STORAGE_BUCKET_ENV, raising=False)

    with pytest.raises(ValueError, match="bucket name is required"):
        report_output_utils.resolve_bucket_name()


def test_save_report_to_local_writes_file(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "out.md"

    saved = report_output_utils.save_report_to_local("# Report\n", output_path)

    assert saved.destination == "local"
    assert saved.location == str(output_path)
    assert output_path.read_text(encoding="utf-8") == "# Report\n"


def test_save_report_to_object_storage_uses_injected_storage() -> None:
    class FakeStorage:
        def __init__(self) -> None:
            self.calls = []

        def write_text_file(self, **kwargs):
            self.calls.append(kwargs)

    storage = FakeStorage()

    saved = report_output_utils.save_report_to_object_storage(
        "# Report",
        bucket_name="bucket",
        object_name="reports/out.md",
        storage=storage,
    )

    assert saved.destination == "object_storage"
    assert saved.location == "oci://bucket/reports/out.md"
    assert storage.calls == [
        {
            "bucket_name": "bucket",
            "object_name": "reports/out.md",
            "content": "# Report",
        }
    ]


def test_save_report_from_args_returns_none_for_stdout() -> None:
    args = SimpleNamespace(output_target="stdout")

    assert (
        report_output_utils.save_report_from_args(
            "# Report",
            args,
            default_filename="out.md",
        )
        is None
    )


def test_save_report_from_args_saves_local_file(tmp_path: Path) -> None:
    output_path = tmp_path / "out.md"
    args = SimpleNamespace(
        output_target="local",
        output_file=str(output_path),
    )

    saved = report_output_utils.save_report_from_args(
        "# Report",
        args,
        default_filename="default.md",
    )

    assert saved is not None
    assert saved.location == str(output_path)
    assert output_path.read_text(encoding="utf-8") == "# Report"
