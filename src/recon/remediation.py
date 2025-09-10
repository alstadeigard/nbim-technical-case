"""
Generate actionable remediation suggestions from a classified reconciliation event.

This module creates concise, next-step actions based on:
- break_types (from LLM or rules),
- numeric diffs (amounts, FX, tax, shares, dates),
- per-account attribution evidence.

Output is a list of human-readable bullet items (strings), ordered by priority.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Any

from .schemas import CanonicalEvent, DiffRecord


def _acct_evidence(per_account_rows: Iterable[Dict[str, Any]]) -> List[str]:
    """
    Extract and format account evidence from per-account attribution rows.
    
    Args:
        per_account_rows: Iterable of per-account attribution dictionaries
        
    Returns:
        List of formatted evidence strings showing account deltas
    """
    rows = list(per_account_rows)
    # Keep only rows with notable deltas
    interesting = [
        r for r in rows
        if abs(r.get("share_delta", 0)) != 0
        or abs(r.get("net_qc_delta", 0.0)) > 0.0
        or abs(r.get("net_sc_delta", 0.0)) > 0.0
    ]
    # Format as ACCOUNT: (changes)
    formatted = []
    for r in interesting:
        acct = str(r.get("bank_account") or "(blank)")
        sd = int(r.get("share_delta", 0))
        qc = float(r.get("net_qc_delta", 0.0))
        sc = float(r.get("net_sc_delta", 0.0))
        formatted.append(f"{acct} (SharesΔ={sd}, QCΔ={qc:.2f}, SCΔ={sc:.2f})")
    return formatted


def _priority_tag(severity: str, require_review: bool) -> str:
    """
    Generate priority tag based on severity and review requirements.
    
    Args:
        severity: Severity level ("low", "medium", "high")
        require_review: Whether manual review is required
        
    Returns:
        Priority tag string ([P1], [P2], or [P3])
    """
    if require_review or severity == "high":
        return "[P1]"
    if severity == "medium":
        return "[P2]"
    return "[P3]"


def suggest_remediation(
    *,
    event: CanonicalEvent,
    diff: DiffRecord,
    classification: Dict[str, Any],
    per_account_rows: Iterable[Dict[str, Any]],
    risk: Dict[str, Any],
) -> List[str]:
    """
    Turn an event's state into prioritized, concrete next-step actions.
    """
    break_types = [str(b) for b in classification.get("break_types", [])]
    severity = str(classification.get("severity", "low"))
    require_review = bool(risk.get("require_review", False))
    tag = _priority_tag(severity, require_review)
    actions: List[str] = []

    evidence = _acct_evidence(per_account_rows)
    ev_accounts = f" Evidence: {', '.join(evidence)}" if evidence else ""

    # Quantity mismatch
    if "Quantity_mismatch" in break_types:
        actions.append(
            f"{tag} Verify positions vs. custody for {event.isin}: reconcile "
            f"NBIM shares ({int(event.nbim.shares)}) with custody total; "
            f"investigate loans/recalls and corporate actions.{ev_accounts}"
        )
        if diff.share_diff_after_loan != 0:
            actions.append(
                f"{tag} Check latest share movements around EX/PAY dates (fails/late receipts). "
                f"Confirm lending records and recalls cover {int(diff.loan_total)} shares."
            )

    # Tax rate mismatch
    if "Tax_rate_mismatch" in break_types:
        actions.append(
            f"{tag} Validate withholding rate for {event.isin}: treaty rate vs. custody rate. "
            "Confirm residency docs, relief-at-source setup, and corporate action tax flags."
        )

    # Timing mismatch
    if "Timing_mismatch" in break_types:
        actions.append(
            f"{tag} Align cash value dates for {event.isin}: compare custodian PAY_DATE vs internal. "
            "Check market calendars/holidays and settlement cutoffs; post timing adjustment if needed."
        )

    # FX mismatch
    if "FX_mismatch" in break_types or abs(diff.fx_delta) > 0.000001:
        actions.append(
            f"{tag} Reconcile FX for {event.isin}: verify custodian FX ({event.settlement_ccy}) source/time "
            "vs. NBIM policy rate; confirm cross-currency reversal flags and applied rate."
        )

    # Amount delta unexplained or any non-zero amounts
    if "Amount_delta_unexplained" in break_types or abs(diff.amount_delta_qc) > 0.0 or abs(diff.amount_delta_sc) > 0.0:
        actions.append(
            f"{tag} Trace amount delta for {event.isin}: recompute gross→net with tax/fees; "
            "confirm fee buckets (ADR/local charges) and rounding rules in both systems."
        )

    # Low/no break
    if not actions:
        actions.append(f"{tag} No break to remediate for {event.isin}; auto-close per policy if permitted.")

    # De-duplicate while preserving order
    seen = set()
    dedup: List[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            dedup.append(a)
    return dedup
