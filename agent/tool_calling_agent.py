"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: LangChain tool-calling agent that consumes tools exposed by configured MCP servers.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.mcp_config import load_mcp_server_connections
from utils import get_console_logger
from utils.oci_model import create_chat_oci_genai

SYSTEM_PROMPT = (
    "You are an OCI cloud consumption assistant for tenant administrators. "
    "Use MCP tools whenever data retrieval or analysis is needed. "
    "Provide concise, accurate, and actionable answers. "
    "When calling tools, never call with empty arguments. "
    "Always provide all required date inputs explicitly using ISO format "
    "(YYYY-MM-DD), and include required scope fields such as compartment "
    "or service when applicable. "
    "If a tool returns missing_arguments, call the same tool again with "
    "the required arguments."
)
AGENT_RECURSION_LIMIT = 30
LLM_MAX_RETRIES = int(os.getenv("OCI_LLM_MAX_RETRIES", "3"))
LLM_RETRY_BASE_SECONDS = float(os.getenv("OCI_LLM_RETRY_BASE_SECONDS", "1.0"))
LLM_RETRY_MAX_SECONDS = float(os.getenv("OCI_LLM_RETRY_MAX_SECONDS", "8.0"))
logger = get_console_logger(name="ConsumptionToolCallingAgent")


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
        result = await self._ainvoke_with_retry(agent_graph, messages)

        result_messages = result.get("messages", [])
        self._log_tool_calls(result_messages)
        answer = self._extract_answer(result_messages)

        return {
            "answer": answer,
            "messages": result_messages,
            "mcp_servers": list(connections.keys()),
            "tool_count": len(tools),
        }

    async def invoke_stream(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Invoke the agent and stream execution events incrementally.

        Args:
            user_message: Current user request.
            history: Optional chat history list with dictionaries containing
                `role` and `content` keys.

        Yields:
            Dictionaries shaped as:
            - `{"event": "start", "data": {...}}`
            - `{"event": "tool_start", "data": {...}}`
            - `{"event": "tool_end", "data": {...}}`
            - `{"event": "token", "data": {"text": "..."} }`
            - `{"event": "final", "data": {...}}`

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

        yield {
            "event": "start",
            "data": {
                "mcp_servers": list(connections.keys()),
                "tool_count": len(tools),
            },
        }

        streamed_parts: List[str] = []
        final_answer = ""

        attempt = 1
        while attempt <= LLM_MAX_RETRIES:
            emitted_any_output = False
            try:
                async for event in agent_graph.astream_events(
                    {"messages": messages},
                    config={"recursion_limit": AGENT_RECURSION_LIMIT},
                    version="v2",
                ):
                    event_name = event.get("event")
                    event_data = event.get("data", {})

                    if event_name == "on_tool_start":
                        tool_name = event.get("name", "unknown_tool")
                        tool_input = event_data.get("input", {})
                        logger.info(
                            "Tool call executed | name=%s | args=%s",
                            tool_name,
                            tool_input,
                        )
                        emitted_any_output = True
                        yield {
                            "event": "tool_start",
                            "data": {"name": tool_name, "args": tool_input},
                        }
                        continue

                    if event_name == "on_tool_end":
                        tool_name = event.get("name", "unknown_tool")
                        emitted_any_output = True
                        yield {"event": "tool_end", "data": {"name": tool_name}}
                        continue

                    if event_name == "on_chat_model_stream":
                        token_text = self._extract_text_from_chunk(event_data.get("chunk"))
                        if token_text:
                            streamed_parts.append(token_text)
                            emitted_any_output = True
                            yield {"event": "token", "data": {"text": token_text}}
                        continue

                    if event_name == "on_chain_end":
                        output = event_data.get("output", {})
                        if isinstance(output, dict) and "messages" in output:
                            final_answer = self._extract_answer(output.get("messages", []))

                break
            except Exception as exc:  # pragma: no cover - runtime integration behavior
                retryable = self._is_retryable_llm_error(exc)
                has_attempts_left = attempt < LLM_MAX_RETRIES
                if retryable and has_attempts_left and not emitted_any_output:
                    wait_seconds = self._backoff_seconds(attempt)
                    logger.warning(
                        "Retryable LLM stream error. attempt=%s/%s wait=%.2fs error=%s",
                        attempt,
                        LLM_MAX_RETRIES,
                        wait_seconds,
                        exc,
                    )
                    await asyncio.sleep(wait_seconds)
                    attempt += 1
                    continue
                raise

        answer = final_answer or "".join(streamed_parts).strip()
        yield {
            "event": "final",
            "data": {
                "answer": answer,
                "mcp_servers": list(connections.keys()),
                "tool_count": len(tools),
            },
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

    @staticmethod
    def _log_tool_calls(messages: List[Any]) -> None:
        """Log each executed tool call with tool name and provided arguments.

        Args:
            messages: Message list returned by the LangChain agent run.
        """
        for message in messages:
            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                continue

            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "unknown_tool")
                    tool_args = tool_call.get("args", {})
                    logger.info(
                        "Tool call executed | name=%s | args=%s",
                        tool_name,
                        tool_args,
                    )

    @staticmethod
    def _extract_text_from_chunk(chunk: Any) -> str:
        """Extract textual token content from a LangChain stream chunk.

        Args:
            chunk: Streamed chunk object from `on_chat_model_stream`.

        Returns:
            Extracted text for this chunk, or empty string when unavailable.
        """
        if chunk is None:
            return ""

        content = getattr(chunk, "content", chunk)
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return str(content.get("text") or content.get("content") or "")
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
            return "".join(parts)
        return ""

    async def _ainvoke_with_retry(self, agent_graph: Any, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Invoke the agent graph with retries for transient OCI LLM failures.

        Args:
            agent_graph: LangChain/LangGraph runnable returned by `create_agent`.
            messages: Prepared message payload.

        Returns:
            Agent invocation result dictionary.

        Raises:
            Exception: Re-raises the last non-retryable or exhausted exception.
        """
        last_error: Optional[Exception] = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            try:
                return await agent_graph.ainvoke(
                    {"messages": messages},
                    config={"recursion_limit": AGENT_RECURSION_LIMIT},
                )
            except Exception as exc:  # pragma: no cover - runtime integration behavior
                last_error = exc
                retryable = self._is_retryable_llm_error(exc)
                has_attempts_left = attempt < LLM_MAX_RETRIES
                if retryable and has_attempts_left:
                    wait_seconds = self._backoff_seconds(attempt)
                    logger.warning(
                        "Retryable LLM invoke error. attempt=%s/%s wait=%.2fs error=%s",
                        attempt,
                        LLM_MAX_RETRIES,
                        wait_seconds,
                        exc,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM invocation failed without a captured exception")

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        """Compute exponential backoff delay for a retry attempt.

        Args:
            attempt: Retry attempt number starting from 1.

        Returns:
            Delay in seconds bounded by configured max delay.
        """
        delay = LLM_RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1))
        return min(delay, LLM_RETRY_MAX_SECONDS)

    @staticmethod
    def _is_retryable_llm_error(exc: Exception) -> bool:
        """Determine whether an LLM error is transient and retryable.

        Args:
            exc: Raised exception from model invocation.

        Returns:
            True for transient network/throttling/service-unavailable errors.
        """
        error_name = exc.__class__.__name__.lower()
        message = str(exc).lower()
        retryable_markers = (
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "connection error",
            "network",
            "throttl",
            "too many requests",
            "rate limit",
            "service unavailable",
            "internal server error",
            "bad gateway",
            "gateway timeout",
            "status 429",
            "status 500",
            "status 502",
            "status 503",
            "status 504",
        )
        retryable_names = (
            "timeouterror",
            "connectionerror",
            "readtimeout",
            "connecttimeout",
            "serviceerror",
        )
        if any(marker in message for marker in retryable_markers):
            return True
        if any(name in error_name for name in retryable_names):
            return True
        return False
