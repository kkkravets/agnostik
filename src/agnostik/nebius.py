"""Nebius Token Factory adapter for the Parseltongue LLM pipeline."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from parseltongue.llm.openrouter import OpenRouterProvider

DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


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
        return create_kwargs


def create_nebius_provider(
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    reasoning: bool | int | None = None,
) -> NebiusProvider:
    """Build a configured provider for use with ``parseltongue.Pipeline``."""

    return NebiusProvider(
        model=model,
        api_key=api_key,
        base_url=base_url,
        reasoning=reasoning,
    )
