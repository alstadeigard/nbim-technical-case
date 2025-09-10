"""
CSV ingestion utilities for NBIM and Custody data.

This module provides robust CSV loading capabilities that handle various
formats, encodings, and separators commonly found in financial data files.
"""

import pandas as pd


def _read_any_csv(path: str) -> pd.DataFrame:
    """
    Read a CSV file with automatic separator detection and UTF-8 BOM handling.
    
    Args:
        path: Path to the CSV file
        
    Returns:
        DataFrame containing the CSV data
    """
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")


def load_csvs(nbim_path: str, custody_path: str):
    """
    Load NBIM and Custody CSV files into DataFrames.
    
    Args:
        nbim_path: Path to the NBIM dividend bookings CSV file
        custody_path: Path to the Custody dividend bookings CSV file
        
    Returns:
        Tuple of (nbim_df, custody_df) DataFrames
    """
    nbim = _read_any_csv(nbim_path)
    custody = _read_any_csv(custody_path)
    return nbim, custody
