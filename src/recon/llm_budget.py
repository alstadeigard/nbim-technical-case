"""
Simple budget guard for LLM usage.

Estimates cost using character-count heuristics unless explicit token counts
are provided by the caller. Tracks cumulative spend in a JSON file.
"""

from __future__ import annotations

import os
import json
from typing import Tuple


def _usage_path() -> str:
    env_path = os.getenv("LLM_USAGE_PATH")
    if env_path:
        return env_path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    cache_dir = os.getenv("LLM_CACHE_DIR") or os.path.join(root, ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "llm_usage.json")


def _load_usage() -> dict:
    path = _usage_path()
    if not os.path.exists(path):
        return {"total_usd": 0.0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"total_usd": 0.0}


def _save_usage(data: dict) -> None:
    path = _usage_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def budget_usd() -> float:
    val = os.getenv("LLM_BUDGET_USD")
    if not val:
        return 50.0
    try:
        return float(val)
    except Exception:
        return 50.0


def prices_per_1k(provider: str, model: str) -> Tuple[float, float]:
    """
    Returns (input_per_1k_usd, output_per_1k_usd).
    Defaults are conservative; override via env:
      LLM_INPUT_COST_PER_1K, LLM_OUTPUT_COST_PER_1K
    """
    env_in = os.getenv("LLM_INPUT_COST_PER_1K")
    env_out = os.getenv("LLM_OUTPUT_COST_PER_1K")
    if env_in and env_out:
        try:
            return float(env_in), float(env_out)
        except Exception:
            pass

    # Conservative defaults for lightweight models; user can override via env.
    return (0.01, 0.03)


def estimate_tokens_from_text(text: str) -> int:
    """
    Rough token estimate using 4 chars per token heuristic.
    """
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def estimate_cost_usd(provider: str, model: str, in_tokens: int, out_tokens: int) -> float:
    in_per, out_per = prices_per_1k(provider, model)
    return (in_tokens / 1000.0) * in_per + (out_tokens / 1000.0) * out_per


def can_spend(amount_usd: float) -> bool:
    usage = _load_usage()
    return usage.get("total_usd", 0.0) + amount_usd <= budget_usd()


def record_spend(amount_usd: float) -> None:
    usage = _load_usage()
    usage["total_usd"] = float(usage.get("total_usd", 0.0)) + float(amount_usd)
    _save_usage(usage)
