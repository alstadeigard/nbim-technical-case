"""
Structured JSONL run logging with traceable run_id and per-event records.

Creates one JSONL file per run under LOG_DIR (default: ./logs), named:
  logs/run-<run_id>.jsonl

Each line is a JSON object with at least:
  - ts: ISO8601 timestamp (UTC)
  - run_id: stable id for the run
  - stage: short tag (e.g., "run_start", "llm_classify", "event_summary")
  - payload: dict with structured content for that stage
"""

from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class RunLogger:
    """
    JSONL logger storing logs for a single run_id. Thread-safe enough for CLI usage.
    """

    def __init__(self, log_dir: Optional[str] = None, run_id: Optional[str] = None) -> None:
        base = log_dir or os.getenv("LOG_DIR")
        if not base:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
            base = os.path.join(root, "logs")
        os.makedirs(base, exist_ok=True)

        self.run_id = run_id or str(uuid.uuid4())
        self.path = os.path.join(base, f"run-{self.run_id}.jsonl")

        # Create the file on init for discoverability.
        with open(self.path, "a", encoding="utf-8"):
            pass

    def _ts(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log(self, stage: str, payload: Dict[str, Any]) -> None:
        rec = {
            "ts": self._ts(),
            "run_id": self.run_id,
            "stage": stage,
            "payload": payload,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log_run_start(self, args: Dict[str, Any]) -> None:
        self.log("run_start", {"args": args})

    def log_llm_classify(
        self,
        *,
        provider: str,
        model: str,
        system: str,
        user: str,
        response_text: str,
        cache_hit: bool,
        budget_blocked: bool,
        est_in_tokens: int,
        out_tokens: int,
        cost_usd: float,
        event_id: Optional[str] = None,
    ) -> None:
        self.log(
            "llm_classify",
            {
                "event_id": event_id,
                "provider": provider,
                "model": model,
                "cache_hit": cache_hit,
                "budget_blocked": budget_blocked,
                "est_in_tokens": est_in_tokens,
                "out_tokens": out_tokens,
                "cost_usd": cost_usd,
                "system": system,
                "user": user,
                "response": response_text,
            },
        )

    def log_event_summary(
        self,
        *,
        event_id: str,
        diff: Dict[str, Any],
        risk: Dict[str, Any],
        classification: Dict[str, Any],
        actions: list[str],
        audit_text: str,
        per_account: list[Dict[str, Any]],
    ) -> None:
        self.log(
            "event_summary",
            {
                "event_id": event_id,
                "diff": diff,
                "risk": risk,
                "classification": classification,
                "actions": actions,
                "audit_text": audit_text,
                "per_account": per_account,
            },
        )
