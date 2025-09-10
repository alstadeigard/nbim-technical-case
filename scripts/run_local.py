import os, sys
# so 'src/' is importable regardless of where we run from
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, os.pardir))
sys.path.insert(0, os.path.join(root, "src"))

from recon.orchestrator import run

if __name__ == "__main__":
    nbim_path = os.path.join(root, "data", "NBIM_Dividend_Bookings 1.csv")
    custody_path = os.path.join(root, "data", "CUSTODY_Dividend_Bookings 1.csv")
    events, diffs = run(nbim_path, custody_path)
    for ev, d in zip(events, diffs):
        print(f"{ev.event_id} | QCΔ={d.amount_delta_qc:.2f} | SCΔ={d.amount_delta_sc:.2f} "
              f"| WHTΔ={d.wht_rate_delta:.2f}pp | FXΔ={d.fx_delta:.6f} "
              f"| PayΔ={d.date_offset_pay_abs_days}d | SharesΔ={d.share_diff:.2f}")
