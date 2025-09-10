"""
Deterministic classification of reconciliation breaks.

This module provides a rule-based classifier that labels each event with break types
and a coarse confidence score. It prepares the ground for later LLM-based classification
by keeping a stable JSON shape (break_types, severity, hypothesized_causes, confidence).
"""

from typing import Dict, List, Literal
from .schemas import DiffRecord

Severity = Literal["low", "medium", "high"]


def classify(diff: DiffRecord, cfg: Dict[str, float] | None = None) -> Dict[str, object]:
    """
    Classify a reconciliation diff into break types with severity and confidence.

    Heuristics:
      - Amount deltas drive severity (settlement currency).
      - Labels inferred from specific signals (FX, WHT, shares/lending, date).
      - Confidence increases with the magnitude of clear signals.

    Args:
        diff: DiffRecord with deterministic deltas.
        cfg:  Optional thresholds override (same keys as policy if desired).

    Returns:
        dict with:
          - break_types: List[str]
          - severity: "low" | "medium" | "high"
          - hypothesized_causes: List[str]
          - confidence: float in [0, 1]
    """
    # Defaults coordinated loosely with policy thresholds
    C = {
        "sev_high_amount": 10_000.0,
        "sev_med_amount": 1_000.0,
        "fx_eps": 1e-6,
        "wht_eps_pp": 0.25,  # 0.25 pp threshold for noticing WHT differences
        "share_eps_units": 1.0,  # any non-zero after-loan shares count
        "date_eps_days": 1,  # any non-zero day offset counts
    }
    if cfg:
        C.update(cfg)

    labels: List[str] = []
    causes: List[str] = []

    # Amount-based severity (SC)
    amt = abs(diff.amount_delta_sc)
    if amt >= C["sev_high_amount"]:
        severity: Severity = "high"
    elif amt >= C["sev_med_amount"]:
        severity = "medium"
    else:
        severity = "low"

    # FX
    if abs(diff.fx_delta) > C["fx_eps"]:
        labels.append("FX_mismatch")
        causes.append("Different implied FX conversion between NBIM and Custody")

    # Withholding tax
    if abs(diff.wht_rate_delta) > C["wht_eps_pp"]:
        labels.append("Tax_rate_mismatch")
        causes.append("Different withholding tax rate applied")

    # Shares (after lending)
    if abs(diff.share_diff_after_loan) > C["share_eps_units"]:
        labels.append("Quantity_mismatch")
        causes.append("Share count discrepancy after lending adjustment")

    # Date
    if diff.date_offset_pay_abs_days > C["date_eps_days"]:
        labels.append("Timing_mismatch")
        causes.append("Payment date processed on different day")

    # Residual amounts with no explicit reason
    if (amt > 0) and not labels:
        labels.append("Amount_delta_unexplained")
        causes.append("Residual difference in settlement amount")

    # Confidence: simple aggregation of signals
    signal_count = 0
    signal_count += int("FX_mismatch" in labels)
    signal_count += int("Tax_rate_mismatch" in labels)
    signal_count += int("Quantity_mismatch" in labels)
    signal_count += int("Timing_mismatch" in labels)
    signal_count += int("Amount_delta_unexplained" in labels)
    base_conf = min(0.3 + 0.15 * signal_count, 0.9)

    # Boost confidence slightly for larger amounts and share deltas
    boost = 0.0
    if amt >= C["sev_med_amount"]:
        boost += 0.05
    if abs(diff.share_diff_after_loan) >= 1000:
        boost += 0.05
    confidence = max(0.3, min(base_conf + boost, 0.95))

    return {
        "break_types": labels or ["No_break_detected"],
        "severity": severity,
        "hypothesized_causes": causes,
        "confidence": round(confidence, 2),
    }
