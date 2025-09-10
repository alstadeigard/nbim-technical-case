# NBIM Dividend Reconciliation

System for reconciling NBIM’s internal dividend bookings with Custodian records.  
The repository is organized for incremental development and extension.

## Repository Layout
- `data/` — CSV files for NBIM and Custody inputs.
- `src/recon/` — core modules:
  - `ingest.py` — CSV loading.
  - `harmonize.py` — normalize NBIM and Custody records into a canonical model.
  - `match.py` — event matching logic.
  - `diff.py` — compute deterministic differences between NBIM and Custody.
  - `schemas.py` — Pydantic data contracts.
  - `orchestrator.py` — pipeline runner.
- `scripts/` — entrypoints for running the reconciliation locally.
- `tests/` — unit tests.

## Setup
```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

