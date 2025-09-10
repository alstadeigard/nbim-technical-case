"""
Export utilities for reconciliation results.

This module serializes an event's key artifacts (diffs, classification, risk,
per-account evidence, and audit paragraph) to JSON for downstream use.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional

from .schemas import CanonicalEvent, DiffRecord


def _to_plain(obj: Any) -> Any:
    """
    Convert Pydantic models, dataclasses, and other serializable objects into plain Python types.
    """
    # Pydantic BaseModel has .model_dump(), but we don't depend on it directly;
    # we try common patterns in a safe order.
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # type: ignore[attr-defined]
        except Exception:
            pass
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    return obj


def build_event_payload(
    *,
    event: CanonicalEvent,
    diff: DiffRecord,
    classification: Dict[str, Any],
    risk: Dict[str, Any],
    per_account_rows: Iterable[Dict[str, Any]],
    audit_text: str,
) -> Dict[str, Any]:
    """
    Build a single JSON-serializable payload for a reconciliation event.

    Args:
        event: CanonicalEvent describing NBIM + custody legs.
        diff: Deterministic DiffRecord with numeric deltas.
        classification: Output from recon.classify.classify.
        risk: Output from recon.policy.risk_and_policy.
        per_account_rows: Iterable from recon.attribution.per_account_attribution.
        audit_text: String from recon.audit.generate_audit_paragraph.

    Returns:
        dict ready to be json.dump()'d.
    """
    return {
        "event_id": event.event_id,
        "isin": event.isin,
        "ex_date": event.ex_date,
        "pay_date": event.pay_date,
        "quotation_ccy": event.quotation_ccy,
        "settlement_ccy": event.settlement_ccy,
        "nbim": _to_plain(event.nbim),
        "nbim_accounts": _to_plain(event.nbim_accounts),
        "custody_legs": _to_plain(event.custody_legs),
        "diff": _to_plain(diff),
        "classification": _to_plain(classification),
        "risk": _to_plain(risk),
        "per_account": _to_plain(list(per_account_rows)),
        "audit_text": audit_text,
    }


def write_event_json(path: str, payload: Dict[str, Any]) -> None:
    """
    Write a single event payload to the given file path as UTF-8 JSON.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
