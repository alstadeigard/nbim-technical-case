from .schemas import CanonicalEvent, DiffRecord
from datetime import datetime

def compute_diff(ev: CanonicalEvent) -> DiffRecord:
    cust_net_qc = sum(l.net_qc for l in ev.custody_legs)
    cust_net_sc = sum(l.net_sc for l in ev.custody_legs)
    cust_gross = sum(l.gross_qc for l in ev.custody_legs)
    cust_tax = sum(l.tax_qc for l in ev.custody_legs)
    cust_tax_rate = (cust_tax / cust_gross * 100) if cust_gross else 0.0
    cust_fx_weighted = _weighted_fx(ev)
    share_diff = sum(l.shares for l in ev.custody_legs) - ev.nbim.shares
    pay_offset = _max_pay_offset_days(ev)
    return DiffRecord(
        event_id=ev.event_id,
        amount_delta_qc=cust_net_qc - ev.nbim.net_qc,
        amount_delta_sc=cust_net_sc - ev.nbim.net_sc,
        wht_rate_delta=cust_tax_rate - ev.nbim.wht_rate,
        fx_delta=cust_fx_weighted - ev.nbim.fx_used,
        date_offset_pay_abs_days=pay_offset,
        share_diff=share_diff,
    )

def _weighted_fx(ev: CanonicalEvent) -> float:
    w = [max(l.net_qc, 0.0) for l in ev.custody_legs]
    n = [l.fx for l in ev.custody_legs]
    s = sum(w)
    return sum(ni * wi for ni, wi in zip(n, w)) / s if s else 0.0

def _max_pay_offset_days(ev: CanonicalEvent) -> int:
    try:
        nb = datetime.fromisoformat(_normalize_date(ev.pay_date))
        legs = [_normalize_date(l.pay_date) for l in ev.custody_legs if l.pay_date]
        if not legs:
            return 0
        diffs = []
        for d in legs:
            diffs.append(abs((datetime.fromisoformat(d) - nb).days))
        return max(diffs) if diffs else 0
    except Exception:
        return 0

def _normalize_date(s: str) -> str:
    s = s.strip()
    if "/" in s:
        m, d, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    if "." in s:
        d, m, y = s.split(".")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s
