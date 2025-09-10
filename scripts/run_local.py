"""
Entry script: run reconciliation with optional LLM-backed classification.

Usage:
    python scripts/run_local.py
    python scripts/run_local.py --out artifacts --summary-csv summary.csv
    python scripts/run_local.py --use-llm --llm-provider openai --llm-model gpt-4o-mini --out artifacts --summary-csv summary.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, List, Dict

# Ensure src/ is on sys.path
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, os.pardir))
sys.path.insert(0, os.path.join(root, "src"))

from recon.orchestrator import run
from recon.audit import generate_audit_paragraph
from recon.attribution import per_account_attribution
from recon.policy import risk_and_policy
from recon.classify import classify as classify_rules
from recon.classify_llm import classify_llm
from recon.remediation import suggest_remediation
from recon.export import build_event_payload, write_event_json
from recon.summary import build_summary_dataframe
from recon.runlog import RunLogger


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NBIM dividend reconciliation runner")
    p.add_argument("--nbim", type=str, default=os.path.join(root, "data", "NBIM_Dividend_Bookings 1.csv"))
    p.add_argument("--custody", type=str, default=os.path.join(root, "data", "CUSTODY_Dividend_Bookings 1.csv"))
    p.add_argument("--out", type=str, default=None, help="Directory to write one JSON file per event")
    p.add_argument(
        "--summary-csv",
        type=str,
        default=None,
        help="If set and --out is also set to a directory, 'summary.csv' will be written inside that directory unless a full path is provided.",
    )
    p.add_argument("--use-llm", action="store_true", help="Use LLM-backed classification.")
    p.add_argument("--llm-provider", type=str, default=None, help="openai | anthropic")
    p.add_argument("--llm-model", type=str, default=None, help="Model name, e.g., gpt-4o-mini")
    return p.parse_args()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def main() -> None:
    args = _parse_args()

    run_logger = RunLogger()
    run_logger.log_run_start(
        {
            "nbim": args.nbim,
            "custody": args.custody,
            "out": args.out,
            "summary_csv": args.summary_csv,
            "use_llm": bool(args.use_llm),
            "llm_provider": args.llm_provider or "openai",
            "llm_model": args.llm_model or "gpt-4o-mini",
        }
    )

    events, diffs = run(args.nbim, args.custody)

    export_dir: Optional[str] = args.out
    if export_dir:
        _ensure_dir(export_dir)

    risks: List[Dict[str, object]] = []
    classes: List[Dict[str, object]] = []

    for ev, d in zip(events, diffs):
        print(
            f"{ev.event_id} | QCΔ={d.amount_delta_qc:.2f} | SCΔ={d.amount_delta_sc:.2f} "
            f"| WHTΔ={d.wht_rate_delta:.2f}pp | FXΔ={d.fx_delta:.6f} "
            f"| PayΔ={d.date_offset_pay_abs_days}d | SharesΔ={d.share_diff:.2f} "
            f"| LoanΣ={d.loan_total:.2f} | SharesΔ(loan-adj)={d.share_diff_after_loan:.2f}"
        )

        rp = risk_and_policy(ev, d, cfg=None)
        risks.append(rp)
        print(f"Risk: score={rp['risk_score']:.2f} | require_review={rp['require_review']} | auto_close={rp['auto_close']}")

        rows = per_account_attribution(ev)
        if args.use_llm:
            cls = classify_llm(
                event=ev,
                diff=d,
                per_account_rows=rows,
                provider=args.llm_provider,
                model=args.llm_model,
                run_logger=run_logger,
            )
            source = "LLM"
        else:
            cls = classify_rules(d)
            source = "rules"
        classes.append(cls)
        print(f"Classify[{source}]: types={cls['break_types']} severity={cls['severity']} confidence={cls['confidence']}")

        causes = cls.get("hypothesized_causes") or []
        if causes:
            print("Causes:", "; ".join(str(c) for c in causes))

        actions = suggest_remediation(event=ev, diff=d, classification=cls, per_account_rows=rows, risk=rp)
        if actions:
            print("Next actions:")
            for a in actions:
                print(f"  - {a}")

        audit_text = generate_audit_paragraph(ev, d, account_rows=rows)
        print(audit_text)

        interesting = [
            r for r in rows
            if abs(r["share_delta"]) > 0.0 or abs(r["net_qc_delta"]) > 0.0 or abs(r["net_sc_delta"]) > 0.0
        ]
        if interesting:
            print("Per-account attribution:")
            for r in rows:
                acct = r["bank_account"] or "(blank)"
                print(
                    f"  - {acct}: SharesΔ={r['share_delta']:.0f}, "
                    f"QCΔ={r['net_qc_delta']:.2f}, SCΔ={r['net_sc_delta']:.2f} "
                    f"(NBIM shares={r['nbim_shares']:.0f}, Custody shares={r['custody_shares']:.0f})"
                )

        # Persist per-event structured log for audit
        run_logger.log_event_summary(
            event_id=ev.event_id,
            diff={
                "amount_delta_qc": float(d.amount_delta_qc),
                "amount_delta_sc": float(d.amount_delta_sc),
                "wht_rate_delta": float(d.wht_rate_delta),
                "fx_delta": float(d.fx_delta),
                "date_offset_pay_abs_days": int(d.date_offset_pay_abs_days),
                "share_diff": float(d.share_diff),
                "loan_total": float(d.loan_total),
                "share_diff_after_loan": float(d.share_diff_after_loan),
            },
            risk={
                "risk_score": float(rp.get("risk_score", 0.0)),
                "require_review": bool(rp.get("require_review", False)),
                "auto_close": bool(rp.get("auto_close", False)),
            },
            classification={
                "break_types": list(cls.get("break_types", [])),
                "severity": str(cls.get("severity")),
                "confidence": float(cls.get("confidence", 0.0)),
                "hypothesized_causes": list(cls.get("hypothesized_causes", [])),
            },
            actions=list(actions),
            audit_text=audit_text,
            per_account=list(rows),
        )

        if export_dir:
            payload = build_event_payload(
                event=ev,
                diff=d,
                classification=cls,
                risk=rp,
                per_account_rows=rows,
                audit_text=audit_text,
                actions=actions,
            )
            out_path = os.path.join(export_dir, f"{ev.event_id}.json")
            write_event_json(out_path, payload)

        print("-" * 80)

    if args.summary_csv:
        out_path = args.summary_csv
        if args.summary_csv == "summary.csv" and export_dir:
            out_path = os.path.join(export_dir, "summary.csv")
        df = build_summary_dataframe(events, diffs, risks, classes)
        df.to_csv(out_path, index=False)
        print(f"Summary written to: {out_path}")


if __name__ == "__main__":
    main()
