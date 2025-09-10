"""
Summary CSV builder for reconciliation results.

This module produces a tidy, one-row-per-event summary suitable for quick review
or spreadsheet analysis. It expects the already-computed artifacts per event:
DiffRecord, risk/policy dict, and classification dict.
"""

from __future__ import annotations

from typing import Dict, List
import pandas as pd

from .schemas import CanonicalEvent, DiffRecord


def _row(
    event: CanonicalEvent,
    diff: DiffRecord,
    risk: Dict[str, object],
    classification: Dict[str, object],
) -> Dict[str, object]:
    """
    Build a single summary row (dict) for the given event.
    """
    break_types = classification.get("break_types", [])
    if isinstance(break_types, list):
        break_types_str = ",".join(break_types)
    else:
        break_types_str = str(break_types)

    return {
        "event_id": event.event_id,
        "isin": event.isin,
        "ex_date": event.ex_date,
        "pay_date": event.pay_date,
        "q_ccy": event.quotation_ccy,
        "s_ccy": event.settlement_ccy,
        "amount_delta_qc": diff.amount_delta_qc,
        "amount_delta_sc": diff.amount_delta_sc,
        "fx_delta": diff.fx_delta,
        "wht_rate_delta_pp": diff.wht_rate_delta,
        "pay_date_offset_days": diff.date_offset_pay_abs_days,
        "shares_delta": diff.share_diff,
        "shares_delta_after_loan": diff.share_diff_after_loan,
        "risk_score": risk.get("risk_score"),
        "require_review": risk.get("require_review"),
        "auto_close": risk.get("auto_close"),
        "break_types": break_types_str,
        "severity": classification.get("severity"),
        "confidence": classification.get("confidence"),
    }


def build_summary_dataframe(
    events: List[CanonicalEvent],
    diffs: List[DiffRecord],
    risks: List[Dict[str, object]],
    classes: List[Dict[str, object]],
) -> pd.DataFrame:
    """
    Build a pandas DataFrame with one row per event from the provided artifacts.
    """
    rows: List[Dict[str, object]] = []
    for ev, d, rp, cls in zip(events, diffs, risks, classes):
        rows.append(_row(ev, d, rp, cls))
    df = pd.DataFrame(rows)
    # Stable column order for readability
    cols = [
        "event_id", "isin", "ex_date", "pay_date", "q_ccy", "s_ccy",
        "amount_delta_qc", "amount_delta_sc", "fx_delta", "wht_rate_delta_pp",
        "pay_date_offset_days", "shares_delta", "shares_delta_after_loan",
        "risk_score", "require_review", "auto_close",
        "break_types", "severity", "confidence",
    ]
    return df[cols]
