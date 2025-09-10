"""
Config loader and accessors for the reconciler.

Loads YAML from a given path, falling back to sane defaults if keys are missing.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


_DEFAULTS: Dict[str, Any] = {
    "risk": {
        "weights": {
            "amount_delta_qc": 0.0005,
            "amount_delta_sc": 0.005,
            "shares_delta_after_loan": 0.001,
            "wht_rate_delta_pp": 0.25,
            "fx_delta_abs": 1.0,
            "pay_date_offset_days": 0.2,
        },
        "thresholds": {
            "review_score": 1.0,
            "auto_close_score": 0.2,
        },
        "caps": {"max_score": 5.0},
    },
    "formatting": {
        "rounding": {
            "amounts_dp": 2,
            "fx_dp": 6,
        }
    },
}


def _deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(dst)
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = dict(_DEFAULTS)
    if not path:
        return cfg
    if not os.path.exists(path):
        return cfg
    if yaml is None:
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        if isinstance(user_cfg, dict):
            cfg = _deep_update(cfg, user_cfg)
    except Exception:
        return dict(_DEFAULTS)
    return cfg


def risk_weight(cfg: Dict[str, Any], key: str) -> float:
    return float(cfg.get("risk", {}).get("weights", {}).get(key, _DEFAULTS["risk"]["weights"][key]))


def risk_threshold(cfg: Dict[str, Any], key: str) -> float:
    return float(cfg.get("risk", {}).get("thresholds", {}).get(key, _DEFAULTS["risk"]["thresholds"][key]))


def risk_cap(cfg: Dict[str, Any], key: str) -> float:
    return float(cfg.get("risk", {}).get("caps", {}).get(key, _DEFAULTS["risk"]["caps"][key]))


def rounding(cfg: Dict[str, Any], key: str) -> int:
    return int(cfg.get("formatting", {}).get("rounding", {}).get(key, _DEFAULTS["formatting"]["rounding"][key]))
