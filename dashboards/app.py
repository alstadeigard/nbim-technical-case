"""
A minimal, read-only Streamlit dashboard for NBIM Dividend Reconciliation.

Improvements over prior version:
- Clear, structured "Findings" bullets instead of dumping audit_text inline.
- "Evidence accounts" is explicitly defined as accounts with non-zero deltas.
- Per-account table is filtered to Evidence accounts by default (toggle to show all).
- The raw free-text audit trail remains available in an expander.

Run:
    streamlit run dashboards/app.py -- --artifacts artifacts --summary artifacts/summary.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Iterable

import pandas as pd
import streamlit as st


# ------------------------------ Helpers ---------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--artifacts", type=str, default="artifacts")
    p.add_argument("--summary", type=str, default=None)
    known, _ = p.parse_known_args(sys.argv[1:])
    return known


def load_summary(summary_path: Path) -> pd.DataFrame:
    if not summary_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(summary_path)
    except Exception:
        return pd.DataFrame()


def find_event_jsons(artifacts_dir: Path) -> List[Path]:
    if not artifacts_dir.exists():
        return []
    return sorted(artifacts_dir.glob("*.json"))


def load_event_payload(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def kpi(label: str, value: str):
    cols = st.columns(1)
    cols[0].metric(label, value)


def render_dataflow():
    st.subheader("Data flow")
    st.code(
        "NBIM CSV   Custody CSV\n"
        "   |            |\n"
        "   `- Ingest -> Canonical Events\n"
        "                 |\n"
        "              Diff Engine\n"
        "                 |\n"
        "      Risk/Policy + Classifier (Rules/LLM)\n"
        "                 |\n"
        "           Audit + Remediation\n"
        "                 |\n"
        "        JSON artifacts + summary.csv",
        language="text",
    )


def _is_nonzero(x: float, eps: float = 1e-12) -> bool:
    try:
        return abs(float(x)) > eps
    except Exception:
        return False


def _fmt_amt(x: float, dp: int = 2) -> str:
    try:
        return f"{float(x):,.{dp}f}"
    except Exception:
        return str(x)


def _fmt_fx(x: float, dp: int = 6) -> str:
    try:
        x = float(x)
        if abs(x) < 1e-12:
            x = 0.0
        return f"{x:.{dp}f}"
    except Exception:
        return str(x)


def _plural(n: int, s: str) -> str:
    n = int(n)
    return f"{n} {s}" if n == 1 else f"{n} {s}s"


def evidence_accounts(per_account: Iterable[Dict[str, Any]]) -> List[str]:
    """
    Evidence accounts = accounts with any non-zero delta in shares, QC, or SC.
    """
    out: List[str] = []
    for r in per_account or []:
        if (
            _is_nonzero(r.get("share_delta", 0.0))
            or _is_nonzero(r.get("net_qc_delta", 0.0))
            or _is_nonzero(r.get("net_sc_delta", 0.0))
        ):
            acct = str(r.get("bank_account") or "")
            if acct:
                out.append(acct)
    return out


def render_findings(payload: Dict[str, Any]) -> None:
    """
    Structured bullet list of the main diffs, using payload['diff'].
    """
    diff = payload.get("diff") or {}
    ev = payload

    # Header line with key context
    header_bits = []
    eid = ev.get("event_id", "")
    isin = ev.get("isin", "")
    q = ev.get("quotation_ccy") or ev.get("q_ccy") or ""
    s = ev.get("settlement_ccy") or ev.get("s_ccy") or ""
    if eid:
        header_bits.append(f"**Event:** {eid}")
    if isin:
        header_bits.append(f"**ISIN:** {isin}")
    header_bits.append(f"**CCY:** {q}->{s}")
    st.markdown(" &nbsp; | &nbsp; ".join(header_bits))

    # Findings bullets
    st.markdown("**Findings**")
    bullets: List[str] = []

    # Amounts
    aq = diff.get("amount_delta_qc", 0.0)
    as_ = diff.get("amount_delta_sc", 0.0)
    if _is_nonzero(aq) or _is_nonzero(as_):
        if _is_nonzero(aq):
            bullets.append(f"- Amount delta (QC): `{_fmt_amt(aq)}`")
        else:
            bullets.append("- No amount delta in quotation currency")
        if _is_nonzero(as_):
            bullets.append(f"- Amount delta (SC): `{_fmt_amt(as_)}`")
        else:
            bullets.append("- No amount delta in settlement currency")
    else:
        bullets.append("- No amount deltas detected")

    # Shares (loan-adjusted)
    shares_adj = diff.get("share_diff_after_loan", 0.0)
    loan_total = diff.get("loan_total", 0.0)
    if _is_nonzero(shares_adj):
        bullets.append(f"- Share delta (loan-adjusted): `{int(round(float(shares_adj)))}`; Loan total: `{int(round(float(loan_total)))}`")
    else:
        bullets.append(f"- No share delta after lending adjustment; Loan total: `{int(round(float(loan_total)))}`")

    # FX
    fx = diff.get("fx_delta", 0.0)
    if _is_nonzero(fx):
        bullets.append(f"- Implied FX delta: `{_fmt_fx(fx)}`")
    else:
        bullets.append("- No implied FX difference")

    # WHT
    wht = diff.get("wht_rate_delta", 0.0)
    if _is_nonzero(wht):
        bullets.append(f"- Withholding tax rate delta: `{wht:.2f} pp`")
    else:
        bullets.append("- No withholding tax rate difference")

    # Pay-date offset
    pay = int(diff.get("date_offset_pay_abs_days", 0) or 0)
    if pay != 0:
        bullets.append(f"- Payment date offset: `{_plural(pay, 'day')}`")

    st.markdown("\n".join(bullets))

    # Evidence accounts (explicit meaning)
    per_acct = payload.get("per_account") or []
    ev_accts = evidence_accounts(per_acct)
    st.markdown("**Evidence accounts** (accounts with non-zero deltas): " + ("`" + "`, `".join(ev_accts) + "`" if ev_accts else "—"))

    # Classifier causes (if present)
    cls = payload.get("classification") or {}
    causes = cls.get("hypothesized_causes") or []
    if causes:
        st.markdown("**Causes**")
        for c in causes:
            st.write(f"- {c}")


# --------------------------------- App ----------------------------------------

def main():
    args = parse_args()
    st.set_page_config(page_title="NBIM Reconciliation Dashboard", layout="wide")

    st.title("NBIM Dividend Reconciliation — Dashboard")
    st.caption("Read-only view over generated artifacts (no changes to the core pipeline).")

    with st.sidebar:
        st.header("Inputs")
        artifacts_dir_str = st.text_input("Artifacts directory", value=args.artifacts)
        artifacts_dir = Path(artifacts_dir_str)

        default_summary = Path(args.summary) if args.summary else artifacts_dir / "summary.csv"
        summary_path_str = st.text_input("Summary CSV path", value=str(default_summary))
        summary_path = Path(summary_path_str)

        st.divider()
        st.caption("Run the pipeline first to (re)generate artifacts.\n"
                   "Example: `python scripts/run_local.py --out artifacts --summary-csv summary.csv`")

    df = load_summary(summary_path)
    event_files = find_event_jsons(artifacts_dir)

    if df.empty and not event_files:
        st.warning("No artifacts found.")
        render_dataflow()
        return

    st.subheader("Overview")
    col1, col2, col3, col4 = st.columns(4)
    total_events = (len(df) if not df.empty else len(event_files))
    reviewed = int(df["require_review"].sum()) if not df.empty and "require_review" in df else 0
    auto_closed = int(df["auto_close"].sum()) if not df.empty and "auto_close" in df else 0
    with col1:
        st.metric("Events", f"{total_events}")
    with col2:
        st.metric("Require Review", f"{reviewed}")
    with col3:
        st.metric("Auto-Closable", f"{auto_closed}")
    with col4:
        if not df.empty and "risk_score" in df and len(df) > 0:
            st.metric("Avg Risk", f"{df['risk_score'].mean():.2f}")
        else:
            st.metric("Avg Risk", "—")

    st.divider()

    st.subheader("Summary")
    if not df.empty:
        filter_cols = st.columns(4)
        severity_filter = filter_cols[0].multiselect(
            "Severity", sorted(df["severity"].astype(str).unique().tolist()), default=None
        )
        review_filter = filter_cols[1].selectbox("Require Review", ["Any", "True", "False"], index=0)
        auto_close_filter = filter_cols[2].selectbox("Auto Close", ["Any", "True", "False"], index=0)
        sort_by = filter_cols[3].selectbox("Sort by", ["event_id", "risk_score", "pay_date_offset_days"], index=1)

        filtered = df.copy()
        if severity_filter:
            filtered = filtered[filtered["severity"].astype(str).isin(severity_filter)]
        if review_filter != "Any":
            filtered = filtered[filtered["require_review"] == (review_filter == "True")]
        if auto_close_filter != "Any":
            filtered = filtered[filtered["auto_close"] == (auto_close_filter == "True")]

        filtered = filtered.sort_values(by=sort_by, ascending=(sort_by == "event_id"))
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        st.download_button(
            "Download summary.csv",
            data=summary_path.read_bytes() if summary_path.exists() else b"",
            file_name="summary.csv",
            mime="text/csv",
        )
    else:
        st.info("summary.csv not found or empty.")

    st.divider()

    st.subheader("Event details")
    left, right = st.columns([0.5, 0.5])

    with left:
        if event_files:
            event_ids = [p.stem for p in event_files]
            selected_id = st.selectbox("Select event", options=event_ids)
            selected_path = artifacts_dir / f"{selected_id}.json"
            payload = load_event_payload(selected_path)
        else:
            st.info("No per-event JSON files found.")
            payload = {}

        if payload:
            # KPIs
            top_cols = st.columns(3)
            top_cols[0].metric("Event ID", str(payload.get("event_id", "")))
            risk = payload.get("risk", {})
            top_cols[1].metric("Risk Score", f"{risk.get('risk_score', 0)}")
            top_cols[2].metric("Require Review", str(risk.get("require_review", False)))

            cls = payload.get("classification", {})
            st.markdown(
                f"**Break types:** {', '.join(cls.get('break_types', [])) or '—'}  "
                f"| **Severity:** {cls.get('severity', '—')}  "
                f"| **Confidence:** {cls.get('confidence', '—')}"
            )

            # Structured findings (bulleted)
            render_findings(payload)

            # Raw audit in expander (optional view)
            with st.expander("Show compact audit paragraph"):
                st.write(payload.get("audit_text", ""))

    with right:
        if payload:
            per_acct = payload.get("per_account") or []
            ev_accts = evidence_accounts(per_acct)

            st.markdown("**Per-account attribution**")
            # Evidence toggle: show only evidence accounts by default
            show_all = st.checkbox("Show ALL accounts (uncheck to show only evidence accounts)", value=False)
            table_rows = per_acct
            if not show_all and ev_accts:
                table_rows = [r for r in per_acct if str(r.get("bank_account") or "") in ev_accts]

            if table_rows:
                per_df = pd.DataFrame(table_rows)
                # Column order if present
                preferred = [
                    "bank_account",
                    "nbim_shares", "custody_shares", "share_delta",
                    "nbim_net_qc", "custody_net_qc", "net_qc_delta",
                    "nbim_net_sc", "custody_net_sc", "net_sc_delta",
                ]
                cols = [c for c in preferred if c in per_df.columns] + [c for c in per_df.columns if c not in preferred]
                per_df = per_df[cols]
                st.dataframe(per_df, use_container_width=True, hide_index=True)
            else:
                st.info("No per-account deltas.")

            st.divider()
            render_dataflow()


if __name__ == "__main__":
    main()
