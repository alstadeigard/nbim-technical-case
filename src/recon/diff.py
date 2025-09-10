from datetime import datetime
from .schemas import CanonicalEvent, DiffRecord


def compute_diff(ev: CanonicalEvent) -> DiffRecord:
    """
    Deterministic reconciliation deltas for a single event.

    - Amount deltas computed in both quotation currency (QC) and settlement currency (SC).
    - Withholding tax delta based on effective tax rate observed on custody vs NBIM expectation.
    - FX delta computed from implied FX (amount-based) to avoid comparing incompatible raw FX columns.
    - Payment date offset computed as the maximum absolute difference across custody legs.
    - Share difference flags quantity/lending mismatches early.
    """
    cust_net_qc = sum(l.net_qc for l in ev.custody_legs)
    cust_net_sc = sum(l.net_sc for l in ev.custody_legs)

    cust_gross = sum(l.gross_qc for l in ev.custody_legs)
    cust_tax = sum(l.tax_qc for l in ev.custody_legs)
    cust_tax_rate = (cust_tax / cust_gross * 100.0) if cust_gross else 0.0

    nbim_fx_implied = _implied_fx_nbim(ev)
    cust_fx_implied = _implied_fx_custody(ev)

    share_diff = sum(l.shares for l in ev.custody_legs) - ev.nbim.shares
    pay_offset = _max_pay_offset_days(ev)

    return DiffRecord(
        event_id=ev.event_id,
        amount_delta_qc=cust_net_qc - ev.nbim.net_qc,
        amount_delta_sc=cust_net_sc - ev.nbim.net_sc,
        wht_rate_delta=cust_tax_rate - ev.nbim.wht_rate,
        fx_delta=cust_fx_implied - nbim_fx_implied,
        date_offset_pay_abs_days=pay_offset,
        share_diff=share_diff,
    )


def _implied_fx_nbim(ev: CanonicalEvent) -> float:
    """
    NBIM implied FX from amounts:
        if quotation_ccy == settlement_ccy → 1.0
        else → net_sc / net_qc (guarding division by zero)

    This is robust to different raw FX conventions across systems.
    """
    q = (ev.quotation_ccy or "").strip()
    s = (ev.settlement_ccy or "").strip()
    if q == s:
        return 1.0
    return (ev.nbim.net_sc / ev.nbim.net_qc) if ev.nbim.net_qc else 0.0


def _implied_fx_custody(ev: CanonicalEvent) -> float:
    """
    Custody implied FX blended across legs:
        per-leg ratio = net_sc / net_qc (0.0 if net_qc is 0)
        weighted average with weights = net_qc (economic materiality)
    """
    weights = [max(l.net_qc, 0.0) for l in ev.custody_legs]
    ratios = [(l.net_sc / l.net_qc) if l.net_qc else 0.0 for l in ev.custody_legs]
    total_w = sum(weights)
    return sum(w * r for w, r in zip(weights, ratios)) / total_w if total_w else 0.0


def _max_pay_offset_days(ev: CanonicalEvent) -> int:
    """
    Maximum absolute difference (in days) between NBIM payment date and custody leg payment dates.
    Accepts 'dd.mm.yyyy', 'mm/dd/yyyy', or 'yyyy-mm-dd' and normalizes to ISO for comparison.
    """
    try:
        nb = datetime.fromisoformat(_normalize_date(ev.pay_date))
    except Exception:
        # If NBIM date is malformed, we can’t compute an offset reliably.
        return 0

    leg_dates = []
    for l in ev.custody_legs:
        if not l.pay_date:
            continue
        try:
            leg_dates.append(datetime.fromisoformat(_normalize_date(l.pay_date)))
        except Exception:
            # Skip malformed custody dates; data-quality can be flagged elsewhere.
            continue

    if not leg_dates:
        return 0

    return max(abs((d - nb).days) for d in leg_dates)


def _normalize_date(s: str) -> str:
    """
    Normalize date strings into ISO 'yyyy-mm-dd'.
    Supported inputs:
      - 'dd.mm.yyyy' (e.g., '14.02.2025')
      - 'mm/dd/yyyy' (e.g., '02/14/2025')
      - 'yyyy-mm-dd' (already ISO)
    """
    if s is None:
        raise ValueError("Date string is None")
    s = s.strip()
    if not s:
        raise ValueError("Empty date string")

    # mm/dd/yyyy
    if "/" in s:
        m, d, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # dd.mm.yyyy
    if "." in s:
        d, m, y = s.split(".")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # assume already ISO
    return s