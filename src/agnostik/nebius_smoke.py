"""Live smoke test for the Nebius/Parseltongue provider connection."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from agnostik.nebius import create_nebius_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agnostik-nebius-smoke",
        description="Verify Nebius authentication and forced tool calling.",
    )
    parser.add_argument(
        "--model",
        help="Nebius model ID; defaults to NEBIUS_MODEL",
    )
    parser.add_argument(
        "--base-url",
        help="API base URL; defaults to NEBIUS_BASE_URL or Token Factory",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = create_nebius_provider(model=args.model, base_url=args.base_url)
    result = provider.complete(
        messages=[
            {
                "role": "user",
                "content": "Call the connectivity_check function with status ok.",
            }
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "connectivity_check",
                    "description": "Return the status of this connectivity check.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["ok"]}
                        },
                        "required": ["status"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        temperature=0,
    )

    if result.get("status") != "ok":
        raise RuntimeError(f"Unexpected tool response: {result!r}")

    print(json.dumps({"connected": True, "tool_result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
