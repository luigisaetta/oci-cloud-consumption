"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Factory utilities to create OCI chat models for agent tool-calling workflows.
"""

import os
from typing import Optional

from langchain_oci import ChatOCIGenAI

from utils import emit_structured_log, get_console_logger

logger = get_console_logger(name="OCIModelFactory")


def create_chat_oci_genai(
    *,
    model_id: Optional[str] = None,
    region: Optional[str] = None,
    auth_type: Optional[str] = None,
    compartment_id: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> ChatOCIGenAI:
    """Create and configure a `ChatOCIGenAI` model instance.

    The function uses explicit arguments when provided, otherwise it falls back
    to environment variables defined in `.env`.

    Args:
        model_id: OCI model identifier. Falls back to `OCI_MODEL_ID`.
        region: OCI region (for endpoint derivation). Falls back to `OCI_REGION`.
        auth_type: OCI auth type (for example `API_KEY` or resource principal).
            Falls back to `OCI_AUTH_TYPE`.
        compartment_id: OCI compartment OCID used by the model service.
            Falls back to `OCI_COMPARTMENT_ID`.
        max_tokens: Max tokens for model output. Falls back to `MAX_TOKENS`.
        temperature: Sampling temperature for model generation.
            Falls back to `TEMPERATURE` and defaults to `0.0`.

    Returns:
        A configured `ChatOCIGenAI` instance ready for LangChain agent execution.

    Raises:
        ValueError: If required settings are missing.
    """
    try:
        resolved_model_id = model_id or os.getenv("OCI_MODEL_ID")
        resolved_region = region or os.getenv("OCI_REGION")
        resolved_auth_type = auth_type or os.getenv("OCI_AUTH_TYPE", "API_KEY")
        resolved_compartment_id = compartment_id or os.getenv("OCI_COMPARTMENT_ID")

        if not resolved_model_id:
            raise ValueError("Missing OCI model id. Set OCI_MODEL_ID or pass model_id.")
        if not resolved_compartment_id:
            raise ValueError(
                "Missing OCI compartment id. Set OCI_COMPARTMENT_ID or pass compartment_id."
            )

        if max_tokens is None:
            max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        if temperature is None:
            temperature = float(os.getenv("TEMPERATURE", "0.0"))

        service_endpoint = None
        if resolved_region:
            service_endpoint = (
                f"https://inference.generativeai.{resolved_region}.oci.oraclecloud.com"
            )

        model_kwargs = {}
        # OCI OpenAI-compatible GPT-5 models expect `max_completion_tokens`
        # instead of legacy `max_tokens`.
        if resolved_model_id.startswith("openai.gpt-5"):
            model_kwargs["max_completion_tokens"] = max_tokens
        else:
            model_kwargs["max_tokens"] = max_tokens
        model_kwargs["temperature"] = temperature

        kwargs = {
            "model_id": resolved_model_id,
            "auth_type": resolved_auth_type,
            "compartment_id": resolved_compartment_id,
            "provider": "openai",
            "model_kwargs": model_kwargs,
        }
        if service_endpoint:
            kwargs["service_endpoint"] = service_endpoint

        emit_structured_log(
            logger,
            component="agent",
            operation="llm_model_init",
            status="success",
            model_id=resolved_model_id,
            has_region=bool(resolved_region),
            auth_type=resolved_auth_type,
        )
        return ChatOCIGenAI(**kwargs)
    except Exception as exc:
        emit_structured_log(
            logger,
            component="agent",
            operation="llm_model_init",
            status="failure",
            error_details=str(exc),
        )
        raise
