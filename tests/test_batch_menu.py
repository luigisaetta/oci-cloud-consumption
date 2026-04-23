"""
Author: L. Saetta
Date last modified: 2026-04-23
License: MIT
Description: Unit tests for batch CLI menu helper utilities.
"""

import pytest

from cli import batch_menu


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
