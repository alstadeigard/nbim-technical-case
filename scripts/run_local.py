"""
Entry script: run reconciliation, print summaries, and include per-account evidence in the audit text.
"""

import os
import sys

# Ensure src/ is on sys.path
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, os.pardir))
sys.path.insert(0, os.path.join(root, "src"))

from recon.orchestrator import run
from recon.audit import generate_audit_paragraph
from recon.attribution import per_account_attribution
from recon.policy import risk_and_policy


def main() -> None:
    """
    Load CSVs, run reconciliation, print numeric summary and audit paragraph per event,
    including per-account evidence lines within the paragraph.
    """
    nbim_path = os.path.join(root, "data", "NBIM_Dividend_Bookings 1.csv")
    custody_path = os.path.join(root, "data", "CUSTODY_Dividend_Bookings 1.csv")

    events, diffs = run(nbim_path, custody_path)

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

        # Per-account rows (used both for printing and to embed in audit text)
        rows = per_account_attribution(ev)

        # Single, portable audit paragraph with embedded account evidence lines
        print(generate_audit_paragraph(ev, d, account_rows=rows))

        # Also print a compact per-account table if there are interesting deltas
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

        print("-" * 80)


if __name__ == "__main__":
    main()
