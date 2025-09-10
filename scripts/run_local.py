"""
Entry script to run reconciliation on NBIM vs Custody CSV files and print audit text.
"""

import os
import sys

# Ensure src/ is on sys.path
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, os.pardir))
sys.path.insert(0, os.path.join(root, "src"))

from recon.orchestrator import run
from recon.audit import generate_audit_paragraph


def main() -> None:
    """
    Load CSVs, run reconciliation, print numeric summary per event,
    then print a concise audit paragraph.
    """
    nbim_path = os.path.join(root, "data", "NBIM_Dividend_Bookings 1.csv")
    custody_path = os.path.join(root, "data", "CUSTODY_Dividend_Bookings 1.csv")

    events, diffs = run(nbim_path, custody_path)
    for ev, d in zip(events, diffs):
        print(
            f"{ev.event_id} | QCΔ={d.amount_delta_qc:.2f} | SCΔ={d.amount_delta_sc:.2f} "
            f"| WHTΔ={d.wht_rate_delta:.2f}pp | FXΔ={d.fx_delta:.6f} "
            f"| PayΔ={d.date_offset_pay_abs_days}d | SharesΔ={d.share_diff:.2f} "
            f"| LoanΣ={d.loan_total:.2f} | SharesΔ(loan-adj)={d.share_diff_after_loan:.2f}"
        )
        print(generate_audit_paragraph(ev, d))
        print("-" * 80)


if __name__ == "__main__":
    main()
