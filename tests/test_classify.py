"""
Tests for deterministic reconciliation classification (classify.py).
"""

from src.recon.classify import classify
from src.recon.schemas import DiffRecord


def _diff(
    qc=0.0, sc=0.0, wht_pp=0.0, fx=0.0, days=0, shares=0.0, loan_total=0.0, shares_after=0.0
) -> DiffRecord:
    """
    Helper to build a minimal DiffRecord for classification tests.
    """
    return DiffRecord(
        event_id="T",
        amount_delta_qc=qc,
        amount_delta_sc=sc,
        wht_rate_delta=wht_pp,
        fx_delta=fx,
        date_offset_pay_abs_days=days,
        share_diff=shares,
        loan_total=loan_total,
        share_diff_after_loan=shares_after,
    )


def test_no_break_detected_when_all_zeros():
    d = _diff()
    out = classify(d)
    assert out["break_types"] == ["No_break_detected"]
    assert out["severity"] == "low"
    assert 0.3 <= out["confidence"] <= 0.5


def test_amount_only_triggers_unexplained_label_and_medium_severity():
    d = _diff(sc=1500.0)
    out = classify(d)
    assert "Amount_delta_unexplained" in out["break_types"]
    assert out["severity"] in ("medium", "high")


def test_fx_mismatch_label_when_implied_fx_diff():
    d = _diff(fx=0.002, sc=200.0)
    out = classify(d)
    assert "FX_mismatch" in out["break_types"]


def test_tax_rate_mismatch_label():
    d = _diff(wht_pp=0.5)  # 0.5 percentage points difference
    out = classify(d)
    assert "Tax_rate_mismatch" in out["break_types"]


def test_quantity_mismatch_after_lending():
    d = _diff(shares_after=1200.0, sc=2500.0)
    out = classify(d)
    assert "Quantity_mismatch" in out["break_types"]
    assert out["severity"] in ("medium", "high")


def test_timing_mismatch_for_payment_date_offset():
    d = _diff(days=4)
    out = classify(d)
    assert "Timing_mismatch" in out["break_types"]
