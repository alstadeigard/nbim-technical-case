"""
Deterministic audit text generator for reconciliation results.

This module produces a concise paragraph for each event, including:
- Amount deltas in quotation/settlement currency
- Share deltas (and lending explanation)
- FX and tax differences
- Payment-date offsets
- Per-account evidence lines (which account drives the break)
"""

from typing import List, Iterable, Dict, Optional
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


def _format_account_evidence(rows: Iterable[Dict[str, object]]) -> Optional[str]:
    """
    Render per-account evidence lines, but only include accounts with any non-zero deltas.

    Each line looks like:
      [acct] SharesΔ=..., QCΔ=..., SCΔ=...
    """
    lines: List[str] = []
    for r in rows:
        share_delta = float(r.get("share_delta", 0.0))
        qc_delta = float(r.get("net_qc_delta", 0.0))
        sc_delta = float(r.get("net_sc_delta", 0.0))
        if abs(share_delta) > 0.0 or abs(qc_delta) > 0.0 or abs(sc_delta) > 0.0:
            acct = (r.get("bank_account") or "(blank)")
            lines.append(
                f"[{acct}] SharesΔ={share_delta:,.0f}, QCΔ={qc_delta:,.2f}, SCΔ={sc_delta:,.2f}"
            )
    if not lines:
        return None
    return "Evidence by account: " + " | ".join(lines)


def generate_audit_paragraph(
    event: CanonicalEvent,
    diff: DiffRecord,
    account_rows: Optional[Iterable[Dict[str, object]]] = None
) -> str:
    """
    Generate a concise, human-readable audit paragraph for a single event.

    Args:
        event: CanonicalEvent with NBIM/custody legs.
        diff:  DiffRecord with deterministic deltas.
        account_rows: Optional iterable of per-account attribution rows
                      (see recon.attribution.per_account_attribution).

    Returns:
        A single paragraph string with embedded per-account evidence lines when available.
    """
    parts: List[str] = []

    # Header
    cpair = _fmt_ccy_pair(event.quotation_ccy, event.settlement_ccy)
    parts.append(f"Event {event.event_id} (ISIN {event.isin}, {cpair}) reconciliation summary:")

    # Amount deltas
    if abs(diff.amount_delta_qc) > 0:
        parts.append(f"Amount delta in quotation currency: {diff.amount_delta_qc:,.2f}.")
    if abs(diff.amount_delta_sc) > 0:
        parts.append(f"Amount delta in settlement currency: {diff.amount_delta_sc:,.2f}.")
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

    # Per-account evidence (if provided)
    if account_rows is not None:
        acct_text = _format_account_evidence(account_rows)
        if acct_text:
            parts.append(acct_text)

    return " ".join(parts)
