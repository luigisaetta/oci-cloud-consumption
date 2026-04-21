"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Unit tests for MCP server configuration loading.
"""

import json

import pytest

from agent.mcp_config import load_mcp_server_connections


def test_load_mcp_server_connections_happy_path(tmp_path) -> None:
    cfg = {
        "servers": [
            {
                "name": "consumption",
                "url": "http://127.0.0.1:8000/mcp",
                "transport": "streamable_http",
                "enabled": True,
            }
        ]
    }
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")

    connections = load_mcp_server_connections(str(path))

    assert "consumption" in connections
    assert connections["consumption"]["url"] == "http://127.0.0.1:8000/mcp"
    assert connections["consumption"]["transport"] == "streamable_http"


def test_load_mcp_server_connections_ignores_disabled(tmp_path) -> None:
    cfg = {
        "servers": [
            {
                "name": "disabled_server",
                "url": "http://127.0.0.1:9999/mcp",
                "enabled": False,
            }
        ]
    }
    path = tmp_path / "mcp_servers.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")

    with pytest.raises(ValueError, match="No enabled MCP servers"):
        load_mcp_server_connections(str(path))


def test_load_mcp_server_connections_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_mcp_server_connections("/tmp/this_file_does_not_exist_mcp_servers.json")
