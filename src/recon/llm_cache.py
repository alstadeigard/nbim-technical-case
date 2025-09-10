"""
Lightweight file-backed cache for LLM responses.

Keys are SHA-256 hashes of (provider, model, system, user).
Values are the raw text response returned by the provider.
"""

from __future__ import annotations

import os
import json
import hashlib
from typing import Optional


def _cache_dir() -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    return os.getenv("LLM_CACHE_DIR") or os.path.join(root, ".cache")


def _cache_file() -> str:
    return os.path.join(_cache_dir(), "llm_responses.jsonl")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _key(provider: str, model: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(provider.encode("utf-8"))
    h.update(b"|")
    h.update(model.encode("utf-8"))
    h.update(b"|")
    h.update(system.encode("utf-8"))
    h.update(b"|")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def lookup(provider: str, model: str, system: str, user: str) -> Optional[str]:
    """
    Return cached raw response text if present, else None.
    """
    k = _key(provider, model, system, user)
    path = _cache_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("key") == k:
                    return rec.get("response")
    except Exception:
        return None
    return None


def store(provider: str, model: str, system: str, user: str, response_text: str) -> None:
    """
    Append a cached entry to the JSONL file.
    """
    _ensure_dir(_cache_dir())
    path = _cache_file()
    rec = {
        "key": _key(provider, model, system, user),
        "provider": provider,
        "model": model,
        "response": response_text,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
