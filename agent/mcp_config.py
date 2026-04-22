"""
Author: L. Saetta
Date last modified: 2026-04-22
License: MIT
Description: Configuration loader for internal MCP server list used by the tool-calling agent.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def _load_mcp_servers(config_path: str) -> List[Dict[str, Any]]:
    """Load raw MCP server entries from JSON config."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"MCP server config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("servers", [])


def load_mcp_server_statuses(config_path: str) -> List[Dict[str, Any]]:
    """Load MCP server list with enabled status for UI/metadata exposure.

    Args:
        config_path: Path to JSON configuration file.

    Returns:
        List of dictionaries: `{"name": str, "enabled": bool}`.
    """
    servers = _load_mcp_servers(config_path)
    statuses: List[Dict[str, Any]] = []
    for server in servers:
        name = server.get("name")
        if not name:
            raise ValueError("Each MCP server must define 'name'.")
        statuses.append(
            {
                "name": name,
                "enabled": bool(server.get("enabled", True)),
            }
        )
    return statuses


def load_mcp_server_connections(config_path: str) -> Dict[str, Dict[str, Any]]:
    """Load MCP server definitions and return LangChain MCP client connections.

    Args:
        config_path: Path to JSON configuration file. Expected shape:
            {
              "servers": [
                {"name": "...", "url": "...", "transport": "streamable_http", "enabled": true}
              ]
            }

    Returns:
        Dictionary keyed by server name, where each value is a connection
        dictionary compatible with `MultiServerMCPClient`.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If no enabled servers are available or entries are invalid.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    servers = _load_mcp_servers(config_path)

    connections: Dict[str, Dict[str, Any]] = {}
    for server in servers:
        if not server.get("enabled", True):
            continue

        name = server.get("name")
        url = server.get("url")
        transport = server.get("transport", "streamable_http")

        if not name or not url:
            raise ValueError("Each enabled MCP server must define 'name' and 'url'.")

        connections[name] = {
            "transport": transport,
            "url": url,
        }

    if not connections:
        raise ValueError("No enabled MCP servers found in configuration.")

    return connections
