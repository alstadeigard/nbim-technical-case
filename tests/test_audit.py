"""
Tests for embedding per-account evidence lines in the audit paragraph.
"""

import pandas as pd
from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.attribution import per_account_attribution
from src.recon.audit import generate_audit_paragraph


def _nbim(event_id, bank, shares, qc=1.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": "01.01.2025",
        "PAYMENT_DATE": "02.01.2025",
        "QUOTATION_CURRENCY": "CHF",
        "SETTLEMENT_CURRENCY": "CHF",
        "NOMINAL_BASIS": shares,
        "DIVIDENDS_PER_SHARE": qc,  # make gross/net = shares * 1.0 for simplicity
        "GROSS_AMOUNT_QUOTATION": shares * qc,
        "NET_AMOUNT_QUOTATION": shares * qc,
        "NET_AMOUNT_SETTLEMENT": shares * qc,
        "WTHTAX_RATE": 0.0,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0,
        "BANK_ACCOUNT": bank,
    }


def _cust(event_id, bank, shares, qc=1.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": shares * qc,
        "NET_AMOUNT_QC": shares * qc,
        "NET_AMOUNT_SC": shares * qc,
        "TAX": 0.0,
        "FX_RATE": 1.0,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": bank,
        "PAY_DATE": "02.01.2025",
        "LOAN_QUANTITY": 0.0,
    }


def test_audit_contains_evidence_lines_when_account_deltas_exist():
    # NBIM has A1=10k, A2=15k; Custody A1=10k, A2=17k → A2 delta +2k
    nbim = pd.DataFrame([
        _nbim("E1", "A1", 10_000),
        _nbim("E1", "A2", 15_000),
    ])
    custody = pd.DataFrame([
        _cust("E1", "A1", 10_000),
        _cust("E1", "A2", 17_000),
    ])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)

    text = generate_audit_paragraph(ev, diff, account_rows=rows)
    assert "Evidence by account:" in text
    assert "[A2] SharesΔ=2,000" in text
    assert "QCΔ=2,000.00" in text
    assert "SCΔ=2,000.00" in text


def test_audit_omits_evidence_lines_when_all_account_deltas_zero():
    # Both accounts match exactly → no evidence section
    nbim = pd.DataFrame([
        _nbim("E2", "B1", 5_000),
        _nbim("E2", "B2", 7_000),
    ])
    custody = pd.DataFrame([
        _cust("E2", "B1", 5_000),
        _cust("E2", "B2", 7_000),
    ])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)

    text = generate_audit_paragraph(ev, diff, account_rows=rows)
    assert "Evidence by account:" not in text
