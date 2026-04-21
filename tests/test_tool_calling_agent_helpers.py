"""
Author: L. Saetta
Date last modified: 2026-04-21
License: MIT
Description: Unit tests for tool-calling agent helper methods.
"""

from types import SimpleNamespace

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
