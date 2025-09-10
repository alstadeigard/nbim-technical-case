"""
Entry script: run reconciliation, print summaries, and (optionally) export JSON artifacts.

Usage:
    python scripts/run_local.py
    python scripts/run_local.py --out artifacts/    # writes one JSON per event into 'artifacts/'
    python scripts/run_local.py --nbim path/to/NBIM.csv --custody path/to/CUSTODY.csv --out outdir/
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

# Ensure src/ is on sys.path
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, os.pardir))
sys.path.insert(0, os.path.join(root, "src"))

from recon.orchestrator import run
from recon.audit import generate_audit_paragraph
from recon.attribution import per_account_attribution
from recon.policy import risk_and_policy
from recon.classify import classify
from recon.export import build_event_payload, write_event_json


def _parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments for flexible input paths and optional export directory.
    """
    p = argparse.ArgumentParser(description="NBIM dividend reconciliation runner")
    p.add_argument(
        "--nbim",
        type=str,
        default=os.path.join(root, "data", "NBIM_Dividend_Bookings 1.csv"),
        help="Path to NBIM CSV",
    )
    p.add_argument(
        "--custody",
        type=str,
        default=os.path.join(root, "data", "CUSTODY_Dividend_Bookings 1.csv"),
        help="Path to Custody CSV",
    )
    p.add_argument(
        "--out",
        type=str,
        default=None,
        help="If set, directory to write one JSON file per event",
    )
    return p.parse_args()


def _ensure_dir(path: str) -> None:
    """
    Create directory if it doesn't exist.
    """
    os.makedirs(path, exist_ok=True)


def main() -> None:
    """
    Load CSVs, run reconciliation, print numeric summary, risk flags, classification,
    and an audit paragraph per event with embedded per-account evidence. Optionally export JSON.
    """
    args = _parse_args()

    events, diffs = run(args.nbim, args.custody)

    # Export directory preparation (if requested)
    export_dir: Optional[str] = args.out
    if export_dir:
        _ensure_dir(export_dir)

    for ev, d in zip(events, diffs):
        # Aggregate numeric one-liner
        print(
            f"{ev.event_id} | QCΔ={d.amount_delta_qc:.2f} | SCΔ={d.amount_delta_sc:.2f} "
            f"| WHTΔ={d.wht_rate_delta:.2f}pp | FXΔ={d.fx_delta:.6f} "
            f"| PayΔ={d.date_offset_pay_abs_days}d | SharesΔ={d.share_diff:.2f} "
            f"| LoanΣ={d.loan_total:.2f} | SharesΔ(loan-adj)={d.share_diff_after_loan:.2f}"
        )

        # Risk flags
        rp = risk_and_policy(ev, d, cfg=None)
        print(f"Risk: score={rp['risk_score']:.2f} | require_review={rp['require_review']} | auto_close={rp['auto_close']}")

        # Deterministic classification
        cls = classify(d)
        print(
            "Classify:",
            f"types={cls['break_types']}",
            f"severity={cls['severity']}",
            f"confidence={cls['confidence']}",
        )

        # Per-account rows (used for evidence)
        rows = per_account_attribution(ev)

        # Single audit paragraph with embedded account evidence lines
        audit_text = generate_audit_paragraph(ev, d, account_rows=rows)
        print(audit_text)

        # Optional compact per-account table when interesting
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

        # Export if requested
        if export_dir:
            payload = build_event_payload(
                event=ev,
                diff=d,
                classification=cls,
                risk=rp,
                per_account_rows=rows,
                audit_text=audit_text,
            )
            out_path = os.path.join(export_dir, f"{ev.event_id}.json")
            write_event_json(out_path, payload)

        print("-" * 80)


if __name__ == "__main__":
    main()
