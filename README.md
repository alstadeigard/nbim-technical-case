# NBIM Dividend Reconciliation (Technical Case)

This repository contains a prototype reconciliation engine for NBIM’s dividend bookings.
It ingests internal NBIM data and custodian data, computes diffs, classifies breaks,
assesses risk, generates natural-language audit trails, and suggests remediation actions.
Optionally, it integrates with LLMs for richer classification.

## Features
- Ingest & Harmonize: read NBIM / Custody CSVs, normalize to canonical schema.
- Diff Engine: compute deltas (amounts, FX, tax, shares, timing).
- Policy & Risk: deterministic scoring, `require_review` and `auto_close` flags.
- Classification: rules-based and optional LLM-based (OpenAI).
- Audit Trails: natural-language summaries and per-account attribution.
- Remediation: prioritized next-step suggestions.
- Artifacts: per-event JSON payloads + `summary.csv`.
- Tests: unit tests + CLI integration test.

## Installation
```bash
git clone <repo-url>
cd nbim-technical-case
python -m venv .venv
.venv\Scripts\activate   # on Windows
pip install -r requirements.txt
```

## Usage

### Rules-only mode (no LLM calls)
```bash
python scripts/run_local.py --out artifacts --summary-csv summary.csv
```

### With LLM classification (OpenAI)
```bash
setx OPENAI_API_KEY "sk-..."   # Windows PowerShell
python scripts/run_local.py --use-llm --llm-provider openai --llm-model gpt-4o-mini --out artifacts --summary-csv summary.csv
```

### Outputs
- `artifacts/<event_id>.json` — per-event payload with diff, risk, classification, remediation, audit text.
- `artifacts/summary.csv` — flat summary across all events.
- Console logs show deltas, risk, classification, actions, and audit text.

## Running tests
```bash
pytest
```

## Data switching (use different CSVs)
```bash
python scripts/run_local.py \
  --nbim path/to/NBIM_file.csv \
  --custody path/to/CUSTODY_file.csv \
  --out artifacts \
  --summary-csv summary.csv
```

Notes:
- Paths can be relative or absolute.
- If `--summary-csv summary.csv` and `--out <dir>` are both provided, the summary is written inside `<dir>/summary.csv`.
