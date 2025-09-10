"""
Unit tests for remediation suggestions.
"""

import pandas as pd

from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.attribution import per_account_attribution
from src.recon.remediation import suggest_remediation


def _nbim(event_id="E", bank="ACC1", shares=1000, qc=1.0, q="USD", s="USD", wht=0.0):
    amt = shares * qc
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": "01.01.2025",
        "PAYMENT_DATE": "02.01.2025",
        "QUOTATION_CURRENCY": q,
        "SETTLEMENT_CURRENCY": s,
        "NOMINAL_BASIS": shares,
        "DIVIDENDS_PER_SHARE": qc,
        "GROSS_AMOUNT_QUOTATION": amt,
        "NET_AMOUNT_QUOTATION": amt,
        "NET_AMOUNT_SETTLEMENT": amt,
        "WTHTAX_RATE": wht,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0,
        "BANK_ACCOUNT": bank,
    }


def _cust(event_id="E", bank="ACC1", shares=1000, net_qc=1000.0, net_sc=1000.0, tax=0.0, fx=1.0, pay="02.01.2025", loan=0.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": net_qc + tax,
        "NET_AMOUNT_QC": net_qc,
        "NET_AMOUNT_SC": net_sc,
        "TAX": tax,
        "FX_RATE": fx,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": bank,
        "PAY_DATE": pay,
        "LOAN_QUANTITY": loan,
    }


def test_quantity_and_tax_suggestions():
    nbim = pd.DataFrame([
        _nbim("E1", bank="A", shares=10000, qc=1.0, q="USD", s="USD", wht=15.0),
    ])
    custody = pd.DataFrame([
        _cust("E1", bank="A", shares=12000, net_qc=8500.0, net_sc=8500.0, tax=1500.0),
    ])

    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)
    cls = {"break_types": ["Quantity_mismatch", "Amount_delta_unexplained", "Tax_rate_mismatch"], "severity": "medium"}
    risk = {"require_review": True}

    actions = suggest_remediation(event=ev, diff=diff, classification=cls, per_account_rows=rows, risk=risk)
    text = " ".join(actions).lower()
    assert "verify positions" in text
    assert "withholding rate" in text or "treaty" in text
    assert "trace amount delta" in text


def test_no_break_auto_close():
    nbim = pd.DataFrame([_nbim("E2", shares=1000, qc=1.0)])
    custody = pd.DataFrame([_cust("E2", shares=1000, net_qc=1000.0, net_sc=1000.0, tax=0.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)
    cls = {"break_types": ["No_break_detected"], "severity": "low"}
    risk = {"require_review": False}

    actions = suggest_remediation(event=ev, diff=diff, classification=cls, per_account_rows=rows, risk=risk)
    assert any("no break" in a.lower() for a in actions)
