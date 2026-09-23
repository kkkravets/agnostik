"""Nebius Token Factory adapter for the Parseltongue LLM pipeline."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from parseltongue.llm.openrouter import OpenRouterProvider

DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


class EmptyToolCallError(RuntimeError):
    """The model answered without a usable tool call; the message says why."""


def _tool_call_hint(finish_reason: str | None, has_text: bool, reasoning_chars: int, truncated_json: bool) -> str:
    if finish_reason == "length":
        return (
            "the reply hit the output-token limit before the tool call was finished"
            + (" (the model spent it on reasoning)" if reasoning_chars else "")
            + ". Raise the limit with --max-output-tokens (for example 32000), or use a smaller input "
            "(--max-documents-per-target, --max-target-chars)."
        )
    if truncated_json:
        return "the tool arguments were cut off or malformed. Retrying may help; a smaller input makes it less likely."
    if has_text:
        return "the model wrote a plain-text answer instead of calling the required tool. Check that the model supports forced function calling."
    return (
        "Nebius returned an empty stream. This usually means the input was too large for the model, "
        "or a transient provider fault. Try a smaller input (--max-documents-per-target, --max-target-chars), or retry."
    )


class NebiusProvider(OpenRouterProvider):
    """Use a Nebius OpenAI-compatible model with Parseltongue.

    Parseltongue normally sends ``tool_choice="required"``. Nebius documents
    forcing a tool by naming it explicitly, so this adapter translates the
    request while retaining Parseltongue's streaming and response parsing.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        reasoning: bool | int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        load_dotenv()
        resolved_api_key = api_key or os.getenv("NEBIUS_API_KEY")
        resolved_model = model or os.getenv("NEBIUS_MODEL")
        resolved_base_url = (
            base_url
            or os.getenv("NEBIUS_BASE_URL")
            or DEFAULT_NEBIUS_BASE_URL
        )

        if not resolved_api_key:
            raise ValueError("NEBIUS_API_KEY is required")
        if not resolved_model:
            raise ValueError("NEBIUS_MODEL is required")

        super().__init__(
            model=resolved_model,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            reasoning=reasoning,
        )
        self._max_output_tokens = max_output_tokens
        self._runner: asyncio.Runner | None = None

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run all passes on one event loop so streamed responses close cleanly."""

        if self._runner is None:
            self._runner = asyncio.Runner()
        try:
            return self._runner.run(self.async_complete(messages, tools, **kwargs))
        except asyncio.CancelledError:
            raise InterruptedError("Request cancelled") from None

    async def async_complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Stream one forced tool call, explaining any reply that carries none.

        Parseltongue's own implementation keeps only the tool-call text, so an
        empty reply surfaces as ``json.loads('')`` with no hint of the cause.
        This mirrors its loop (parseltongue-dsl 0.7.4) and also records why the
        stream ended.
        """

        self._cancelled = False
        self._running_loop = asyncio.get_running_loop()
        self._running_task = asyncio.current_task()
        create_kwargs = self._build_create_kwargs(messages, tools, **kwargs)
        create_kwargs["stream"] = True
        prompt_chars = sum(len(str(message.get("content") or "")) for message in messages)
        try:
            stream = await self._async_client.chat.completions.create(**create_kwargs)
            tool_args, text, reasoning_chars, finish_reason = "", "", 0, None
            try:
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish_reason = getattr(choice, "finish_reason", None) or finish_reason
                    delta = choice.delta
                    if delta.tool_calls:
                        function = delta.tool_calls[0].function
                        if function and function.arguments:
                            tool_args += function.arguments
                    text += getattr(delta, "content", None) or ""
                    reasoning_chars += len(getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or "")
            finally:
                await stream.close()
            try:
                return json.loads(tool_args)
            except json.JSONDecodeError as error:
                snippet = " ".join(text.split())[:200]
                raise EmptyToolCallError(
                    f"Nebius model {create_kwargs.get('model')} returned no usable tool call "
                    f"(finish_reason={finish_reason or 'none'}, {len(tool_args)} tool-argument chars, "
                    f"{reasoning_chars} reasoning chars, prompt ~{prompt_chars} chars"
                    + (f", text reply: {snippet!r}" if snippet else "")
                    + "): "
                    + _tool_call_hint(finish_reason, bool(text.strip()), reasoning_chars, bool(tool_args.strip()))
                ) from error
        finally:
            self._running_loop = None
            self._running_task = None

    def close(self) -> None:
        """Close the shared async HTTP client and its event loop."""

        runner, self._runner = self._runner, None
        if runner is None:
            return
        try:
            runner.run(self._async_client.close())
        finally:
            runner.close()

    def _build_create_kwargs(
        self,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if len(tools) != 1:
            raise ValueError(
                "NebiusProvider expects exactly one Parseltongue tool per pass"
            )

        try:
            function_name = tools[0]["function"]["name"]
        except (KeyError, TypeError) as error:
            raise ValueError("Invalid OpenAI-format tool definition") from error

        create_kwargs = super()._build_create_kwargs(
            list(messages), list(tools), **kwargs
        )
        create_kwargs["tool_choice"] = {
            "type": "function",
            "function": {"name": function_name},
        }
        if self._max_output_tokens:
            # Without this the server's own default cap applies, which a reasoning model can exhaust.
            create_kwargs.setdefault("max_tokens", self._max_output_tokens)
        return create_kwargs


def create_nebius_provider(
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    reasoning: bool | int | None = None,
    max_output_tokens: int | None = None,
) -> NebiusProvider:
    """Build a configured provider for use with ``parseltongue.Pipeline``."""

    return NebiusProvider(
        model=model,
        api_key=api_key,
        base_url=base_url,
        reasoning=reasoning,
        max_output_tokens=max_output_tokens,
    )
