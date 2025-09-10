"""
Main orchestration module for the reconciliation pipeline.

This module coordinates the entire reconciliation process, from data ingestion
through difference computation, providing the main entry point for the system.
"""

from .ingest import load_csvs
from .harmonize import to_canonical
from .match import group_events
from .diff import compute_diff


def run(nbim_path: str, custody_path: str):
    """
    Execute the complete reconciliation pipeline.
    
    This function orchestrates the entire reconciliation process:
    1. Load NBIM and Custody CSV files
    2. Transform data into canonical format
    3. Group and match events
    4. Compute differences for each event
    
    Args:
        nbim_path: Path to the NBIM dividend bookings CSV file
        custody_path: Path to the Custody dividend bookings CSV file
        
    Returns:
        Tuple of (events, diffs) where:
        - events: List of CanonicalEvent objects
        - diffs: List of DiffRecord objects corresponding to each event
    """
    nbim_df, custody_df = load_csvs(nbim_path, custody_path)
    events = to_canonical(nbim_df, custody_df)
    grouped = group_events(events)
    diffs = [compute_diff(ev) for ev in grouped]
    return grouped, diffs
