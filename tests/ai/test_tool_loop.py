"""Tests for :func:`run_tool_loop` — the OpenAI tool-calling engine.

The OpenAI client is fully stubbed; no network calls happen. The stub
mimics the ``client.chat.completions.create`` interface and returns a
deterministic, scripted sequence of responses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from dbt_builder.src.ai.agents.tool_loop import (
    ToolLoopError,
    ToolSpec,
    run_tool_loop,
)

# ── OpenAI response stubs ──────────────────────────────────────────────────


@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    function: _FakeFunction
    type: str = "function"


@dataclass
class _FakeMessage:
    content: str | None = None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]


class _FakeCompletions:
    def __init__(self, scripted: list[_FakeMessage]) -> None:
        self.scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs) -> _FakeResponse:
        self.calls.append(kwargs)
        if not self.scripted:
            raise AssertionError("No more scripted responses")
        msg = self.scripted.pop(0)
        return _FakeResponse(choices=[_FakeChoice(message=msg)])


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, scripted: list[_FakeMessage]) -> None:
        self._completions = _FakeCompletions(scripted)
        self.chat = _FakeChat(self._completions)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._completions.calls


# ── Helpers ─────────────────────────────────────────────────────────────────


def _tool_call(call_id: str, name: str, args: dict[str, Any]) -> _FakeToolCall:
    return _FakeToolCall(id=call_id, function=_FakeFunction(name=name, arguments=json.dumps(args)))


def _final(content: str) -> _FakeMessage:
    return _FakeMessage(content=content, tool_calls=None)


def _calls(*tcs: _FakeToolCall) -> _FakeMessage:
    return _FakeMessage(content=None, tool_calls=list(tcs))


# ── Tests ──────────────────────────────────────────────────────────────────


def test_returns_immediately_when_no_tool_calls() -> None:
    client = _FakeClient([_final("hello")])
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "hi"}],
        tools=(),
    )
    assert result == "hello"
    assert len(client.calls) == 1


def test_strips_response_format_from_call_kwargs() -> None:
    client = _FakeClient([_final("ok")])
    run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={"response_format": {"type": "json_object"}, "temperature": 1.0},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(),
    )
    assert "response_format" not in client.calls[0]
    assert client.calls[0]["temperature"] == 1.0


def test_executes_registered_tool_and_returns_final() -> None:
    invoked: list[dict[str, Any]] = []

    def handler(**kwargs):
        invoked.append(kwargs)
        return {"sum": kwargs["a"] + kwargs["b"]}

    spec = ToolSpec(
        name="add",
        description="add two ints",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )
    client = _FakeClient(
        [
            _calls(_tool_call("c1", "add", {"a": 2, "b": 3})),
            _final("the answer is 5"),
        ]
    )
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "add 2 + 3"}],
        tools=(spec,),
    )
    assert result == "the answer is 5"
    assert invoked == [{"a": 2, "b": 3}]


def test_executes_multiple_parallel_tool_calls_in_one_round() -> None:
    counter = {"n": 0}

    def t(**kwargs):
        counter["n"] += 1
        return {"ok": True}

    spec = ToolSpec(name="t", description="d", parameters={"type": "object"}, handler=t)
    client = _FakeClient(
        [
            _calls(
                _tool_call("c1", "t", {}),
                _tool_call("c2", "t", {}),
                _tool_call("c3", "t", {}),
            ),
            _final("done"),
        ]
    )
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    assert result == "done"
    assert counter["n"] == 3


def test_unknown_tool_returns_error_to_llm_and_loop_continues() -> None:
    client = _FakeClient(
        [
            _calls(_tool_call("c1", "nope", {})),
            _final("recovered"),
        ]
    )
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(),
    )
    assert result == "recovered"
    # Second turn should include the tool-result message containing the error.
    second_call_msgs = client.calls[1]["messages"]
    tool_msgs = [m for m in second_call_msgs if m.get("role") == "tool"]
    assert tool_msgs
    payload = json.loads(tool_msgs[-1]["content"])
    assert "error" in payload
    assert "Unknown tool" in payload["error"]


def test_handler_exception_is_serialised_and_loop_continues() -> None:
    def boom(**kwargs):
        raise RuntimeError("kaboom")

    spec = ToolSpec(name="boom", description="d", parameters={"type": "object"}, handler=boom)
    client = _FakeClient(
        [
            _calls(_tool_call("c1", "boom", {})),
            _final("handled"),
        ]
    )
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    assert result == "handled"
    tool_msgs = [m for m in client.calls[1]["messages"] if m.get("role") == "tool"]
    payload = json.loads(tool_msgs[-1]["content"])
    assert payload == {"error": "kaboom"}


def test_string_handler_result_is_passed_through_verbatim() -> None:
    def h(**kwargs):
        return "raw-string"

    spec = ToolSpec(name="h", description="d", parameters={"type": "object"}, handler=h)
    client = _FakeClient([_calls(_tool_call("c1", "h", {})), _final("ok")])
    run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    tool_msgs = [m for m in client.calls[1]["messages"] if m.get("role") == "tool"]
    assert tool_msgs[-1]["content"] == "raw-string"


def test_max_rounds_exhausted_raises_tool_loop_error() -> None:
    def h(**kwargs):
        return {"ok": True}

    spec = ToolSpec(name="h", description="d", parameters={"type": "object"}, handler=h)
    # Every round returns a tool-call; the final never arrives.
    looping = [_calls(_tool_call(f"c{i}", "h", {})) for i in range(10)]
    client = _FakeClient(looping)
    with pytest.raises(ToolLoopError):
        run_tool_loop(
            client=client,  # type: ignore[arg-type]
            deployment="gpt-x",
            call_kwargs={},
            initial_messages=[{"role": "user", "content": "x"}],
            tools=(spec,),
            max_rounds=3,
        )
    assert len(client.calls) == 3


def test_tool_defs_are_sent_in_openai_function_format() -> None:
    def h(**kwargs):
        return {}

    spec = ToolSpec(
        name="my_tool",
        description="d",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        handler=h,
    )
    client = _FakeClient([_final("done")])
    run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    tool_defs = client.calls[0]["tools"]
    assert tool_defs == [
        {
            "type": "function",
            "function": {
                "name": "my_tool",
                "description": "d",
                "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
            },
        }
    ]
    assert client.calls[0]["tool_choice"] == "auto"


def test_assistant_tool_call_message_appended_before_tool_results() -> None:
    def h(**kwargs):
        return {"ok": True}

    spec = ToolSpec(name="h", description="d", parameters={"type": "object"}, handler=h)
    client = _FakeClient([_calls(_tool_call("cX", "h", {})), _final("done")])
    run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    msgs = client.calls[1]["messages"]
    # Order: user, assistant(with tool_calls), tool
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["tool_calls"][0]["function"]["name"] == "h"
    assert msgs[2]["role"] == "tool"
    assert msgs[2]["tool_call_id"] == "cX"


def test_empty_arguments_string_is_treated_as_empty_dict() -> None:
    received: dict[str, Any] = {}

    def h(**kwargs):
        received.update(kwargs)
        return {}

    spec = ToolSpec(name="h", description="d", parameters={"type": "object"}, handler=h)
    tc = _FakeToolCall(id="c", function=_FakeFunction(name="h", arguments=""))
    client = _FakeClient([_calls(tc), _final("done")])
    run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(spec,),
    )
    assert received == {}


def test_none_content_returned_as_empty_string() -> None:
    client = _FakeClient([_FakeMessage(content=None, tool_calls=None)])
    result = run_tool_loop(
        client=client,  # type: ignore[arg-type]
        deployment="gpt-x",
        call_kwargs={},
        initial_messages=[{"role": "user", "content": "x"}],
        tools=(),
    )
    assert result == ""
