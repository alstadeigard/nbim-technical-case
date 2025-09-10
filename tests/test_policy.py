"""
Tests for deterministic risk scoring (policy.py).
"""

import pandas as pd
from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.policy import risk_and_policy


def _mk_nbim_row(event_id="E", net_qc=100.0, net_sc=100.0, wht=15.0, fx=1.0,
                 gross_qc=117.647, shares=1000, exdate="01.01.2025", paydate="02.01.2025",
                 qccy="USD", sccy="USD", bank="ACC1"):
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": exdate,
        "PAYMENT_DATE": paydate,
        "QUOTATION_CURRENCY": qccy,
        "SETTLEMENT_CURRENCY": sccy,
        "NOMINAL_BASIS": shares,
        "DIVIDENDS_PER_SHARE": 0.117647,
        "GROSS_AMOUNT_QUOTATION": gross_qc,
        "NET_AMOUNT_QUOTATION": net_qc,
        "NET_AMOUNT_SETTLEMENT": net_sc,
        "WTHTAX_RATE": wht,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": fx,
        "BANK_ACCOUNT": bank,
    }


def _mk_custody_row(event_id="E", net_qc=100.0, net_sc=100.0, tax=17.647, gross_qc=117.647,
                    fx=1.0, pay_date="02.01.2025", shares=1000, bank="ACC1", loan_qty=0.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": gross_qc,
        "NET_AMOUNT_QC": net_qc,
        "NET_AMOUNT_SC": net_sc,
        "TAX": tax,
        "FX_RATE": fx,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": bank,
        "PAY_DATE": pay_date,
        "LOAN_QUANTITY": loan_qty,
    }


def test_policy_autoclose_when_immaterial_and_no_shares_or_tax_or_date():
    nbim = pd.DataFrame([_mk_nbim_row(event_id="A", net_qc=100.0, net_sc=100.0)])
    custody = pd.DataFrame([_mk_custody_row(event_id="A", net_qc=100.0, net_sc=100.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert rp["risk_score"] == 0.0
    assert rp["require_review"] is False
    assert rp["auto_close"] is True


def test_policy_date_offset_contributes_and_blocks_autoclose():
    nbim = pd.DataFrame([_mk_nbim_row(event_id="B", paydate="02.01.2025")])
    custody = pd.DataFrame([_mk_custody_row(event_id="B", pay_date="07.01.2025")])  # 5-day offset
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert rp["risk_score"] > 0.0  # date contributes
    assert rp["auto_close"] is False  # date issue prevents autoclose


def test_policy_amount_medium_severity_thresholds():
    # Settlement delta ~ 342.77 → small score (< 1.0) with default thresholds
    nbim = pd.DataFrame([_mk_nbim_row(event_id="C", net_qc=100.0, net_sc=100.0)])
    custody = pd.DataFrame([_mk_custody_row(event_id="C", net_qc=100.0, net_sc=442.77)])  # +342.77 SC
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert 0.0 < rp["risk_score"] < 1.5
    assert rp["require_review"] is False


def test_policy_share_delta_after_loan_increases_score():
    # 2,000 share delta after lending adds to score and should require review with default params
    nbim = pd.DataFrame([_mk_nbim_row(event_id="D", shares=10000)])
    custody = pd.DataFrame([_mk_custody_row(event_id="D", shares=12000, loan_qty=0.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rp = risk_and_policy(ev, diff)
    assert rp["risk_score"] >= 1.5
    assert rp["require_review"] is True
