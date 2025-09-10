# Demo Script (Interview Presentation)

Cheat sheet for a concise demo.

## 1) Setup
```powershell
.venv\Scripts\activate
```

## 2) Run (rules-only)
```powershell
python scripts/run_local.py --out artifacts --summary-csv summary.csv
```
Talking points:
- Walk through console lines: deltas, risk score, classification, audit summary.
- Show `artifacts/summary.csv` and one `artifacts/<event_id>.json`.

## 3) Run (with LLM)
```powershell
setx OPENAI_API_KEY "sk-..."   # if not already set
python scripts/run_local.py --use-llm --llm-provider openai --llm-model gpt-4o-mini --out artifacts --summary-csv summary.csv
```
Talking points:
- Highlight "Causes" and "Next actions" lines.
- Emphasize deterministic rules baseline + LLM as advisory.

## 4) Tests
```powershell
pytest
```
Talking points:
- All tests pass, including CLI integration.

## 5) Switching data
```powershell
python scripts/run_local.py --nbim alt/NBIM.csv --custody alt/CUST.csv --out artifacts --summary-csv summary.csv
```
Talking points:
- No code changes required; flags control inputs.
