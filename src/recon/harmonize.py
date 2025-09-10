from .schemas import NBIMLeg, CustodyLeg, CanonicalEvent
from typing import List
import pandas as pd

def to_canonical(nbim_df: pd.DataFrame, custody_df: pd.DataFrame) -> List[CanonicalEvent]:
    nbim_df = nbim_df.copy()
    custody_df = custody_df.copy()
    nbim_df["COAC_EVENT_KEY"] = nbim_df["COAC_EVENT_KEY"].astype(str)
    custody_df["COAC_EVENT_KEY"] = custody_df["COAC_EVENT_KEY"].astype(str)
    events = []
    for event_id, nbim_rows in nbim_df.groupby("COAC_EVENT_KEY"):
        nb = nbim_rows.iloc[0]
        nbim_leg = NBIMLeg(
            shares=float(nb["NOMINAL_BASIS"]),
            div_per_share=float(nb["DIVIDENDS_PER_SHARE"]),
            gross_qc=float(nb["GROSS_AMOUNT_QUOTATION"]),
            net_qc=float(nb["NET_AMOUNT_QUOTATION"]),
            net_sc=float(nb["NET_AMOUNT_SETTLEMENT"]),
            wht_rate=float(nb["WTHTAX_RATE"]),
            fx_used=float(nb["AVG_FX_RATE_QUOTATION_TO_PORTFOLIO"]),
        )
        cust_rows = custody_df[custody_df["COAC_EVENT_KEY"].astype(str) == event_id]
        legs = []
        for _, cr in cust_rows.iterrows():
            legs.append(
                CustodyLeg(
                    bank_account=str(cr.get("BANK_ACCOUNTS") or cr.get("CUSTODY") or ""),
                    shares=float(cr.get("HOLDING_QUANTITY", cr.get("NOMINAL_BASIS", 0))),
                    gross_qc=float(cr["GROSS_AMOUNT"]),
                    net_qc=float(cr.get("NET_AMOUNT_QC", cr.get("NET_AMOUNT_SC", 0))),
                    tax_qc=float(cr.get("TAX", 0)),
                    net_sc=float(cr.get("NET_AMOUNT_SC", cr.get("NET_AMOUNT_QC", 0))),
                    fx=float(cr.get("FX_RATE", 1)),
                    pay_date=str(cr.get("PAY_DATE", cr.get("EVENT_PAYMENT_DATE", ""))),
                )
            )
        ev = CanonicalEvent(
            event_id=event_id,
            isin=str(nb["ISIN"]),
            ex_date=str(nb["EXDATE"]),
            pay_date=str(nb["PAYMENT_DATE"]),
            quotation_ccy=str(nb["QUOTATION_CURRENCY"]),
            settlement_ccy=str(nb["SETTLEMENT_CURRENCY"]),
            nbim=nbim_leg,
            custody_legs=legs,
        )
        events.append(ev)
    return events
