"""
Tests for per-account attribution of deltas.
"""

import pandas as pd
from src.recon.harmonize import to_canonical
from src.recon.attribution import per_account_attribution


def test_attribution_aligns_accounts_and_reports_deltas():
    nbim = pd.DataFrame([
        # Two NBIM accounts for same event
        {"COAC_EVENT_KEY": "E1", "ISIN": "X", "EXDATE": "01.01.2025", "PAYMENT_DATE": "02.01.2025",
         "QUOTATION_CURRENCY": "CHF", "SETTLEMENT_CURRENCY": "CHF",
         "NOMINAL_BASIS": 10_000, "DIVIDENDS_PER_SHARE": 1.0,
         "GROSS_AMOUNT_QUOTATION": 10_000, "NET_AMOUNT_QUOTATION": 10_000, "NET_AMOUNT_SETTLEMENT": 10_000,
         "WTHTAX_RATE": 0.0, "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0, "BANK_ACCOUNT": "A1"},
        {"COAC_EVENT_KEY": "E1", "ISIN": "X", "EXDATE": "01.01.2025", "PAYMENT_DATE": "02.01.2025",
         "QUOTATION_CURRENCY": "CHF", "SETTLEMENT_CURRENCY": "CHF",
         "NOMINAL_BASIS": 15_000, "DIVIDENDS_PER_SHARE": 1.0,
         "GROSS_AMOUNT_QUOTATION": 15_000, "NET_AMOUNT_QUOTATION": 15_000, "NET_AMOUNT_SETTLEMENT": 15_000,
         "WTHTAX_RATE": 0.0, "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0, "BANK_ACCOUNT": "A2"},
    ])
    custody = pd.DataFrame([
        # A1 matches; A2 has +2,000 shares and +2,000 QC/SC
        {"COAC_EVENT_KEY": "E1", "GROSS_AMOUNT": 10_000, "NET_AMOUNT_QC": 10_000, "NET_AMOUNT_SC": 10_000,
         "TAX": 0.0, "FX_RATE": 1.0, "HOLDING_QUANTITY": 10_000, "BANK_ACCOUNTS": "A1", "PAY_DATE": "02.01.2025"},
        {"COAC_EVENT_KEY": "E1", "GROSS_AMOUNT": 17_000, "NET_AMOUNT_QC": 17_000, "NET_AMOUNT_SC": 17_000,
         "TAX": 0.0, "FX_RATE": 1.0, "HOLDING_QUANTITY": 17_000, "BANK_ACCOUNTS": "A2", "PAY_DATE": "02.01.2025"},
    ])
    ev = to_canonical(nbim, custody)[0]
    rows = per_account_attribution(ev)
    by_acct = {r["bank_account"]: r for r in rows}
    assert by_acct["A1"]["share_delta"] == 0
    assert by_acct["A1"]["net_qc_delta"] == 0
    assert by_acct["A1"]["net_sc_delta"] == 0
    assert by_acct["A2"]["share_delta"] == 2000
    assert by_acct["A2"]["net_qc_delta"] == 2000
    assert by_acct["A2"]["net_sc_delta"] == 2000
