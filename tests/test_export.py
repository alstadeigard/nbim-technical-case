"""
Tests for JSON export payload shape (export.py).
"""

import pandas as pd
from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.classify import classify
from src.recon.policy import risk_and_policy
from src.recon.attribution import per_account_attribution
from src.recon.audit import generate_audit_paragraph
from src.recon.export import build_event_payload


def _nbim(event_id="E", bank="ACC1", shares=1000, qc=1.0):
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": "01.01.2025",
        "PAYMENT_DATE": "02.01.2025",
        "QUOTATION_CURRENCY": "USD",
        "SETTLEMENT_CURRENCY": "USD",
        "NOMINAL_BASIS": shares,
        "DIVIDENDS_PER_SHARE": qc,
        "GROSS_AMOUNT_QUOTATION": shares * qc,
        "NET_AMOUNT_QUOTATION": shares * qc,
        "NET_AMOUNT_SETTLEMENT": shares * qc,
        "WTHTAX_RATE": 0.0,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0,
        "BANK_ACCOUNT": bank,
    }


def _cust(event_id="E", bank="ACC1", shares=1000, qc=1.0):
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


def test_build_event_payload_has_required_keys():
    nbim = pd.DataFrame([_nbim(event_id="E1")])
    custody = pd.DataFrame([_cust(event_id="E1")])

    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    cls = classify(diff)
    rp = risk_and_policy(ev, diff)
    rows = per_account_attribution(ev)
    text = generate_audit_paragraph(ev, diff, account_rows=rows)

    payload = build_event_payload(
        event=ev,
        diff=diff,
        classification=cls,
        risk=rp,
        per_account_rows=rows,
        audit_text=text,
    )

    # Top-level keys
    for key in [
        "event_id", "isin", "ex_date", "pay_date",
        "quotation_ccy", "settlement_ccy",
        "nbim", "nbim_accounts", "custody_legs",
        "diff", "classification", "risk", "per_account", "audit_text",
    ]:
        assert key in payload

    # Sanity on nested structures
    assert isinstance(payload["nbim"], dict)
    assert isinstance(payload["nbim_accounts"], list)
    assert isinstance(payload["custody_legs"], list)
    assert isinstance(payload["diff"], dict)
    assert isinstance(payload["classification"], dict)
    assert isinstance(payload["risk"], dict)
    assert isinstance(payload["per_account"], list)
    assert isinstance(payload["audit_text"], str)
