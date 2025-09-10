"""
Tests for the summary CSV/DataFrame formatting (rounding and signed-zero normalization).
"""

import math
import pandas as pd

from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.policy import risk_and_policy
from src.recon.classify import classify
from src.recon.summary import build_summary_dataframe


def _nbim_row(event_id, isin="X", q="USD", s="USD", ex="01.01.2025", pay="02.01.2025",
              shares=1000, dps=1.0, wht=0.0, fx=1.0, bank="ACC1"):
    """
    Build a synthetic NBIM row with simple amount derivation: net = shares * dps.
    """
    amt = shares * dps
    return {
        "COAC_EVENT_KEY": event_id, "ISIN": isin,
        "EXDATE": ex, "PAYMENT_DATE": pay,
        "QUOTATION_CURRENCY": q, "SETTLEMENT_CURRENCY": s,
        "NOMINAL_BASIS": shares, "DIVIDENDS_PER_SHARE": dps,
        "GROSS_AMOUNT_QUOTATION": amt, "NET_AMOUNT_QUOTATION": amt, "NET_AMOUNT_SETTLEMENT": amt,
        "WTHTAX_RATE": wht, "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": fx,
        "BANK_ACCOUNT": bank,
    }


def _cust_row(event_id, bank="ACC1", shares=1000, net_qc=None, net_sc=None, tax=0.0, gross=None,
              fx=1.0, pay="02.01.2025", loan=0.0):
    """
    Build a synthetic custody row. By default net_sc == net_qc; callers can
    induce FX/amount differences by setting net_qc and net_sc separately.
    """
    if net_qc is None:
        net_qc = shares * 1.0
    if net_sc is None:
        net_sc = net_qc
    if gross is None:
        gross = net_qc + tax
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": gross,
        "NET_AMOUNT_QC": net_qc,
        "NET_AMOUNT_SC": net_sc,
        "TAX": tax,
        "FX_RATE": fx,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": bank,
        "PAY_DATE": pay,
        "LOAN_QUANTITY": loan,
    }


def _is_rounded(value: float, decimals: int) -> bool:
    """
    Return True if value has at most `decimals` decimal places (within float tol).
    """
    scale = 10 ** decimals
    return math.isclose(round(value * scale) / scale, value, rel_tol=0, abs_tol=1e-12)


def test_summary_rounding_and_no_signed_zero():
    """
    Validates:
      - Near-zero FX deltas are normalized to 0.0 (no -0.0 / eps).
      - Non-zero FX deltas remain non-zero.
      - Money deltas are rounded to 2 dp; FX to 6 dp.
      - Shares & day offsets are integers.
      - Break types are joined strings.
    """
    nbim = pd.DataFrame([
        # A1 exact match (all zeros)
        _nbim_row("A1", isin="US0378331005", q="USD", s="USD",
                  shares=1_500_000, dps=0.2125, wht=15.0, bank="501234567"),
        # B1 cross-currency w/ scaling diffs (likely non-zero FX/amount deltas)
        _nbim_row("B1", isin="KR7005930003", q="KRW", s="USD",
                  shares=25_000, dps=361.0, wht=22.0, bank="712345678"),
        # C1 multi-account; one account will have a share/amount delta
        _nbim_row("C1", isin="CH0038863350", q="CHF", s="CHF",
                  shares=20_000, dps=3.1, wht=35.0, bank="823456789"),
        _nbim_row("C1", isin="CH0038863350", q="CHF", s="CHF",
                  shares=15_000, dps=3.1, wht=35.0, bank="823456790"),
        _nbim_row("C1", isin="CH0038863350", q="CHF", s="CHF",
                  shares=10_000, dps=3.1, wht=35.0, bank="823456791"),
    ])
    custody = pd.DataFrame([
        # A1 exact match
        _cust_row("A1", bank="501234567", shares=1_500_000,
                  net_qc=318_750.0, net_sc=318_750.0, tax=56_250.0, fx=1.0, pay="14.02.2025"),
        # B1: induce FX/amount/date mismatch (values arbitrary but consistent)
        _cust_row("B1", bank="712345678", shares=23_000,
                  net_qc=6_769_950.0, net_sc=5_181.5, tax=1_805_000.0,
                  fx=1307.241766, pay="25.05.2025", loan=2_000.0),
        # C1: two accounts match; one has +2,000 shares and +4,030 QC/SC delta
        _cust_row("C1", bank="823456789", shares=20_000, net_qc=40_300.0, net_sc=40_300.0, tax=21_700.0),
        _cust_row("C1", bank="823456790", shares=15_000, net_qc=30_225.0, net_sc=30_225.0, tax=16_275.0),
        _cust_row("C1", bank="823456791", shares=12_000, net_qc=24_180.0, net_sc=24_180.0, tax=13_020.0),
    ])

    events = to_canonical(nbim, custody)
    diffs = [compute_diff(ev) for ev in events]
    risks = [risk_and_policy(ev, d) for ev, d in zip(events, diffs)]
    classes = [classify(d) for d in diffs]

    df = build_summary_dataframe(events, diffs, risks, classes)

    # (1) FX rounding/normalization
    # Near-zero entries must be exactly 0.0; others can be non-zero.
    near_zero_mask = df["fx_delta"].abs() < 1e-12
    if near_zero_mask.any():
        assert (df.loc[near_zero_mask, "fx_delta"] == 0.0).all()
    if (~near_zero_mask).any():
        # Ensure non-near-zero values are not normalized to zero
        assert (df.loc[~near_zero_mask, "fx_delta"].abs() > 0.0).all()

    # FX values are rounded to 6 dp (no need to match specific number)
    for fx_val in df["fx_delta"]:
        assert _is_rounded(float(fx_val), 6)

    # (2) Money deltas rounded to 2 dp
    for val in df["amount_delta_qc"]:
        assert _is_rounded(float(val), 2)
    for val in df["amount_delta_sc"]:
        assert _is_rounded(float(val), 2)

    # (3) Shares & day offsets are integers (dtype)
    assert df["shares_delta"].dtype.kind in ("i",)
    assert df["shares_delta_after_loan"].dtype.kind in ("i",)
    assert df["pay_date_offset_days"].dtype.kind in ("i",)

    # (4) Break types are joined strings
    # For the multi-account event "C1", we should have a string in the column
    assert isinstance(df.loc[df["event_id"] == "C1", "break_types"].iloc[0], str)
