"""
RunLogger basic behavior: creates JSONL file and records expected fields.
"""

import json
import os
import tempfile
from src.recon.runlog import RunLogger


def test_runlogger_writes_jsonl_lines():
    with tempfile.TemporaryDirectory() as td:
        os.environ["LOG_DIR"] = td
        rl = RunLogger()
        rl.log_run_start({"foo": "bar"})
        rl.log("llm_classify", {"provider": "openai", "model": "gpt-4o-mini"})
        rl.log_event_summary(
            event_id="E1",
            diff={"amount_delta_qc": 1.0},
            risk={"risk_score": 0.1, "require_review": False, "auto_close": True},
            classification={"break_types": ["No_break_detected"], "severity": "low", "confidence": 0.3, "hypothesized_causes": []},
            actions=["ok"],
            audit_text="audit",
            per_account=[{"bank_account": "A"}],
        )

        # Verify file exists and has multiple JSON lines
        files = [f for f in os.listdir(td) if f.endswith(".jsonl")]
        assert len(files) == 1
        path = os.path.join(td, files[0])
        with open(path, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        assert len(lines) >= 3

        # Basic shape check of first record
        rec = json.loads(lines[0])
        assert "ts" in rec and "run_id" in rec and "stage" in rec and "payload" in rec
