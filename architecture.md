# Architecture Vision — LLM-Powered Dividend Reconciliation

## 1) Purpose
Create a reliable, explainable reconciliation system that:
- Detects & classifies breaks across NBIM vs Custody dividend data.
- Produces natural-language audit trails and prioritized remediation steps.
- Uses LLMs for classification/causality **without** sacrificing determinism or control.
- Scales to thousands of events/day with strong safeguards for financial operations.

---

## 2) Design Principles
- **Deterministic baseline, AI assist:** Rules compute diffs and risk; LLMs add rationale and triage hints.
- **Agentic pipeline:** Small, single-purpose agents coordinated by an orchestrator.
- **Explainability first:** Every decision emits a structured payload + human audit text.
- **Idempotent & observable:** Pure functions where possible; artifacts/logs for replay.
- **Security & safety:** No autonomous posting; guarded actions; PII-safe logs (redaction on).

---

## 3) System Overview (Logical)
```
             +-----------------+
   NBIM CSV  |                 |   Custody CSV
────────────▶|   Ingest Agent  |◀──────────────
             |  (parsers, QC)  |
             +--------┬--------+
                      │ Canonical Events
                      ▼
             +-----------------+
             |  Diff Agent     |  (amounts, FX, dates, shares, tax)
             +--------┬--------+
                      │ Diff Records
                      ▼
             +-----------------+           +------------------+
             | Risk/Policy     |           | Classifier Agent |
             |  (deterministic)|◀──────────|  (Rules + LLM)   |
             +--------┬--------+           +------------------+
                      │ Decisions                  ▲
                      ▼                             │ optional
             +-----------------+                   LLM API
             | Audit Agent     |
             | (NL summaries)  |
             +--------┬--------+
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
+------------------+     +------------------+
| Remediation Agent|     | Attribution Agent|
| (next actions)   |     | (per-account)    |
+--------┬---------+     +--------┬---------+
         │                         │
         ▼                         ▼
   +------------+            +-------------+
   | Exporter   |            | Run Logger  |
   | (JSON/CSV) |            | (redacted)  |
   +------------+            +-------------+
```

**Orchestrator** coordinates agents, handles flags (`--use-llm`, data paths), and writes artifacts.

---

## 4) Key Components (Agents)

1) **Ingest Agent**
- Parses NBIM/Custody CSV (schema validation, type normalization, date/ccy normalization).
- Emits canonical event with NBIM leg + custody legs by bank account.
- **Patterns:** Adapter (per source), Validator.

2) **Diff Agent**
- Computes deltas: quotation/settlement amounts, implied FX, withholding tax pp, pay-date offsets, share deltas (pre/post loan).
- **Patterns:** Pure function; Strategy (diff rules).

3) **Risk/Policy**
- Deterministic scoring from diffs; thresholds for `require_review` and `auto_close`.
- Guardrails: no auto-close when shares/SC deltas exist.
- **Patterns:** Policy object.

4) **Classifier Agent (Rules + LLM)**
- Rules produce stable break types; **optional** LLM enriches with causes, severity hints, and next-step context.
- LLM outputs are treated as *advisory metadata* (not state-changing).
- **Patterns:** Decorator (LLM layer wraps rules), Facade (single classify entrypoint).

5) **Audit Agent**
- Generates concise, human-readable summaries tied to numerical evidence.
- **Patterns:** Template Method (consistent tone/structure).

6) **Attribution Agent**
- Breaks down differences by bank account for targeted remediation.
- **Patterns:** Aggregator.

7) **Remediation Agent**
- Produces prioritized actions (P1/P3) mapped to break types and evidence.
- **Patterns:** Rules engine; Priority queue.

8) **Exporter**
- Writes per-event JSON payloads and roll-up `summary.csv`.
- **Patterns:** DTO/Serializer.

9) **Run Logger**
- Structured logs, PII-redaction (`--log-redact`), prompt/response elision.

---

## 5) Data Contracts (selected)
- **Canonical Event**: `{ event_id, isin, ex_date, pay_date, quotation_ccy, settlement_ccy, nbim:{...}, custody_legs:[...] }`
- **Diff Record**: `{ amount_delta_qc, amount_delta_sc, fx_delta, wht_rate_delta, date_offset_pay_abs_days, share_diff, loan_total, share_diff_after_loan }`
- **Classification**: `{ break_types[], severity, confidence, hypothesized_causes[] }`
- **Risk/Policy**: `{ risk_score, require_review, auto_close }`
- **Per-Account Row**: `{ bank_account, nbim_shares, custody_shares, share_delta, nbim_net_qc, custody_net_qc, net_qc_delta, nbim_net_sc, custody_net_sc, net_sc_delta }`
- **Event Payload (exported JSON)** includes all of the above + `audit_text` and `actions[]`.

Contracts are **append-only** to preserve backward compatibility.

---

## 6) LLM Use and Safeguards
- **LLM scope:** classification hints (types, severity, causes) + remediation suggestions; never posts bookings or changes source data.
- **Budget control:** optional; can add token meter / max calls per run.
- **Redaction:** `--log-redact` removes sensitive fields from logs; prompts kept minimal and numeric.
- **Determinism:** all critical decisions (risk, pass/fail, auto_close) are rules-based.
- **Fail-safe:** LLM timeouts/errors fall back to rules-only path; pipeline continues.

---

## 7) End-to-End Flows

### Normal flow (no breaks)
1. Ingest → Diff (all zeros) → Risk score 0 → Classifier (“No_break_detected”)  
2. Audit: confirms no deltas → Policy: `auto_close=True` → Export artifacts.

### Break with lending & tax/timing noise
1. Ingest → Diff (SC delta small, share diff offset by loans, tax pp mismatch)  
2. Risk score low/medium → LLM adds “rate mismatch” + “timing mismatch” causes  
3. Remediation suggests treaty validation + pay-date alignment → Export.

### Quantity mismatch on one account
1. Ingest → Diff (shares + amounts on a single bank account)  
2. Risk score high; `require_review=True`  
3. Attribution pinpoints offending account → P1 remediation → Export.

---

## 8) Scalability & Ops
- **Batchability:** Each event processed independently; easy to parallelize.
- **Throughput:** Diff/risk are O(n); LLM calls can be batched or limited.
- **Observability:** JSON artifacts + CSV + structured logs enable replay/slicing.
- **Deployment:** CLI today; can become scheduled job or service (REST/queue).

---

## 9) Extensibility Roadmap
- **More sources:** Additional custodian adapters (same canonical schema).
- **Policy tuning:** Thresholds per market/instrument; learned calibration (offline).
- **LLM plugins:** Retrieval augmentation (treaties/holiday calendars) for causes.
- **Workflow:** Human-in-the-loop UI to accept/annotate resolutions; export to ticketing.
- **Streaming:** Kafka/S3 triggers; incremental runs; dashboard views.

---

## 10) Risks & Mitigations (summary)
- **Model drift / non-determinism:** Rules baseline; test suite; versioned prompts.
- **PII/log leakage:** Redaction flag; minimal prompts; secrets in env.
- **Mis-prioritization:** Risk thresholds unit-tested; no autonomous actions.
- **Data variance:** Canonical schema + strict validators.
- **Cost spikes:** Optional call caps; rules-only mode as default.

---

## 11) Demo Command Cheatsheet
- Rules only:  
  `python scripts/run_local.py --out artifacts --summary-csv summary.csv`
- With LLM:  
  `python scripts/run_local.py --use-llm --llm-provider openai --llm-model gpt-4o-mini --out artifacts --summary-csv summary.csv`
- Switch data:  
  `python scripts/run_local.py --nbim <NBIM.csv> --custody <CUST.csv> --out artifacts --summary-csv summary.csv`
