"""
Author: L. Saetta
Date last modified: 2026-04-25
License: MIT
Description: Reusable helper class for reading and writing OCI Object Storage files.
"""

# pylint: disable=too-many-arguments,broad-exception-caught

from typing import Any, Dict, List, Optional, Union

import oci
from oci.object_storage import ObjectStorageClient

from utils import emit_structured_log, get_console_logger
from utils.oci_utils import make_oci_config

logger = get_console_logger()

TextBody = Union[str, bytes]


class ObjectStorageUtils:
    """Utility wrapper around OCI Object Storage operations.

    The class supports the same authentication strategies used by the rest of
    the project: `AUTO`, `API_KEY`/`USER_PRINCIPAL`, and `RESOURCE_PRINCIPAL`.
    Tests and callers that already manage OCI clients can inject `client`
    directly to avoid creating a new SDK client.
    """

    def __init__(
        self,
        *,
        namespace_name: Optional[str] = None,
        config_profile: Optional[str] = None,
        auth_type: Optional[str] = None,
        client: Optional[ObjectStorageClient] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._namespace_name = namespace_name
        self._client = client
        self._config = config or {}

        if self._client is None:
            self._client, self._config = self._make_object_storage_client(
                config_profile=config_profile,
                auth_type=auth_type,
            )

    @staticmethod
    def _make_object_storage_client(
        *,
        config_profile: Optional[str],
        auth_type: Optional[str],
    ) -> tuple[ObjectStorageClient, Dict[str, Any]]:
        """Create an Object Storage client with OCI SDK retry support."""
        cfg, signer = make_oci_config(config_profile, auth_type=auth_type)
        client_kwargs = {
            "timeout": 60.0,
            "retry_strategy": oci.retry.DEFAULT_RETRY_STRATEGY,
        }
        if signer is not None:
            client_kwargs["signer"] = signer
        return ObjectStorageClient(cfg, **client_kwargs), cfg

    @property
    def namespace_name(self) -> str:
        """Return the configured namespace, resolving it once when omitted."""
        if not self._namespace_name:
            self._namespace_name = self._client.get_namespace().data
        return self._namespace_name

    def write_text_file(
        self,
        *,
        bucket_name: str,
        object_name: str,
        content: TextBody,
        content_type: str = "text/markdown; charset=utf-8",
    ) -> Optional[str]:
        """Write a text object to an OCI Object Storage bucket.

        Args:
            bucket_name: Target Object Storage bucket name.
            object_name: Target object name, including any virtual folder prefix.
            content: Text or UTF-8 bytes to write.
            content_type: MIME content type to store with the object.

        Returns:
            OCI `opc-request-id` when the SDK response exposes it, otherwise `None`.
        """
        operation = "object_storage_write_text_file"
        try:
            body = content.encode("utf-8") if isinstance(content, str) else content
            response = self._client.put_object(
                namespace_name=self.namespace_name,
                bucket_name=bucket_name,
                object_name=object_name,
                put_object_body=body,
                content_type=content_type,
            )
            request_id = _get_response_header(response, "opc-request-id")
            emit_structured_log(
                logger,
                component="api",
                operation=operation,
                status="success",
                bucket_name=bucket_name,
                object_name=object_name,
                opc_request_id=request_id,
            )
            return request_id
        except Exception as exc:
            _emit_failure(
                operation=operation,
                bucket_name=bucket_name,
                object_name=object_name,
                error=exc,
            )
            raise

    def list_files(
        self,
        *,
        bucket_name: str,
        prefix: Optional[str] = None,
    ) -> List[str]:
        """Return all object names in a bucket, optionally filtered by prefix."""
        operation = "object_storage_list_files"
        try:
            object_names: List[str] = []
            start = None

            while True:
                response = self._client.list_objects(
                    namespace_name=self.namespace_name,
                    bucket_name=bucket_name,
                    prefix=prefix,
                    start=start,
                )
                data = response.data
                object_names.extend(item.name for item in getattr(data, "objects", []))
                start = getattr(data, "next_start_with", None)
                if not start:
                    break

            emit_structured_log(
                logger,
                component="api",
                operation=operation,
                status="success",
                bucket_name=bucket_name,
                prefix=prefix or "",
                file_count=len(object_names),
            )
            return object_names
        except Exception as exc:
            _emit_failure(
                operation=operation,
                bucket_name=bucket_name,
                prefix=prefix or "",
                error=exc,
            )
            raise

    def read_markdown_file(
        self,
        *,
        bucket_name: str,
        object_name: str,
        encoding: str = "utf-8",
    ) -> str:
        """Read a Markdown text object from an OCI Object Storage bucket."""
        normalized_name = object_name.lower()
        if not normalized_name.endswith((".md", ".markdown")):
            raise ValueError("object_name must point to a Markdown file")
        return self.read_text_file(
            bucket_name=bucket_name,
            object_name=object_name,
            encoding=encoding,
        )

    def read_text_file(
        self,
        *,
        bucket_name: str,
        object_name: str,
        encoding: str = "utf-8",
    ) -> str:
        """Read a text object from an OCI Object Storage bucket."""
        operation = "object_storage_read_text_file"
        try:
            response = self._client.get_object(
                namespace_name=self.namespace_name,
                bucket_name=bucket_name,
                object_name=object_name,
            )
            content = _read_response_body(response.data)
            if isinstance(content, str):
                text = content
            else:
                text = content.decode(encoding)

            emit_structured_log(
                logger,
                component="api",
                operation=operation,
                status="success",
                bucket_name=bucket_name,
                object_name=object_name,
                content_length=len(text),
            )
            return text
        except Exception as exc:
            _emit_failure(
                operation=operation,
                bucket_name=bucket_name,
                object_name=object_name,
                error=exc,
            )
            raise


def _read_response_body(data: Any) -> Union[str, bytes]:
    """Normalize OCI get_object response data into text or bytes."""
    if isinstance(data, (str, bytes)):
        return data
    if hasattr(data, "content"):
        return data.content
    if hasattr(data, "read"):
        return data.read()
    raise TypeError("Unsupported OCI Object Storage response body")


def _get_response_header(response: Any, name: str) -> Optional[str]:
    """Extract a response header value when available."""
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    return headers.get(name)


def _emit_failure(operation: str, error: Exception, **extra: Any) -> None:
    """Emit a structured failure log before re-raising an operation error."""
    emit_structured_log(
        logger,
        component="api",
        operation=operation,
        status="failure",
        error_details=str(error),
        **extra,
    )
