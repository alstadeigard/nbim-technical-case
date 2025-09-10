"""
LLM-backed classification with schema validation and deterministic fallback.

Exports a single function `classify_llm(...)` that returns the same JSON shape as
the rule-based `classify(...)` function: break_types, severity, hypothesized_causes, confidence.
"""

from __future__ import annotations

import json
from typing import Dict, Iterable, Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from .schemas import CanonicalEvent, DiffRecord
from .prompts import build_classify_messages, classification_schema_json
from .llm_client import LLMClient
from .classify import classify as classify_rules


class _ClassifyOut(BaseModel):
    """
    Pydantic model ensuring the LLM output conforms to our expected JSON shape.
    """
    break_types: list[str] = Field(default_factory=list)
    severity: str
    hypothesized_causes: list[str] = Field(default_factory=list)
    confidence: float

    @field_validator("severity")
    @classmethod
    def _sev_ok(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v

    @field_validator("confidence")
    @classmethod
    def _conf_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be within [0,1]")
        return v


def _event_meta(ev: CanonicalEvent) -> Dict[str, str]:
    return {
        "event_id": ev.event_id,
        "isin": ev.isin,
        "quotation_ccy": ev.quotation_ccy,
        "settlement_ccy": ev.settlement_ccy,
        "pay_date": ev.pay_date,
        "ex_date": ev.ex_date,
    }


def _diff_summary(d: DiffRecord) -> Dict[str, float | int]:
    return {
        "amount_delta_qc": float(d.amount_delta_qc),
        "amount_delta_sc": float(d.amount_delta_sc),
        "fx_delta": float(d.fx_delta),
        "wht_rate_delta_pp": float(d.wht_rate_delta),
        "pay_date_offset_days": int(d.date_offset_pay_abs_days),
        "shares_delta": float(d.share_diff),
        "shares_delta_after_loan": float(d.share_diff_after_loan),
    }


def classify_llm(
    *,
    event: CanonicalEvent,
    diff: DiffRecord,
    per_account_rows: Iterable[Dict[str, Any]],
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 800,
) -> Dict[str, object]:
    """
    Invoke an LLM to classify reconciliation breaks. On error, fall back to rules.

    Returns:
        dict with keys:
          - break_types: List[str]
          - severity: "low" | "medium" | "high"
          - hypothesized_causes: List[str]
          - confidence: float
    """
    try:
        msgs = build_classify_messages(
            event_meta=_event_meta(event),
            diff_summary=_diff_summary(diff),
            per_account_rows=per_account_rows,
        )
        client = LLMClient(provider=provider, model=model)
        raw = client.classify_json(system=msgs["system"], user=msgs["user"], max_tokens=max_tokens)

        data = json.loads(raw or "{}")
        out = _ClassifyOut.model_validate(data)

        return {
            "break_types": out.break_types or ["Amount_delta_unexplained"]
                if abs(diff.amount_delta_sc) > 0 else ["No_break_detected"],
            "severity": out.severity,
            "hypothesized_causes": out.hypothesized_causes,
            "confidence": round(float(out.confidence), 2),
        }
    except (ValidationError, json.JSONDecodeError, RuntimeError, Exception):
        # Fallback: rule-based classifier
        return classify_rules(diff)
