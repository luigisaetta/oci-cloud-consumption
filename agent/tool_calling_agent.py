"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: LangChain tool-calling agent that consumes tools exposed by configured MCP servers.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.mcp_config import load_mcp_server_connections
from utils.oci_model import create_chat_oci_genai

SYSTEM_PROMPT = (
    "You are an OCI cloud consumption assistant for tenant administrators. "
    "Use MCP tools whenever data retrieval or analysis is needed. "
    "Provide concise, accurate, and actionable answers."
)


class ConsumptionToolCallingAgent:
    """Tool-calling agent orchestrating OCI analysis over MCP tools.

    The agent:
    1. Loads MCP server connections from internal project configuration.
    2. Fetches available tools from all configured MCP servers.
    3. Executes LangChain tool-calling loop using an OCI-hosted LLM.

    Attributes:
        mcp_config_path: Path to MCP server configuration JSON.
        system_prompt: System instruction used by the agent.
    """

    def __init__(self, mcp_config_path: str, system_prompt: str = SYSTEM_PROMPT):
        """Initialize the tool-calling agent.

        Args:
            mcp_config_path: Path to internal MCP server configuration file.
            system_prompt: System prompt used by the agent loop.
        """
        self.mcp_config_path = str(Path(mcp_config_path))
        self.system_prompt = system_prompt
        self.llm = create_chat_oci_genai()

    async def invoke(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Invoke the agent and execute complete tool-calling loop.

        Args:
            user_message: Current user request.
            history: Optional chat history list with dictionaries containing
                `role` and `content` keys.

        Returns:
            Dictionary containing:
            - `answer`: final assistant answer text.
            - `messages`: raw message list returned by LangChain agent graph.
            - `mcp_servers`: list of MCP server names used.
            - `tool_count`: number of tools discovered across servers.

        Raises:
            ValueError: If input message is empty.
        """
        if not user_message or not user_message.strip():
            raise ValueError("user_message must be a non-empty string")

        connections = load_mcp_server_connections(self.mcp_config_path)

        mcp_client = MultiServerMCPClient(connections=connections)
        tools = await mcp_client.get_tools()

        agent_graph = create_agent(
            model=self.llm,
            tools=tools,
            system_prompt=self.system_prompt,
        )

        messages = self._prepare_messages(user_message=user_message, history=history)
        result = await agent_graph.ainvoke({"messages": messages})

        result_messages = result.get("messages", [])
        answer = self._extract_answer(result_messages)

        return {
            "answer": answer,
            "messages": result_messages,
            "mcp_servers": list(connections.keys()),
            "tool_count": len(tools),
        }

    @staticmethod
    def _prepare_messages(
        user_message: str,
        history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """Prepare normalized message list for LangChain agent invocation.

        Args:
            user_message: Current user message.
            history: Optional conversation history.

        Returns:
            List of message dictionaries in OpenAI-style format.
        """
        normalized_history: List[Dict[str, str]] = []
        for msg in history or []:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                normalized_history.append({"role": role, "content": content})

        normalized_history.append({"role": "user", "content": user_message})
        return normalized_history

    @staticmethod
    def _extract_answer(messages: List[Any]) -> str:
        """Extract final textual answer from LangChain message sequence.

        Args:
            messages: Message list returned by LangChain agent graph.

        Returns:
            Best-effort assistant answer as plain text.
        """
        if not messages:
            return ""

        last = messages[-1]
        content = getattr(last, "content", last)

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()

        return str(content)
