"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Unit tests for tool-calling agent helper methods.
"""

from types import SimpleNamespace

import agent.tool_calling_agent as tool_calling_agent_module
from agent.tool_calling_agent import ConsumptionToolCallingAgent


def test_prepare_messages_appends_user_message() -> None:
    messages = ConsumptionToolCallingAgent._prepare_messages(
        user_message="Current prompt",
        history=[{"role": "assistant", "content": "Previous answer"}],
    )

    assert messages[0] == {"role": "assistant", "content": "Previous answer"}
    assert messages[-1] == {"role": "user", "content": "Current prompt"}


def test_extract_answer_from_string_content() -> None:
    out = ConsumptionToolCallingAgent._extract_answer(
        [SimpleNamespace(content="Final answer")]
    )
    assert out == "Final answer"


def test_extract_answer_from_list_content_blocks() -> None:
    out = ConsumptionToolCallingAgent._extract_answer(
        [
            SimpleNamespace(
                content=[
                    {"type": "text", "text": "Part 1"},
                    {"type": "text", "text": "Part 2"},
                ]
            )
        ]
    )
    assert out == "Part 1\nPart 2"


def test_log_tool_calls_logs_name_and_args(monkeypatch) -> None:
    captured = []

    def fake_info(message, tool_name, tool_args):
        captured.append((message, tool_name, tool_args))

    monkeypatch.setattr(tool_calling_agent_module.logger, "info", fake_info)

    ConsumptionToolCallingAgent._log_tool_calls(
        [
            SimpleNamespace(
                tool_calls=[
                    {"name": "tool_a", "args": {"start_day": "2026-04-01"}},
                    {"name": "tool_b", "args": {"compartment": "lsaetta"}},
                ]
            )
        ]
    )

    assert captured == [
        (
            "Tool call executed | name=%s | args=%s",
            "tool_a",
            {"start_day": "2026-04-01"},
        ),
        (
            "Tool call executed | name=%s | args=%s",
            "tool_b",
            {"compartment": "lsaetta"},
        ),
    ]


def test_log_tool_calls_ignores_messages_without_tool_calls(monkeypatch) -> None:
    captured = []

    def fake_info(*_args):
        captured.append("called")

    monkeypatch.setattr(tool_calling_agent_module.logger, "info", fake_info)

    ConsumptionToolCallingAgent._log_tool_calls(
        [SimpleNamespace(content="no tools"), SimpleNamespace(tool_calls=[])]
    )

    assert captured == []
