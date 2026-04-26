"""
Author: L. Saetta
Date last modified: 2026-04-26
License: MIT
Description: Simple MCP client that prints the tool names exposed by a server.
"""

import argparse
import asyncio
import os

from fastmcp import Client

DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"


async def _list_tools(mcp_url: str) -> None:
    """Connect to an MCP server and print available tool names."""
    async with Client(mcp_url) as client:
        tools = await client.list_tools()
        for tool in tools:
            print(tool.name)


def main() -> None:
    """Parse command-line options and run the MCP tool listing."""
    parser = argparse.ArgumentParser(
        description="Print the tool names exposed by an MCP streamable HTTP server."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=os.getenv("MCP_URL", DEFAULT_MCP_URL),
        help=(
            "MCP streamable HTTP URL. "
            f"Defaults to MCP_URL or {DEFAULT_MCP_URL}."
        ),
    )
    args = parser.parse_args()

    asyncio.run(_list_tools(args.url))


if __name__ == "__main__":
    main()
