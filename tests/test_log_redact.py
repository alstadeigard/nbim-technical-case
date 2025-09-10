"""
Verify RunLogger redaction hides prompts/responses and audit_text when enabled.
"""

import json
import os
import tempfile
from src.recon.runlog import RunLogger


def test_redaction_hides_fields():
    with tempfile.TemporaryDirectory() as td:
        os.environ["LOG_DIR"] = td
        rl = RunLogger(redact=True)
        rl.log_llm_classify(
            provider="openai",
            model="gpt-4o-mini",
            system="SYSTEM_PROMPT",
            user="USER_PROMPT",
            response_text='{"ok":true}',
            cache_hit=False,
            budget_blocked=False,
            est_in_tokens=100,
            out_tokens=50,
            cost_usd=0.001,
            event_id="E1",
        )
        rl.log_event_summary(
            event_id="E1",
            diff={"x": 1},
            risk={"y": 2},
            classification={"break_types": ["No_break_detected"], "severity": "low", "confidence": 0.3, "hypothesized_causes": []},
            actions=["do"],
            audit_text="SHOULD_BE_REDACTED",
            per_account=[{"bank_account": "A"}],
        )

        files = [f for f in os.listdir(td) if f.endswith(".jsonl")]
        assert len(files) == 1
        path = os.path.join(td, files[0])
        lines = [l for l in open(path, "r", encoding="utf-8").read().splitlines() if l.strip()]
        assert len(lines) >= 2

        rec1 = json.loads(lines[0])["payload"]
        assert rec1["system"] == "<redacted:system>"
        assert rec1["user"] == "<redacted:user>"
        assert rec1["response"] == "<redacted:response>"

        rec2 = json.loads(lines[1])["payload"]
        assert rec2["audit_text"] == "<redacted:audit_text>"
