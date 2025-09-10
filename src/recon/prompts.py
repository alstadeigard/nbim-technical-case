"""
Prompt builders for LLM-powered components.
"""

from __future__ import annotations

from typing import Iterable, Dict
import json


_CLASSIFY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "break_types": {
            "type": "array",
            "items": {"type": "string"},
        },
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "hypothesized_causes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["break_types", "severity", "hypothesized_causes", "confidence"],
    "additionalProperties": False,
}


def classification_schema_json() -> str:
    """
    Return the JSON schema string used to validate the LLM classification output.
    """
    return json.dumps(_CLASSIFY_JSON_SCHEMA, separators=(",", ":"))


def build_classify_messages(
    *,
    event_meta: Dict[str, str],
    diff_summary: Dict[str, float | int],
    per_account_rows: Iterable[Dict[str, object]],
) -> Dict[str, str]:
    """
    Build system and user messages for the classification task.
    The LLM must return a JSON object conforming to classification_schema_json().
    """
    sys = (
        "You are a meticulous financial reconciliation assistant. "
        "Your only output must be a single JSON object that conforms to the provided JSON schema. "
        "Do not include any text before or after the JSON. "
        "Use only the evidence provided. If multiple break types plausibly apply, include them all. "
        "Be conservative with confidence."
    )

    user_payload = {
        "event": {
            "event_id": event_meta.get("event_id"),
            "isin": event_meta.get("isin"),
            "quotation_ccy": event_meta.get("quotation_ccy"),
            "settlement_ccy": event_meta.get("settlement_ccy"),
            "pay_date": event_meta.get("pay_date"),
            "ex_date": event_meta.get("ex_date"),
        },
        "diff": diff_summary,
        "per_account": list(per_account_rows),
        "json_schema": _CLASSIFY_JSON_SCHEMA,
        "instructions": (
            "Return JSON only. Typical break types include: "
            "FX_mismatch, Tax_rate_mismatch, Quantity_mismatch, Timing_mismatch, Amount_delta_unexplained. "
            "Choose severity: low/medium/high; include hypothesized_causes; set confidence in [0,1]."
        ),
    }
    usr = json.dumps(user_payload, ensure_ascii=False)

    return {"system": sys, "user": usr}
