"""
Thin LLM client wrapper supporting OpenAI or Anthropic, selected via flags/env.

Provider selection (by preference order):
- CLI flags in run_local.py (provider/model) if passed.
- Environment variables:
    LLM_PROVIDER = "openai" | "anthropic"
    OPENAI_API_KEY / ANTHROPIC_API_KEY for credentials
    LLM_MODEL for default model name if not passed via CLI.

This module performs no retries or batching; upstream code should handle fallbacks.
"""

from __future__ import annotations

import os
from typing import Optional


class LLMClient:
    """
    Minimal client that hides provider SDK differences. Returns raw text.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER") or "openai").lower()
        self.model = model or os.getenv("LLM_MODEL") or (
            "gpt-4o-mini" if self.provider == "openai" else "claude-3-haiku-20240307"
        )

    def classify_json(self, system: str, user: str, max_tokens: int = 800) -> str:
        """
        Send a classification prompt and return the raw text. Caller parses/validates JSON.
        """
        if self.provider == "openai":
            return self._openai_chat(system, user, max_tokens)
        elif self.provider == "anthropic":
            return self._anthropic_messages(system, user, max_tokens)
        raise RuntimeError(f"Unsupported provider: {self.provider}")

    def _openai_chat(self, system: str, user: str, max_tokens: int) -> str:
        """
        OpenAI Chat Completions compatible call. Requires `openai` package >= 1.0.
        """
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "OpenAI SDK not installed. `pip install openai` or switch provider."
            ) from e

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set.")

        client = OpenAI()
        # Prefer JSON mode if supported by the model; otherwise rely on instruction-only JSON.
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content or ""
        except Exception:
            # Fallback: no response_format (older models)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""

    def _anthropic_messages(self, system: str, user: str, max_tokens: int) -> str:
        """
        Anthropic Messages API. Requires `anthropic` package.
        """
        try:
            import anthropic  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Anthropic SDK not installed. `pip install anthropic` or switch provider."
            ) from e

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.model,
            temperature=0.0,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text segments
        chunks = []
        for block in resp.content or []:
            if getattr(block, "type", None) == "text":
                chunks.append(getattr(block, "text", ""))
        return "".join(chunks)
