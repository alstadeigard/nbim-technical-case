"""
Tests for LLM-backed classification using monkeypatch to avoid real API calls.
"""

import json
import pandas as pd
import types

from src.recon.harmonize import to_canonical
from src.recon.diff import compute_diff
from src.recon.attribution import per_account_attribution
from src.recon.classify_llm import classify_llm
import src.recon.llm_client as llm_client_mod


def _nbim(event_id="E", bank="ACC1", shares=1000, qc=1.0):
    amt = shares * qc
    return {
        "COAC_EVENT_KEY": event_id,
        "ISIN": "X",
        "EXDATE": "01.01.2025",
        "PAYMENT_DATE": "02.01.2025",
        "QUOTATION_CURRENCY": "USD",
        "SETTLEMENT_CURRENCY": "USD",
        "NOMINAL_BASIS": shares,
        "DIVIDENDS_PER_SHARE": qc,
        "GROSS_AMOUNT_QUOTATION": amt,
        "NET_AMOUNT_QUOTATION": amt,
        "NET_AMOUNT_SETTLEMENT": amt,
        "WTHTAX_RATE": 0.0,
        "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO": 1.0,
        "BANK_ACCOUNT": bank,
    }


def _cust(event_id="E", bank="ACC1", shares=1000, net_qc=None, net_sc=None, tax=0.0):
    if net_qc is None:
        net_qc = shares * 1.0
    if net_sc is None:
        net_sc = net_qc
    return {
        "COAC_EVENT_KEY": event_id,
        "GROSS_AMOUNT": net_qc + tax,
        "NET_AMOUNT_QC": net_qc,
        "NET_AMOUNT_SC": net_sc,
        "TAX": tax,
        "FX_RATE": 1.0,
        "HOLDING_QUANTITY": shares,
        "BANK_ACCOUNTS": bank,
        "PAY_DATE": "02.01.2025",
        "LOAN_QUANTITY": 0.0,
    }


def test_classify_llm_parses_valid_json(monkeypatch):
    """
    LLM returns a valid JSON — ensure we parse, validate, and return same shape.
    """
    # Build a trivial event with a SC amount delta
    nbim = pd.DataFrame([_nbim(event_id="E1", shares=1000, qc=1.0)])
    custody = pd.DataFrame([_cust(event_id="E1", shares=1000, net_qc=900.0, net_sc=900.0, tax=100.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)

    fake_json = json.dumps({
        "break_types": ["Amount_delta_unexplained"],
        "severity": "medium",
        "hypothesized_causes": ["Rounding difference", "Fee treatment mismatch"],
        "confidence": 0.62,
    })

    # Monkeypatch LLMClient.classify_json to return our fake JSON
    def fake_classify_json(self, system, user, max_tokens=800):
        return fake_json

    monkeypatch.setattr(llm_client_mod.LLMClient, "classify_json", fake_classify_json, raising=True)

    out = classify_llm(event=ev, diff=diff, per_account_rows=rows, provider="openai", model="gpt-4o-mini")
    assert out["break_types"] == ["Amount_delta_unexplained"]
    assert out["severity"] == "medium"
    assert out["confidence"] == 0.62
    assert "hypothesized_causes" in out and len(out["hypothesized_causes"]) >= 1


def test_classify_llm_fallback_on_invalid_json(monkeypatch):
    """
    LLM returns invalid JSON — ensure we fall back to deterministic rules.
    """
    nbim = pd.DataFrame([_nbim(event_id="E2", shares=1000, qc=1.0)])
    custody = pd.DataFrame([_cust(event_id="E2", shares=1000, net_qc=1000.0, net_sc=1000.0, tax=0.0)])
    ev = to_canonical(nbim, custody)[0]
    diff = compute_diff(ev)
    rows = per_account_attribution(ev)

    # Return garbage; parser will fail → fallback to rule-based
    def fake_bad(self, system, user, max_tokens=800):
        return "not-json"

    monkeypatch.setattr(llm_client_mod.LLMClient, "classify_json", fake_bad, raising=True)

    out = classify_llm(event=ev, diff=diff, per_account_rows=rows, provider="openai", model="gpt-4o-mini")
    assert out["break_types"] == ["No_break_detected"]
    assert out["severity"] in ("low", "medium", "high")
    assert isinstance(out["confidence"], float)
