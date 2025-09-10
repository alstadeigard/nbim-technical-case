"""
LLM-backed classification with schema validation, caching, budget guard,
structured logging, and deterministic fallback.
"""

from __future__ import annotations

import json
from typing import Dict, Iterable, Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from .schemas import CanonicalEvent, DiffRecord
from .prompts import build_classify_messages, classification_schema_json  # noqa: F401
from .llm_client import LLMClient
from .classify import classify as classify_rules
from . import llm_cache
from . import llm_budget
from .runlog import RunLogger


class _ClassifyOut(BaseModel):
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


def _fallback(diff: DiffRecord) -> Dict[str, object]:
    return classify_rules(diff)


def classify_llm(
    *,
    event: CanonicalEvent,
    diff: DiffRecord,
    per_account_rows: Iterable[Dict[str, Any]],
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int = 800,
    run_logger: Optional[RunLogger] = None,
) -> Dict[str, object]:
    """
    Invoke an LLM to classify reconciliation breaks using cache/budget and log details.
    Falls back to deterministic rules on any error or budget block.
    """
    try:
        msgs = build_classify_messages(
            event_meta=_event_meta(event),
            diff_summary=_diff_summary(diff),
            per_account_rows=per_account_rows,
        )
        prov = (provider or "openai").lower()
        mdl = model or "gpt-4o-mini"

        cached = llm_cache.lookup(prov, mdl, msgs["system"], msgs["user"])
        if cached is not None:
            try:
                data = json.loads(cached or "{}")
                out = _ClassifyOut.model_validate(data)
                result = {
                    "break_types": out.break_types or (["Amount_delta_unexplained"] if abs(diff.amount_delta_sc) > 0 else ["No_break_detected"]),
                    "severity": out.severity,
                    "hypothesized_causes": out.hypothesized_causes,
                    "confidence": round(float(out.confidence), 2),
                }
                if run_logger:
                    run_logger.log_llm_classify(
                        provider=prov,
                        model=mdl,
                        system=msgs["system"],
                        user=msgs["user"],
                        response_text=cached,
                        cache_hit=True,
                        budget_blocked=False,
                        est_in_tokens=llm_budget.estimate_tokens_from_text(msgs["system"])
                        + llm_budget.estimate_tokens_from_text(msgs["user"]),
                        out_tokens=max(1, int(len(cached) / 4)),
                        cost_usd=0.0,
                        event_id=event.event_id,
                    )
                return result
            except Exception:
                pass

        est_in = llm_budget.estimate_tokens_from_text(msgs["system"]) + llm_budget.estimate_tokens_from_text(msgs["user"])
        est_out = 300
        est_cost = llm_budget.estimate_cost_usd(prov, mdl, est_in, est_out)
        if not llm_budget.can_spend(est_cost):
            if run_logger:
                run_logger.log_llm_classify(
                    provider=prov,
                    model=mdl,
                    system=msgs["system"],
                    user=msgs["user"],
                    response_text="",
                    cache_hit=False,
                    budget_blocked=True,
                    est_in_tokens=est_in,
                    out_tokens=0,
                    cost_usd=0.0,
                    event_id=event.event_id,
                )
            return _fallback(diff)

        client = LLMClient(provider=prov, model=mdl)
        raw = client.classify_json(system=msgs["system"], user=msgs["user"], max_tokens=max_tokens)

        out_tokens = max(1, int(len(raw) / 4))
        call_cost = llm_budget.estimate_cost_usd(prov, mdl, est_in, out_tokens)
        llm_budget.record_spend(call_cost)

        llm_cache.store(prov, mdl, msgs["system"], msgs["user"], raw)

        data = json.loads(raw or "{}")
        out = _ClassifyOut.model_validate(data)

        result = {
            "break_types": out.break_types or (["Amount_delta_unexplained"] if abs(diff.amount_delta_sc) > 0 else ["No_break_detected"]),
            "severity": out.severity,
            "hypothesized_causes": out.hypothesized_causes,
            "confidence": round(float(out.confidence), 2),
        }

        if run_logger:
            run_logger.log_llm_classify(
                provider=prov,
                model=mdl,
                system=msgs["system"],
                user=msgs["user"],
                response_text=raw,
                cache_hit=False,
                budget_blocked=False,
                est_in_tokens=est_in,
                out_tokens=out_tokens,
                cost_usd=call_cost,
                event_id=event.event_id,
            )

        return result

    except (ValidationError, json.JSONDecodeError, RuntimeError, Exception):
        return _fallback(diff)
