from pydantic import BaseModel
from typing import List, Optional

class NBIMLeg(BaseModel):
    shares: float
    div_per_share: float
    gross_qc: float
    net_qc: float
    net_sc: float
    wht_rate: float
    fx_used: float

class CustodyLeg(BaseModel):
    bank_account: Optional[str]
    shares: float
    gross_qc: float
    net_qc: float
    tax_qc: float
    net_sc: float
    fx: float
    pay_date: Optional[str]

class CanonicalEvent(BaseModel):
    event_id: str
    isin: str
    ex_date: str
    pay_date: str
    quotation_ccy: str
    settlement_ccy: str
    nbim: NBIMLeg
    custody_legs: List[CustodyLeg]

class DiffRecord(BaseModel):
    event_id: str
    amount_delta_qc: float
    amount_delta_sc: float
    wht_rate_delta: float
    fx_delta: float
    date_offset_pay_abs_days: int
    share_diff: float
