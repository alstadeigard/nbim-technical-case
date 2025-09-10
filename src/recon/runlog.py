"""
Structured JSONL run logging with traceable run_id and optional redaction.

Creates one JSONL file per run under LOG_DIR (default: ./logs), named:
  logs/run-<run_id>.jsonl

If redact=True, LLM prompts/responses are replaced with placeholders.
"""

from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class RunLogger:
    """
    JSONL logger storing logs for a single run_id. Supports redaction.
    """

    def __init__(self, log_dir: Optional[str] = None, run_id: Optional[str] = None, redact: bool = False) -> None:
        base = log_dir or os.getenv("LOG_DIR")
        if not base:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
            base = os.path.join(root, "logs")
        os.makedirs(base, exist_ok=True)

        self.run_id = run_id or str(uuid.uuid4())
        self.path = os.path.join(base, f"run-{self.run_id}.jsonl")
        self.redact = bool(int(os.getenv("LOG_REDACT", "0"))) or redact

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
        if self.redact:
            system_out = "<redacted:system>"
            user_out = "<redacted:user>"
            resp_out = "<redacted:response>"
        else:
            system_out = system
            user_out = user
            resp_out = response_text

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
                "cost_usd": round(cost_usd, 6),
                "system": system_out,
                "user": user_out,
                "response": resp_out,
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
                "audit_text": audit_text if not self.redact else "<redacted:audit_text>",
                "per_account": per_account,
            },
        )
