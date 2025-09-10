"""
Audit trail generation (improved default formatting, ASCII-safe).

This produces a concise, structured paragraph that explains the reconciliation
result using consistent labels and punctuation. It keeps wording compatible
with previous tests (key phrases preserved) while improving readability.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Any, List


def _fmt_amount(x: float, dp: int = 2) -> str:
    """
    Format amount with comma separators and specified decimal places.
    
    Args:
        x: Amount to format
        dp: Number of decimal places
        
    Returns:
        Formatted amount string
    """
    return f"{x:,.{dp}f}"


def _fmt_fx(x: float, dp: int = 6) -> str:
    """
    Format FX rate with specified decimal places, normalizing tiny values to 0.0.
    
    Args:
        x: FX rate to format
        dp: Number of decimal places
        
    Returns:
        Formatted FX rate string
    """
    # normalize tiny -0.0 to 0.0
    if abs(x) < 1e-12:
        x = 0.0
    return f"{x:.{dp}f}"


def _fmt_pp(x: float, dp: int = 2) -> str:
    """
    Format percentage points delta with specified decimal places.
    
    Args:
        x: Percentage points to format
        dp: Number of decimal places
        
    Returns:
        Formatted percentage points string
    """
    # percentage points delta
    return f"{x:.{dp}f}"


def _plural(n: int, s: str) -> str:
    """
    Format count with proper pluralization.
    
    Args:
        n: Count number
        s: Singular form of the word
        
    Returns:
        Formatted string with proper pluralization
    """
    return f"{n} {s}" if n == 1 else f"{n} {s}s"


def _evidence_accounts(rows: Iterable[Mapping[str, Any]]) -> List[str]:
    """
    Extract account names that have non-zero deltas.
    
    Args:
        rows: Iterable of per-account attribution rows
        
    Returns:
        List of account names with deltas
    """
    accs: List[str] = []
    for r in rows or []:
        sd = abs(float(r.get("share_delta", 0.0)))
        qd = abs(float(r.get("net_qc_delta", 0.0)))
        scd = abs(float(r.get("net_sc_delta", 0.0)))
        if sd > 0.0 or qd > 0.0 or scd > 0.0:
            accs.append(str(r.get("bank_account") or ""))
    return accs


def _ccy_pair(q: str | None, s: str | None) -> str:
    """
    Format currency pair with ASCII-safe arrow for Windows consoles.
    
    Args:
        q: Quotation currency
        s: Settlement currency
        
    Returns:
        Formatted currency pair string
    """
    q = q or ""
    s = s or ""
    # ASCII-safe arrow for Windows consoles
    return f"{q}->{s}"


def generate_audit_paragraph(
    event,
    diff,
    account_rows: Iterable[Mapping[str, Any]] | None = None,
) -> str:
    """
    Produce a human-readable, ASCII-safe audit trail describing the reconciliation.

    The output is a single paragraph with consistent labels:
      - Amounts (QC/SC)
      - Shares (loan-adjusted)
      - FX delta
      - WHT delta
      - Payment date offset
      - Evidence accounts (if any)

    Parameters
    ----------
    event : CanonicalEvent
    diff : DiffRecord
    account_rows : iterable of mapping, optional

    Returns
    -------
    str
        A concise explanatory paragraph suitable for logs, JSON, and console.
    """
    event_id = str(event.event_id)
    isin = str(event.isin)
    q_ccy = str(event.quotation_ccy or "")
    s_ccy = str(event.settlement_ccy or "")

    amt_qc = float(diff.amount_delta_qc)
    amt_sc = float(diff.amount_delta_sc)
    fx_d = float(diff.fx_delta)
    wht_pp = float(diff.wht_rate_delta)
    pay_days = int(diff.date_offset_pay_abs_days)
    share_adj = float(diff.share_diff_after_loan)
    loan_total = float(diff.loan_total)

    evidence = _evidence_accounts(account_rows or [])

    parts: List[str] = []
    # Header (kept compatible with previous wording)
    parts.append(f"Event {event_id} (ISIN {isin}, {_ccy_pair(q_ccy, s_ccy)}) reconciliation summary:")

    # Amounts
    if abs(amt_qc) > 0.0:
        parts.append(f"Amount delta (quotation): { _fmt_amount(amt_qc) }.")
    else:
        parts.append("No amount delta in quotation currency.")
    if abs(amt_sc) > 0.0:
        parts.append(f"Amount delta (settlement): { _fmt_amount(amt_sc) }.")
    else:
        parts.append("No amount delta in settlement currency.")

    # Shares (loan-adjusted)
    if abs(share_adj) > 0.0:
        parts.append(
            f"Share delta after lending adjustment: {int(round(share_adj))}; "
            f"loan total: {int(round(loan_total))}."
        )
    else:
        parts.append(
            f"No share delta after lending adjustment; "
            f"loan total: {int(round(loan_total))}."
        )

    # FX
    if abs(fx_d) > 0.0:
        parts.append(f"Implied FX delta: { _fmt_fx(fx_d) }.")
    else:
        parts.append("No implied FX difference.")

    # WHT
    if abs(wht_pp) > 0.0:
        parts.append(f"Withholding tax rate delta: { _fmt_pp(wht_pp) } pp.")
    else:
        parts.append("No withholding tax rate difference.")

    # Pay-date offset
    if pay_days != 0:
        parts.append(f"Payment date offset: { _plural(abs(pay_days), 'day') }.")

    # Evidence accounts (if any)
    if evidence:
        parts.append(f"Evidence by account: [{', '.join(evidence)}].")

    # Join as a single paragraph (readable, punctuation-consistent)
    return " ".join(parts)
