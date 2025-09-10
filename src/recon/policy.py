"""
Deterministic policy & risk scoring for reconciliation events.

This module turns numeric diffs into a risk score and simple control flags:
- require_review: True if risk_score crosses a threshold
- auto_close: True if differences are immaterial per policy
"""

from typing import Dict, Optional
from .schemas import CanonicalEvent, DiffRecord


_DEFAULTS: Dict[str, float] = {
    # Amount materiality (settlement currency)
    "sev_high_amount": 10_000.0,   # high severity floor (SC units)
    "sev_med_amount": 1_000.0,     # medium severity floor (SC units)
    "auto_close_amount": 50.0,     # below this, can auto-close (SC units)

    # Shares & dates
    "sev_share_units": 1_000.0,    # +1.0 to score per N shares of delta (after lending)
    "sev_date_days": 3.0,          # >3 days adds to score

    # Tax/wht
    "sev_wht_pp": 3.0,             # >3 percentage points adds to score

    # Overall review threshold
    "review_threshold": 1.5,       # score >= 1.5 -> require review
}


def risk_and_policy(
    event: CanonicalEvent,
    diff: DiffRecord,
    cfg: Optional[Dict[str, float]] = None
) -> Dict[str, object]:
    """
    Compute a simple additive risk score and control flags for one event.

    Scoring (heuristic but deterministic):
      - Amount delta (SC): scaled by severity floors.
      - Share delta (after lending): contributes per 'sev_share_units'.
      - Withholding tax delta (pp): contributes if above 'sev_wht_pp'.
      - Payment date offset (days): contributes if above 'sev_date_days'.

    Args:
        event: CanonicalEvent being evaluated.
        diff:  Deterministic DiffRecord for the event.
        cfg:   Optional overrides for thresholds.

    Returns:
        dict with:
          - risk_score: float
          - require_review: bool
          - auto_close: bool
    """
    C = {**_DEFAULTS, **(cfg or {})}

    # Amount severity component (settlement currency)
    amt = abs(diff.amount_delta_sc)
    amt_score = 0.0
    if amt >= C["sev_high_amount"]:
        amt_score = 2.0
    elif amt >= C["sev_med_amount"]:
        amt_score = 1.0
    else:
        amt_score = min(amt / max(C["sev_med_amount"], 1.0), 1.0) * 0.5  # small contribution

    # Shares severity (after lending)
    sh = abs(diff.share_diff_after_loan)
    sh_score = (sh / max(C["sev_share_units"], 1.0)) if sh > 0 else 0.0
    sh_score = min(sh_score, 2.0)  # cap

    # WHT severity
    wht = abs(diff.wht_rate_delta)
    wht_score = 0.5 if wht > C["sev_wht_pp"] else 0.0

    # Date severity
    day = diff.date_offset_pay_abs_days
    day_score = 0.5 if day > C["sev_date_days"] else 0.0

    risk_score = round(amt_score + sh_score + wht_score + day_score, 2)

    require_review = risk_score >= C["review_threshold"]

    # Auto-close only if no shares after lending AND amount delta is tiny AND no tax/date issues
    auto_close = (
        (sh == 0)
        and (amt <= C["auto_close_amount"])
        and (wht_score == 0.0)
        and (day_score == 0.0)
    )

    return {
        "risk_score": risk_score,
        "require_review": require_review,
        "auto_close": auto_close,
    }
