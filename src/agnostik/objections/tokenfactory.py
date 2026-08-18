"""Nebius Token Factory client — OpenAI-compatible chat completions.

Zero dependencies: the whole call is one JSON POST, so the tool runs
anywhere python does. Credentials come from the environment only; the key
is never logged, echoed or written into any report.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

__all__ = [
    "TokenFactory",
    "TokenFactoryError",
    "Completion",
    "DEFAULT_MODEL",
    "DEFAULT_BASE_URL",
    "env_model",
    "find_key",
]

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL = "MiniMaxAI/MiniMax-M3"
KEY_VARS = ("TOKENFACTORY_TOKEN", "NEBIUS_API_KEY", "TOKEN_FACTORY_API_KEY")
BASE_URL_VARS = ("TOKENFACTORY_BASE_URL", "NEBIUS_BASE_URL")
MODEL_VARS = ("TOKENFACTORY_MODEL", "NEBIUS_MODEL")


def _load_dotenv_if_available() -> None:
    """Pick up a .env the way the rest of the workspace does, if dotenv is installed."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
    except ImportError:
        return
    load_dotenv()


def _from_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def env_model(default: str = DEFAULT_MODEL) -> str:
    """Model id from the environment, falling back to the verified default."""
    _load_dotenv_if_available()
    return _from_env(MODEL_VARS) or default


class TokenFactoryError(RuntimeError):
    pass


@dataclass
class Completion:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = ""
    latency_s: float = 0.0

    def to_json(self) -> dict:
        return {
            "model": self.model,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_s": round(self.latency_s, 2),
        }


def find_key() -> str | None:
    """API key from the environment. Never read from a CLI flag or a file."""
    _load_dotenv_if_available()
    return _from_env(KEY_VARS)


class TokenFactory:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = "",
        api_key: str | None = None,
        timeout: int = 180,
        max_retries: int = 3,
    ) -> None:
        _load_dotenv_if_available()
        self.model = model or env_model()
        self.base_url = (base_url or _from_env(BASE_URL_VARS) or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or find_key()
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _post(self, path: str, payload: dict) -> dict:
        if not self.api_key:
            raise TokenFactoryError(
                "no API key: set TOKENFACTORY_TOKEN (or NEBIUS_API_KEY in .env). "
                "Keys live at https://tokenfactory.nebius.com/project/api-keys — "
                "or run with --dry-run to build prompts without calling the model."
            )
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "objection-forge/0.1",
            },
            method="POST",
        )
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="replace")[:400]
                if exc.code in (401, 403):
                    raise TokenFactoryError(f"Token Factory rejected the key ({exc.code}): {body}") from exc
                if exc.code == 404:
                    raise TokenFactoryError(
                        f"model or endpoint not found ({exc.code}): {body}. "
                        "Model ids drift — list the live catalogue before trusting a doc."
                    ) from exc
                last = TokenFactoryError(f"HTTP {exc.code}: {body}")
                if exc.code not in (408, 409, 429, 500, 502, 503, 504):
                    raise last from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = TokenFactoryError(f"{type(exc).__name__}: {exc}")
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)
        raise last or TokenFactoryError("request failed")

    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2500,
        seed: int | None = 7,
    ) -> Completion:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        started = time.time()
        data = self._post("/chat/completions", payload)
        elapsed = time.time() - started
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
            finish = choice.get("finish_reason", "")
        except (KeyError, IndexError, TypeError) as exc:
            raise TokenFactoryError(f"unexpected response shape: {json.dumps(data)[:300]}") from exc
        usage = data.get("usage") or {}
        return Completion(
            text=text.strip(),
            model=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            finish_reason=finish,
            latency_s=elapsed,
        )

    def list_models(self) -> list[str]:
        if not self.api_key:
            raise TokenFactoryError("no API key: set TOKENFACTORY_TOKEN")
        req = urllib.request.Request(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "objection-forge/0.1"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode())
        return sorted(m.get("id", "") for m in data.get("data", []))
