from .ingest import load_csvs
from .harmonize import to_canonical
from .match import group_events
from .diff import compute_diff

def run(nbim_path: str, custody_path: str):
    nbim_df, custody_df = load_csvs(nbim_path, custody_path)
    events = to_canonical(nbim_df, custody_df)
    grouped = group_events(events)
    diffs = [compute_diff(ev) for ev in grouped]
    return grouped, diffs
