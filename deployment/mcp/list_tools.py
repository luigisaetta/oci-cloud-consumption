"""
Author: L. Saetta
Date last modified: 2026-04-26
License: MIT
Description: Simple MCP client that prints a readable list of exposed tools.
"""

import argparse
import asyncio
import os
import textwrap
from typing import Any, Iterable

from fastmcp import Client

DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
DESCRIPTION_WIDTH = 88


def _get_tool_description(tool: Any) -> str:
    """Return a compact description from a FastMCP tool object."""
    description = getattr(tool, "description", "") or ""
    return " ".join(str(description).split())


def _format_tools(mcp_url: str, tools: Iterable[Any]) -> str:
    """Build a readable text report for exposed MCP tools."""
    tool_list = sorted(tools, key=lambda item: getattr(item, "name", ""))
    lines = [
        "MCP tool inventory",
        f"Server: {mcp_url}",
        f"Tools:  {len(tool_list)}",
        "",
    ]

    if not tool_list:
        lines.append("No tools exposed by this server.")
        return "\n".join(lines)

    for index, tool in enumerate(tool_list, start=1):
        name = getattr(tool, "name", "<unnamed>")
        lines.append(f"{index:>2}. {name}")

        description = _get_tool_description(tool)
        if description:
            wrapped = textwrap.wrap(
                description,
                width=DESCRIPTION_WIDTH,
                initial_indent="    ",
                subsequent_indent="    ",
            )
            lines.extend(wrapped)

        lines.append("")

    return "\n".join(lines).rstrip()


async def _list_tools(mcp_url: str) -> None:
    """Connect to an MCP server and print available tools."""
    async with Client(mcp_url) as client:
        tools = await client.list_tools()
        print(_format_tools(mcp_url, tools))


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
