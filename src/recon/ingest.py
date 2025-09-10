import pandas as pd

def load_csvs(nbim_path: str, custody_path: str):
    nbim = pd.read_csv(nbim_path)
    custody = pd.read_csv(custody_path)
    return nbim, custody
