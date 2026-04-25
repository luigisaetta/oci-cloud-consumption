"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Unit tests for reusable OCI Object Storage utility helpers.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring,too-few-public-methods

from types import SimpleNamespace

import pytest

from utils import object_storage_utils
from utils.object_storage_utils import ObjectStorageUtils


class FakeObjectStorageClient:
    def __init__(self) -> None:
        self.calls = []
        self.objects = {
            "docs/report.md": b"# Report\n\nHello OCI\n",
            "docs/notes.txt": b"plain text",
        }

    def get_namespace(self):
        self.calls.append(("get_namespace",))
        return SimpleNamespace(data="tenant_namespace")

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        self.objects[kwargs["object_name"]] = kwargs["put_object_body"]
        return SimpleNamespace(headers={"opc-request-id": "req-123"})

    def list_objects(self, **kwargs):
        self.calls.append(("list_objects", kwargs))
        prefix = kwargs.get("prefix") or ""
        start = kwargs.get("start")
        pages = {
            None: (
                [SimpleNamespace(name=name) for name in sorted(self.objects)[:1]],
                "page-2",
            ),
            "page-2": (
                [
                    SimpleNamespace(name=name)
                    for name in sorted(self.objects)[1:]
                    if name.startswith(prefix)
                ],
                None,
            ),
        }
        objects, next_start_with = pages[start]
        return SimpleNamespace(
            data=SimpleNamespace(
                objects=[item for item in objects if item.name.startswith(prefix)],
                next_start_with=next_start_with,
            )
        )

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        return SimpleNamespace(
            data=SimpleNamespace(content=self.objects[kwargs["object_name"]])
        )


def test_write_text_file_uses_namespace_and_stores_utf8_bytes() -> None:
    fake_client = FakeObjectStorageClient()
    storage = ObjectStorageUtils(client=fake_client)

    request_id = storage.write_text_file(
        bucket_name="reports",
        object_name="docs/new.md",
        content="# New",
    )

    assert request_id == "req-123"
    assert fake_client.objects["docs/new.md"] == b"# New"
    put_call = fake_client.calls[-1][1]
    assert put_call["namespace_name"] == "tenant_namespace"
    assert put_call["bucket_name"] == "reports"
    assert put_call["content_type"] == "text/markdown; charset=utf-8"


def test_list_files_returns_all_paginated_names_for_prefix() -> None:
    fake_client = FakeObjectStorageClient()
    storage = ObjectStorageUtils(client=fake_client, namespace_name="ns")

    result = storage.list_files(bucket_name="reports", prefix="docs/")

    assert result == ["docs/notes.txt", "docs/report.md"]
    list_calls = [call for call in fake_client.calls if call[0] == "list_objects"]
    assert len(list_calls) == 2
    assert list_calls[0][1]["start"] is None
    assert list_calls[1][1]["start"] == "page-2"


def test_read_markdown_file_decodes_content() -> None:
    fake_client = FakeObjectStorageClient()
    storage = ObjectStorageUtils(client=fake_client, namespace_name="ns")

    result = storage.read_markdown_file(
        bucket_name="reports",
        object_name="docs/report.md",
    )

    assert result == "# Report\n\nHello OCI\n"


def test_read_markdown_file_rejects_non_markdown_extension() -> None:
    storage = ObjectStorageUtils(client=FakeObjectStorageClient(), namespace_name="ns")

    with pytest.raises(ValueError, match="Markdown"):
        storage.read_markdown_file(bucket_name="reports", object_name="docs/notes.txt")


def test_read_text_file_supports_stream_like_body() -> None:
    class StreamClient(FakeObjectStorageClient):
        def get_object(self, **kwargs):
            self.calls.append(("get_object", kwargs))
            return SimpleNamespace(data=SimpleNamespace(read=lambda: b"stream body"))

    storage = ObjectStorageUtils(client=StreamClient(), namespace_name="ns")

    assert (
        storage.read_text_file(bucket_name="reports", object_name="any.txt")
        == "stream body"
    )


def test_constructor_builds_profile_client_with_default_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    monkeypatch.delenv("OCI_REGION", raising=False)

    class FakeSdkClient:
        def __init__(self, cfg, **kwargs):
            captured["cfg"] = cfg
            captured["kwargs"] = kwargs

        def get_namespace(self):
            return SimpleNamespace(data="tenant_namespace")

    monkeypatch.setattr(
        object_storage_utils.oci.config,
        "from_file",
        lambda profile_name: {"region": "eu-milan-1", "tenancy": "tenancy"},
    )
    monkeypatch.setattr(object_storage_utils, "ObjectStorageClient", FakeSdkClient)

    storage = ObjectStorageUtils(config_profile="DEFAULT", auth_type="API_KEY")

    assert storage.namespace_name == "tenant_namespace"
    assert captured["cfg"]["region"] == "eu-milan-1"
    assert captured["kwargs"]["timeout"] == 60.0
    assert (
        captured["kwargs"]["retry_strategy"]
        is object_storage_utils.oci.retry.DEFAULT_RETRY_STRATEGY
    )


def test_constructor_overrides_profile_region_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeSdkClient:
        def __init__(self, cfg, **kwargs):
            captured["cfg"] = cfg
            captured["kwargs"] = kwargs

    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")
    monkeypatch.setattr(
        object_storage_utils.oci.config,
        "from_file",
        lambda profile_name: {"region": "eu-milan-1", "tenancy": "tenancy"},
    )
    monkeypatch.setattr(object_storage_utils, "ObjectStorageClient", FakeSdkClient)

    ObjectStorageUtils(config_profile="DEFAULT", auth_type="API_KEY")

    assert captured["cfg"]["region"] == "eu-frankfurt-1"
