import pandas as pd

def _read_any_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")

def load_csvs(nbim_path: str, custody_path: str):
    nbim = _read_any_csv(nbim_path)
    custody = _read_any_csv(custody_path)
    return nbim, custody
