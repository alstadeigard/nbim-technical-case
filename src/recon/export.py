"""
Export utilities: build a structured per-event JSON payload and write to disk.

This version is robust to slight schema naming differences across NBIMLeg/CustodyLeg,
using getattr fallbacks (e.g., shares vs holding_quantity, gross_qc vs gross_amount).
"""

from __future__ import annotations

import json
from typing import Dict, Any, Iterable, Optional

from .schemas import CanonicalEvent, DiffRecord


def _coerce_float(val: object, default: float = 0.0) -> float:
    try:
        return float(val)  # type: ignore[call-arg]
    except Exception:
        return float(default)


def _coerce_int(val: object, default: int = 0) -> int:
    try:
        return int(val)  # type: ignore[call-arg]
    except Exception:
        try:
            return int(float(val))  # for numeric strings
        except Exception:
            return int(default)


def _nbim_accounts_rows(event: CanonicalEvent) -> list[dict[str, Any]]:
    """
    Flatten NBIM per-account legs for export.

    NBIMLeg known attrs (from this project):
      - bank_account, shares, gross_qc, net_qc, net_sc
    """
    rows: list[dict[str, Any]] = []
    for acct in event.nbim_accounts:
        shares = getattr(acct, "shares", 0)
        gross_qc = getattr(acct, "gross_qc", getattr(acct, "gross_amount_qc", 0.0))
        net_qc = getattr(acct, "net_qc", getattr(acct, "net_amount_qc", 0.0))
        net_sc = getattr(acct, "net_sc", getattr(acct, "net_amount_sc", 0.0))
        rows.append(
            {
                "bank_account": getattr(acct, "bank_account", None),
                "shares": _coerce_float(shares),
                "gross_qc": _coerce_float(gross_qc),
                "net_qc": _coerce_float(net_qc),
                "net_sc": _coerce_float(net_sc),
            }
        )
    return rows


def _custody_legs_rows(event: CanonicalEvent) -> list[dict[str, Any]]:
    """
    Flatten custody legs for export.

    CustodyLeg known attrs (from this project):
      - bank_account
      - shares (or holding_quantity)
      - loan_quantity
      - gross_amount (gross in quotation ccy)
      - net_amount_qc
      - tax
      - net_amount_sc
      - fx_rate
      - pay_date
    """
    rows: list[dict[str, Any]] = []
    for leg in event.custody_legs:
        shares = getattr(leg, "shares", getattr(leg, "holding_quantity", 0))
        gross_qc = getattr(leg, "gross_qc", getattr(leg, "gross_amount", 0.0))
        net_qc = getattr(leg, "net_qc", getattr(leg, "net_amount_qc", 0.0))
        net_sc = getattr(leg, "net_sc", getattr(leg, "net_amount_sc", 0.0))
        tax_qc = getattr(leg, "tax_qc", getattr(leg, "tax", 0.0))
        fx = getattr(leg, "fx", getattr(leg, "fx_rate", 1.0))
        rows.append(
            {
                "bank_account": getattr(leg, "bank_account", None),
                "shares": _coerce_float(shares),
                "loan_quantity": _coerce_float(getattr(leg, "loan_quantity", 0.0)),
                "gross_qc": _coerce_float(gross_qc),
                "net_qc": _coerce_float(net_qc),
                "tax_qc": _coerce_float(tax_qc),
                "net_sc": _coerce_float(net_sc),
                "fx": _coerce_float(fx, 1.0),
                "pay_date": getattr(leg, "pay_date", None),
            }
        )
    return rows


def _per_account_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize per-account attribution rows from attribution.per_account_attribution(...)
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "bank_account": r.get("bank_account"),
                "nbim_shares": _coerce_int(r.get("nbim_shares", 0)),
                "custody_shares": _coerce_int(r.get("custody_shares", 0)),
                "share_delta": _coerce_int(r.get("share_delta", 0)),
                "nbim_net_qc": _coerce_float(r.get("nbim_net_qc", 0.0)),
                "custody_net_qc": _coerce_float(r.get("custody_net_qc", 0.0)),
                "net_qc_delta": _coerce_float(r.get("net_qc_delta", 0.0)),
                "nbim_net_sc": _coerce_float(r.get("nbim_net_sc", 0.0)),
                "custody_net_sc": _coerce_float(r.get("custody_net_sc", 0.0)),
                "net_sc_delta": _coerce_float(r.get("net_sc_delta", 0.0)),
            }
        )
    return out


def build_event_payload(
    *,
    event: CanonicalEvent,
    diff: DiffRecord,
    classification: Dict[str, Any],
    risk: Dict[str, Any],
    per_account_rows: Iterable[Dict[str, Any]],
    audit_text: str,
    actions: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Build a serializable dict that captures event inputs, diffs, classification,
    risk flags, per-account attribution, audit narrative, and remediation actions.
    """
    nbim_gross_qc = getattr(event.nbim, "gross_qc", getattr(event.nbim, "gross_amount_qc", 0.0))
    nbim_net_qc = getattr(event.nbim, "net_qc", getattr(event.nbim, "net_amount_qc", 0.0))
    nbim_net_sc = getattr(event.nbim, "net_sc", getattr(event.nbim, "net_amount_sc", 0.0))

    payload: Dict[str, Any] = {
        "event_id": event.event_id,
        "isin": event.isin,
        "ex_date": event.ex_date,
        "pay_date": event.pay_date,
        "quotation_ccy": event.quotation_ccy,
        "settlement_ccy": event.settlement_ccy,
        "nbim": {
            "shares": _coerce_float(getattr(event.nbim, "shares", 0.0)),
            "div_per_share": _coerce_float(getattr(event.nbim, "div_per_share", 0.0)),
            "gross_qc": _coerce_float(nbim_gross_qc),
            "net_qc": _coerce_float(nbim_net_qc),
            "net_sc": _coerce_float(nbim_net_sc),
            "wht_rate": _coerce_float(getattr(event.nbim, "wht_rate", 0.0)),
            "fx_used": _coerce_float(getattr(event.nbim, "fx_used", 1.0), 1.0),
        },
        "nbim_accounts": _nbim_accounts_rows(event),
        "custody_legs": _custody_legs_rows(event),
        "diff": {
            "event_id": event.event_id,
            "amount_delta_qc": _coerce_float(diff.amount_delta_qc),
            "amount_delta_sc": _coerce_float(diff.amount_delta_sc),
            "wht_rate_delta": _coerce_float(diff.wht_rate_delta),
            "fx_delta": _coerce_float(diff.fx_delta),
            "date_offset_pay_abs_days": _coerce_int(diff.date_offset_pay_abs_days),
            "share_diff": _coerce_float(diff.share_diff),
            "loan_total": _coerce_float(diff.loan_total),
            "share_diff_after_loan": _coerce_float(diff.share_diff_after_loan),
        },
        "classification": {
            "break_types": list(classification.get("break_types", [])),
            "severity": str(classification.get("severity")),
            "hypothesized_causes": list(classification.get("hypothesized_causes", [])),
            "confidence": _coerce_float(classification.get("confidence", 0.0)),
        },
        "risk": {
            "risk_score": _coerce_float(risk.get("risk_score", 0.0)),
            "require_review": bool(risk.get("require_review", False)),
            "auto_close": bool(risk.get("auto_close", False)),
        },
        "per_account": _per_account_rows(per_account_rows),
        "audit_text": audit_text,
        "remediation": {
            "actions": list(actions or []),
        },
    }
    return payload


def write_event_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
