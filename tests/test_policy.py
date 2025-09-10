import pandas as pd

from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.policy import risk_and_policy


def _mk_nbim_row(event_id="E", net_qc=100.0, net_sc=100.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": "01.01.2025",
        "PAYMENT_DATE": "02.01.2025",
        "QUOTATION_CURRENCY": "USD",
        "SETTLEMENT_CURRENCY": "USD",
        "NOMINAL_BASIS": 1000,
        "DIVIDENDS_PER_SHARE": 0.1,
        "GROSS_AMOUNT_QUOTATION": net_qc,
        "NET_AMOUNT_QUOTATION": net_qc,
        "NET_AMOUNT_SETTLEMENT": net_sc,
        "WTHTAX_RATE": 0.0,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0,
        "BANK_ACCOUNT": "A",
    }


def _mk_custody_row(event_id="E", net_qc=100.0, net_sc=100.0, fx=1.0, pay="02.01.2025", loan=0.0, shares=1000):
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": net_qc,     # unused but present
        "NET_AMOUNT_QC": net_qc,
        "NET_AMOUNT_SC": net_sc,
        "TAX": 0.0,
        "FX_RATE": fx,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": "A",
        "PAY_DATE": pay,
        "LOAN_QUANTITY": loan,
    }


def test_policy_zero_scores_auto_close():
    nbim = pd.DataFrame([_mk_nbim_row(event_id="A", net_qc=100.0, net_sc=100.0)])
    custody = pd.DataFrame([_mk_custody_row(event_id="A", net_qc=100.0, net_sc=100.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert rp["risk_score"] == 0.00
    assert rp["auto_close"] is True
    assert rp["require_review"] is False


def test_policy_amount_medium_severity_thresholds():
    # Settlement delta ~ 342.77 -> score ≈ 342.77 * 0.003 = 1.03 (< 1.5)
    nbim = pd.DataFrame([_mk_nbim_row(event_id="C", net_qc=100.0, net_sc=100.0)])
    custody = pd.DataFrame([_mk_custody_row(event_id="C", net_qc=100.0, net_sc=442.77)])  # +342.77 SC
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert 0.0 < rp["risk_score"] < 1.5


def test_policy_shares_and_tax_raise_score_when_no_sc_delta():
    # 2,000 shares delta => 2000 * 0.001 = 2.0; 2pp tax => 0.5; total >= 2.5
    nbim = pd.DataFrame([_mk_nbim_row(event_id="B", net_qc=100.0, net_sc=100.0)])
    custody = pd.DataFrame([_mk_custody_row(event_id="B", net_qc=100.0, net_sc=100.0, shares=1200)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    # simulate: no SC delta but shares+tax present
    diff.share_diff_after_loan = 2000.0
    diff.wht_rate_delta = 2.0  # percentage points
    rp = risk_and_policy(ev, diff)
    assert rp["risk_score"] >= 2.5
