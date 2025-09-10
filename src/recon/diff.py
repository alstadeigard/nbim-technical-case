"""
Functions for computing deterministic reconciliation differences between NBIM and Custody.
"""

from datetime import datetime
from .schemas import CanonicalEvent, DiffRecord


def compute_diff(ev: CanonicalEvent) -> DiffRecord:
    """
    Compute reconciliation differences for a single event.

    Returns:
        DiffRecord with amount deltas, FX delta, tax delta, share deltas,
        loan totals, and payment date offsets.
    """
    cust_net_qc = sum(l.net_qc for l in ev.custody_legs)
    cust_net_sc = sum(l.net_sc for l in ev.custody_legs)

    cust_gross = sum(l.gross_qc for l in ev.custody_legs)
    cust_tax = sum(l.tax_qc for l in ev.custody_legs)
    cust_tax_rate = (cust_tax / cust_gross * 100.0) if cust_gross else 0.0

    nbim_fx_implied = _implied_fx_nbim(ev)
    cust_fx_implied = _implied_fx_custody(ev)

    custody_shares = sum(l.shares for l in ev.custody_legs)
    loan_total = sum(l.loan_quantity for l in ev.custody_legs)
    share_diff = custody_shares - ev.nbim.shares
    share_diff_after_loan = (custody_shares + loan_total) - ev.nbim.shares

    pay_offset = _max_pay_offset_days(ev)

    return DiffRecord(
        event_id=ev.event_id,
        amount_delta_qc=cust_net_qc - ev.nbim.net_qc,
        amount_delta_sc=cust_net_sc - ev.nbim.net_sc,
        wht_rate_delta=cust_tax_rate - ev.nbim.wht_rate,
        fx_delta=cust_fx_implied - nbim_fx_implied,
        date_offset_pay_abs_days=pay_offset,
        share_diff=share_diff,
        loan_total=loan_total,
        share_diff_after_loan=share_diff_after_loan,
    )


def _implied_fx_nbim(ev: CanonicalEvent) -> float:
    """
    Compute NBIM's implied FX rate from amounts.

    If quotation and settlement currencies match → 1.0.
    Otherwise → net_sc / net_qc.
    """
    q = (ev.quotation_ccy or "").strip()
    s = (ev.settlement_ccy or "").strip()
    if q == s:
        return 1.0
    return (ev.nbim.net_sc / ev.nbim.net_qc) if ev.nbim.net_qc else 0.0


def _implied_fx_custody(ev: CanonicalEvent) -> float:
    """
    Compute custody's implied FX as a weighted average across legs.

    Each leg ratio = net_sc / net_qc (0 if net_qc = 0).
    Weighted by net_qc to avoid small legs dominating.
    """
    weights = [max(l.net_qc, 0.0) for l in ev.custody_legs]
    ratios = [(l.net_sc / l.net_qc) if l.net_qc else 0.0 for l in ev.custody_legs]
    total_w = sum(weights)
    return sum(w * r for w, r in zip(weights, ratios)) / total_w if total_w else 0.0


def _max_pay_offset_days(ev: CanonicalEvent) -> int:
    """
    Compute maximum absolute difference (days) between NBIM pay_date and custody leg pay_dates.
    """
    try:
        nb = datetime.fromisoformat(_normalize_date(ev.pay_date))
    except Exception:
        return 0
    leg_dates = []
    for l in ev.custody_legs:
        if not l.pay_date:
            continue
        try:
            leg_dates.append(datetime.fromisoformat(_normalize_date(l.pay_date)))
        except Exception:
            continue
    if not leg_dates:
        return 0
    return max(abs((d - nb).days) for d in leg_dates)


def _normalize_date(s: str) -> str:
    """
    Normalize a date string into ISO yyyy-mm-dd format.

    Supports:
        dd.mm.yyyy
        mm/dd/yyyy
        yyyy-mm-dd
    """
    if s is None:
        raise ValueError("Date string is None")
    s = s.strip()
    if not s:
        raise ValueError("Empty date string")
    if "/" in s:
        m, d, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    if "." in s:
        d, m, y = s.split(".")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s
