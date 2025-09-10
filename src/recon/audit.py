"""
Simple deterministic audit text generator for reconciliation results.
"""

from typing import List
from .schemas import CanonicalEvent, DiffRecord


def _fmt_ccy_pair(quotation: str, settlement: str) -> str:
    """
    Return a compact currency pair string like 'USD→USD' or 'KRW→USD'.
    """
    q = (quotation or "").strip()
    s = (settlement or "").strip()
    if not q and not s:
        return ""
    return f"{q}→{s}" if q and s else q or s


def generate_audit_paragraph(event: CanonicalEvent, diff: DiffRecord) -> str:
    """
    Generate a concise, human-readable audit paragraph for a single event.

    Rules:
      - Always state the event and currency context.
      - Report amount deltas (QC and SC) when non-zero.
      - Explain share delta; if lending fully explains, call it out explicitly.
      - Note FX and tax differences when present.
      - Mention payment-date offset if non-zero.
    """
    parts: List[str] = []

    # Header
    cpair = _fmt_ccy_pair(event.quotation_ccy, event.settlement_ccy)
    parts.append(
        f"Event {event.event_id} (ISIN {event.isin}, {cpair}) reconciliation summary:"
    )

    # Amount deltas
    if abs(diff.amount_delta_qc) > 0:
        parts.append(
            f"Amount delta in quotation currency: {diff.amount_delta_qc:,.2f}."
        )
    if abs(diff.amount_delta_sc) > 0:
        parts.append(
            f"Amount delta in settlement currency: {diff.amount_delta_sc:,.2f}."
        )
    if abs(diff.amount_delta_qc) == 0 and abs(diff.amount_delta_sc) == 0:
        parts.append("No amount deltas detected.")

    # Shares and lending
    if abs(diff.share_diff_after_loan) < 1e-9 and abs(diff.share_diff) > 1e-9:
        parts.append(
            f"Custody share difference of {diff.share_diff:,.0f} is fully explained by lending "
            f"(loan total {diff.loan_total:,.0f}); loan-adjusted share delta is 0."
        )
    elif abs(diff.share_diff_after_loan) > 1e-9:
        parts.append(
            f"Share delta of {diff.share_diff:,.0f} (loan-adjusted {diff.share_diff_after_loan:,.0f}); "
            f"loan total {diff.loan_total:,.0f}."
        )
    else:
        parts.append("No share delta after lending adjustment.")

    # FX
    if abs(diff.fx_delta) > 1e-9:
        parts.append(f"Implied FX delta: {diff.fx_delta:.6f}.")
    else:
        parts.append("No implied FX difference.")

    # Tax
    if abs(diff.wht_rate_delta) > 1e-9:
        parts.append(f"Withholding tax rate delta: {diff.wht_rate_delta:.2f} pp.")
    else:
        parts.append("No withholding tax rate difference.")

    # Payment date
    if diff.date_offset_pay_abs_days != 0:
        parts.append(f"Payment date offset: {diff.date_offset_pay_abs_days} day(s).")

    return " ".join(parts)
