"""
Data schemas for canonical dividend reconciliation.
"""

from pydantic import BaseModel
from typing import List, Optional


class NBIMLeg(BaseModel):
    """
    Represents NBIM's internal view of a dividend event.
    """
    shares: float
    div_per_share: float
    gross_qc: float
    net_qc: float
    net_sc: float
    wht_rate: float
    fx_used: float


class CustodyLeg(BaseModel):
    """
    Represents a single custodian-reported leg of a dividend event.
    """
    bank_account: Optional[str]
    shares: float
    loan_quantity: float
    gross_qc: float
    net_qc: float
    tax_qc: float
    net_sc: float
    fx: float
    pay_date: Optional[str]


class CanonicalEvent(BaseModel):
    """
    Unified view of a dividend event, containing NBIM leg and custody legs.
    """
    event_id: str
    isin: str
    ex_date: str
    pay_date: str
    quotation_ccy: str
    settlement_ccy: str
    nbim: NBIMLeg
    custody_legs: List[CustodyLeg]


class DiffRecord(BaseModel):
    """
    Deterministic reconciliation results for a single event.
    """
    event_id: str
    amount_delta_qc: float
    amount_delta_sc: float
    wht_rate_delta: float
    fx_delta: float
    date_offset_pay_abs_days: int
    share_diff: float
    loan_total: float
    share_diff_after_loan: float
