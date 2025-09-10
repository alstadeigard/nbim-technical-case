"""
Per-account attribution of reconciliation differences.
"""

from typing import List, Dict, Tuple
from .schemas import CanonicalEvent


def per_account_attribution(event: CanonicalEvent) -> List[Dict[str, object]]:
    """
    Produce per-account deltas by aligning NBIM and Custody legs on bank_account.

    Returns:
        A list of dicts with keys:
        - bank_account
        - nbim_shares, custody_shares, share_delta
        - nbim_net_qc, custody_net_qc, net_qc_delta
        - nbim_net_sc, custody_net_sc, net_sc_delta
    """
    nbim_map: Dict[str, Tuple[float, float, float]] = {}
    for acc in event.nbim_accounts:
        key = (acc.bank_account or "").strip()
        nbim_map[key] = (
            acc.shares,
            acc.net_qc,
            acc.net_sc,
        )

    custody_map: Dict[str, Tuple[float, float, float]] = {}
    for leg in event.custody_legs:
        key = (leg.bank_account or "").strip()
        if key not in custody_map:
            custody_map[key] = (0.0, 0.0, 0.0)
        # accumulate per account (in case of multiple legs per account)
        sh, qc, sc = custody_map[key]
        custody_map[key] = (sh + leg.shares, qc + leg.net_qc, sc + leg.net_sc)

    accounts = sorted(set(list(nbim_map.keys()) + list(custody_map.keys())))
    rows: List[Dict[str, object]] = []
    for acct in accounts:
        nb_sh, nb_qc, nb_sc = nbim_map.get(acct, (0.0, 0.0, 0.0))
        cu_sh, cu_qc, cu_sc = custody_map.get(acct, (0.0, 0.0, 0.0))
        rows.append(
            {
                "bank_account": acct,
                "nbim_shares": nb_sh,
                "custody_shares": cu_sh,
                "share_delta": cu_sh - nb_sh,
                "nbim_net_qc": nb_qc,
                "custody_net_qc": cu_qc,
                "net_qc_delta": cu_qc - nb_qc,
                "nbim_net_sc": nb_sc,
                "custody_net_sc": cu_sc,
                "net_sc_delta": cu_sc - nb_sc,
            }
        )
    return rows
