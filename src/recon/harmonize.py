from .schemas import NBIMLeg, CustodyLeg, CanonicalEvent
from typing import List
import pandas as pd

_NUMERIC_NBIM_FIELDS = [
    "NOMINAL_BASIS",
    "GROSS_AMOUNT_QUOTATION",
    "NET_AMOUNT_QUOTATION",
    "NET_AMOUNT_SETTLEMENT",
    "WTHTAX_RATE",
    "AVG_FX_RATE_QUOTATION_TO_PORTFOLIO",
    "DIVIDENDS_PER_SHARE",
]

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def to_canonical(nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[CanonicalEvent]:
    nbim_df = nbim_df.copy()
    custody_df = custody_df.copy()
    nbim_df["COAC_EVENT_KEY"] = nbim_df["COAC_EVENT_KEY"].astype(str)
    custody_df["COAC_EVENT_KEY"] = custody_df["COAC_EVENT_KEY"].astype(str)

    for col in _NUMERIC_NBIM_FIELDS:
        if col in nbim_df.columns:
            nbim_df[col] = nbim_df[col].apply(_safe_float)

    events: List[CanonicalEvent] = []
    for event_id, nbim_rows in nbim_df.groupby("COAC_EVENT_KEY"):
        # Aggregate NBIM rows for this event (handles multiple bank accounts)
        nbim_agg = {
            "shares": nbim_rows["NOMINAL_BASIS"].sum(),
            "div_per_share": nbim_rows["DIVIDENDS_PER_SHARE"].mean(),
            "gross_qc": nbim_rows["GROSS_AMOUNT_QUOTATION"].sum(),
            "net_qc": nbim_rows["NET_AMOUNT_QUOTATION"].sum(),
            "net_sc": nbim_rows["NET_AMOUNT_SETTLEMENT"].sum(),
            "wht_rate": nbim_rows["WTHTAX_RATE"].mean(),
            "fx_used": nbim_rows["AVG_FX_RATE_QUOTATION_TO_PORTFOLIO"].mean(),
        }
        nbim_any = nbim_rows.iloc[0]
        nbim_leg = NBIMLeg(**nbim_agg)

        # Collect all custody legs for this event
        cust_rows = custody_df[custody_df["COAC_EVENT_KEY"].astype(str) == event_id]
        legs: List[CustodyLeg] = []
        for _, cr in cust_rows.iterrows():
            legs.append(
                CustodyLeg(
                    bank_account=str(cr.get("BANK_ACCOUNTS") or cr.get("CUSTODY") or ""),
                    shares=_safe_float(cr.get("HOLDING_QUANTITY", cr.get("NOMINAL_BASIS", 0))),
                    gross_qc=_safe_float(cr.get("GROSS_AMOUNT", 0)),
                    net_qc=_safe_float(cr.get("NET_AMOUNT_QC", cr.get("NET_AMOUNT_SC", 0))),
                    tax_qc=_safe_float(cr.get("TAX", 0)),
                    net_sc=_safe_float(cr.get("NET_AMOUNT_SC", cr.get("NET_AMOUNT_QC", 0))),
                    fx=_safe_float(cr.get("FX_RATE", 1)),
                    pay_date=str(cr.get("PAY_DATE", cr.get("EVENT_PAYMENT_DATE", ""))),
                )
            )

        ev = CanonicalEvent(
            event_id=event_id,
            isin=str(nbim_any["ISIN"]),
            ex_date=str(nbim_any["EXDATE"]),
            pay_date=str(nbim_any["PAYMENT_DATE"]),
            quotation_ccy=str(nbim_any["QUOTATION_CURRENCY"]),
            settlement_ccy=str(nbim_any["SETTLEMENT_CURRENCY"]),
            nbim=nbim_leg,
            custody_legs=legs,
        )
        events.append(ev)
    return events
