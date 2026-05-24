"""Tool-calling loop engine for the LLM modelling agent.

This module is *model-agnostic*: it drives the standard OpenAI function-calling
protocol (tool_calls → execute → feed back) without knowing anything about
Data Vault.  The modeller injects its own :class:`ToolSpec` instances.

Isolation note
--------------
Only stdlib and typing are imported at module level.  No domain contracts, no
FastAPI, no pydantic.  :class:`ToolSpec` is a stdlib dataclass so the engine
is importable without pydantic installed.

OpenAI compatibility
--------------------
``response_format=json_object`` is **incompatible** with ``tools`` in the
OpenAI API — the endpoint rejects requests that carry both.  :func:`run_tool_loop`
strips ``response_format`` from ``call_kwargs`` automatically before the loop
starts.  The caller decides what to do for the final-answer turn.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AzureOpenAI

_LOG = logging.getLogger(__name__)

_MAX_ROUNDS_DEFAULT: int = 6


class ToolLoopError(RuntimeError):
    """Raised when the loop is exhausted without a final text response."""


@dataclass
class ToolSpec:
    """A single callable tool the LLM may invoke during modelling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object
    handler: Callable[..., Any]


def run_tool_loop(
    *,
    client: AzureOpenAI,
    deployment: str,
    call_kwargs: dict[str, Any],
    initial_messages: list[dict[str, Any]],
    tools: tuple[ToolSpec, ...],
    max_rounds: int = _MAX_ROUNDS_DEFAULT,
) -> str:
    """Run the OpenAI tool-calling loop until the LLM returns a final response.

    Workflow per round
    ------------------
    1. Send ``messages`` with tool definitions to the completions endpoint.
    2. If the response carries ``tool_calls``:

       a. Execute each via the registered handler (errors become JSON error
          objects — the LLM sees them as tool results and can adapt).
       b. Append the assistant message and tool-result messages.
       c. Continue to the next round.

    3. If the response carries ``content`` with no tool calls → return it.
    4. If ``max_rounds`` rounds are exhausted, raise :class:`ToolLoopError`.

    ``response_format`` is stripped from ``call_kwargs`` automatically because
    the OpenAI API rejects it when tools are registered.
    """
    loop_kwargs = {k: v for k, v in call_kwargs.items() if k != "response_format"}

    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]
    registry: dict[str, Callable[..., Any]] = {t.name: t.handler for t in tools}
    msgs: list[dict[str, Any]] = list(initial_messages)

    for round_idx in range(max_rounds):
        response = client.chat.completions.create(
            model=deployment,
            messages=msgs,  # type: ignore[arg-type]
            tools=tool_defs,  # type: ignore[arg-type]
            tool_choice="auto",
            **loop_kwargs,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            _LOG.debug("Tool loop finished after %d round(s)", round_idx + 1)
            return (msg.content or "").strip()

        tool_call_dicts = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
        msgs.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": tool_call_dicts,
            }
        )

        for tc in msg.tool_calls:
            handler = registry.get(tc.function.name)
            if handler is None:
                result_str = json.dumps({"error": f"Unknown tool: {tc.function.name!r}"})
                _LOG.warning("LLM requested unknown tool %r", tc.function.name)
            else:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = handler(**args)
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as exc:
                    result_str = json.dumps({"error": str(exc)})
                    _LOG.warning("Tool %r raised: %s", tc.function.name, exc)

            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result_str})

    raise ToolLoopError(
        f"Tool loop exhausted {max_rounds} rounds without a final response "
        f"for deployment {deployment!r}."
    )
