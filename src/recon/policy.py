"""
Risk scoring and policy decisions, parameterized by config.
"""

from __future__ import annotations

from typing import Dict, Any

from .schemas import CanonicalEvent
from .diff import DiffRecord
from .config import risk_weight, risk_threshold, risk_cap


def _bounded_score(x: float, cap: float) -> float:
    if x < 0:
        return 0.0
    if x > cap:
        return cap
    return x


def _score_from_diff(diff: DiffRecord, cfg: Dict[str, Any]) -> float:
    w_qc = risk_weight(cfg, "amount_delta_qc")
    w_sc = risk_weight(cfg, "amount_delta_sc")
    w_sh = risk_weight(cfg, "shares_delta_after_loan")
    w_tx = risk_weight(cfg, "wht_rate_delta_pp")
    w_fx = risk_weight(cfg, "fx_delta_abs")
    w_pd = risk_weight(cfg, "pay_date_offset_days")

    score = 0.0
    score += abs(diff.amount_delta_qc) * w_qc
    score += abs(diff.amount_delta_sc) * w_sc
    score += abs(diff.share_diff_after_loan) * w_sh
    score += abs(diff.wht_rate_delta) * w_tx
    score += abs(diff.fx_delta) * w_fx
    score += abs(diff.date_offset_pay_abs_days) * w_pd

    return _bounded_score(score, risk_cap(cfg, "max_score"))


def risk_and_policy(event: CanonicalEvent, diff: DiffRecord, cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = cfg or {}
    score = _score_from_diff(diff, cfg)
    review_th = risk_threshold(cfg, "review_score")
    auto_close_th = risk_threshold(cfg, "auto_close_score")
    require_review = bool(score >= review_th)
    auto_close = bool(score <= auto_close_th and diff.share_diff_after_loan == 0 and abs(diff.amount_delta_sc) == 0.0)
    return {"risk_score": round(score, 2), "require_review": require_review, "auto_close": auto_close}
