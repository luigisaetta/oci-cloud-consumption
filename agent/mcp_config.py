"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Configuration loader for internal MCP server list used by the tool-calling agent.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


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
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"MCP server config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    servers: List[Dict[str, Any]] = data.get("servers", [])

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
