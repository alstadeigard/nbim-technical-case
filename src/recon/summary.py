"""
Summary CSV builder for reconciliation results.

Produces a tidy, one-row-per-event summary and applies sensible rounding so the CSV
is easy to read (no scientific notation, consistent decimal places). Also normalizes
signed zero values like -0.0 to 0.0.
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
    
    Args:
        event: CanonicalEvent object
        diff: DiffRecord object
        risk: Risk assessment results
        classification: Classification results
        
    Returns:
        Dictionary representing a single row in the summary DataFrame
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
        "amount_delta_qc": float(diff.amount_delta_qc),
        "amount_delta_sc": float(diff.amount_delta_sc),
        "fx_delta": float(diff.fx_delta),
        "wht_rate_delta_pp": float(diff.wht_rate_delta),
        "pay_date_offset_days": int(diff.date_offset_pay_abs_days),
        "shares_delta": float(diff.share_diff),
        "shares_delta_after_loan": float(diff.share_diff_after_loan),
        "risk_score": float(risk.get("risk_score", 0.0)),
        "require_review": bool(risk.get("require_review", False)),
        "auto_close": bool(risk.get("auto_close", False)),
        "break_types": break_types_str,
        "severity": str(classification.get("severity")),
        "confidence": float(classification.get("confidence", 0.0)),
    }


def build_summary_dataframe(
    events: List[CanonicalEvent],
    diffs: List[DiffRecord],
    risks: List[Dict[str, object]],
    classes: List[Dict[str, object]],
) -> pd.DataFrame:
    """
    Build a pandas DataFrame with one row per event and apply consistent rounding.

    Rounding policy:
      - Money deltas (QC/SC): 2 decimals
      - FX delta: 6 decimals
      - WHT delta (pp): 2 decimals
      - Shares deltas: integer
      - Risk score & confidence: 2 decimals
      - Day offsets: integer

    Also normalizes any signed zero (e.g., -0.0) to 0.0 in float columns.
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
    df = df[cols]

    # Apply rounding/casting
    round_map = {
        "amount_delta_qc": 2,
        "amount_delta_sc": 2,
        "fx_delta": 6,
        "wht_rate_delta_pp": 2,
        "risk_score": 2,
        "confidence": 2,
    }
    df = df.copy()

    for col, ndp in round_map.items():
        if col in df.columns:
            df[col] = df[col].round(ndp)

    # Shares and day offsets as integers
    if "shares_delta" in df.columns:
        df["shares_delta"] = df["shares_delta"].round(0).astype(int)
    if "shares_delta_after_loan" in df.columns:
        df["shares_delta_after_loan"] = df["shares_delta_after_loan"].round(0).astype(int)
    if "pay_date_offset_days" in df.columns:
        df["pay_date_offset_days"] = df["pay_date_offset_days"].astype(int)

    # Normalize signed zeros in float columns (e.g., convert -0.0 to 0.0)
    float_cols = [
        "amount_delta_qc", "amount_delta_sc", "fx_delta",
        "wht_rate_delta_pp", "risk_score", "confidence",
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: 0.0 if isinstance(v, float) and v == 0.0 else v)

    return df
