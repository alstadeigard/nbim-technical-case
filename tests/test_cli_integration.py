"""
End-to-end CLI test (rules-only, no LLM call).

It runs `python scripts/run_local.py` against the repo's sample CSVs,
writes artifacts into a temporary directory, and asserts that:
  - event JSON files are created
  - a summary.csv is written and has the expected header
We use --log-redact to keep logs privacy-safe.
"""

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_rules_end_to_end():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "run_local.py"

    # Sanity: inputs exist
    nbim_csv = repo_root / "data" / "NBIM_Dividend_Bookings 1.csv"
    custody_csv = repo_root / "data" / "CUSTODY_Dividend_Bookings 1.csv"
    assert nbim_csv.exists(), f"Missing {nbim_csv}"
    assert custody_csv.exists(), f"Missing {custody_csv}"

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)

        # Run in rules-only mode (no network/API), redacted logs
        cmd = [
            sys.executable,
            str(script),
            "--out",
            str(out_dir),
            "--summary-csv",
            "summary.csv",
            "--log-redact",
        ]
        # Use default --nbim and --custody which point to /data files.
        cp = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)

        # Debug output in case of failure
        stdout = cp.stdout
        stderr = cp.stderr
        assert "Summary written to" in stdout, f"Unexpected stdout:\n{stdout}\n---\n{stderr}"

        # Expected artifacts
        expected_events = {"950123456.json", "960789012.json", "970456789.json"}
        produced = {p.name for p in out_dir.iterdir() if p.suffix == ".json"}
        missing = expected_events - produced
        assert not missing, f"Missing JSON artifacts: {missing}; produced={produced}"

        # Summary CSV
        summary_path = out_dir / "summary.csv"
        assert summary_path.exists(), "summary.csv not created"
        with summary_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
        expected_headers = [
            "event_id",
            "isin",
            "ex_date",
            "pay_date",
            "q_ccy",
            "s_ccy",
            "amount_delta_qc",
            "amount_delta_sc",
            "fx_delta",
            "wht_rate_delta_pp",
            "pay_date_offset_days",
            "shares_delta",
            "shares_delta_after_loan",
            "risk_score",
            "require_review",
            "auto_close",
            "break_types",
            "severity",
            "confidence",
        ]
        assert headers == expected_headers, f"Unexpected summary header: {headers}"
