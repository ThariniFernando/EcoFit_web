from typing import List, Dict, Tuple
import numpy as np
import pandas as pd


def select_feature_cols(
    df: pd.DataFrame,
    time_col: str,
    ward_col: str,
    label_col: str,
    leakage_cols: List[str],
) -> List[str]:
    """
    Select numeric feature columns, excluding:
    - id/time/label columns
    - leakage columns (future aggregates)
    - any column containing 'future'
    """
    ignore = set([time_col, ward_col, label_col, *leakage_cols])

    cols = []
    for c in df.columns:
        if c in ignore:
            continue
        if c.startswith("f_"):
            continue
        if "future" in c.lower():
            continue
        if df[c].dtype.kind in "biufc":
            cols.append(c)

    if not cols:
        raise ValueError("No numeric feature columns found after filtering.")
    return cols


def fit_scaler(train_df: pd.DataFrame, feature_cols: List[str]) -> Dict[str, List[float]]:
    X = train_df[feature_cols].to_numpy(dtype=np.float32)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-6] = 1.0
    return {"mean": mean.tolist(), "std": std.tolist()}


def apply_scaler(X: np.ndarray, scaler: Dict[str, List[float]]) -> np.ndarray:
    mean = np.array(scaler["mean"], dtype=np.float32)
    std = np.array(scaler["std"], dtype=np.float32)
    return (X - mean) / std


def build_windows(
    df: pd.DataFrame,
    feature_cols: List[str],
    label_col: str,
    ward_col: str,

    time_col: str,
    history_len: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sliding windows per ward.
    X: [N, T, F]
    y: [N]
    """
    df = df.sort_values([ward_col, time_col]).reset_index(drop=True)

    X_list = []
    y_list = []

    for _, g in df.groupby(ward_col):
        g = g.sort_values(time_col)
        if len(g) < history_len:
            continue

        feats = g[feature_cols].to_numpy(dtype=np.float32)
        labels = g[label_col].to_numpy()

        for end in range(history_len - 1, len(g)):
            start = end - (history_len - 1)
            X_list.append(feats[start:end + 1])
            y_list.append(int(labels[end]))

    X = np.stack(X_list, axis=0) if X_list else np.empty((0, history_len, len(feature_cols)), dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    return X, y


def time_split_with_overlap(
    df: pd.DataFrame,
    time_col: str,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    history_len: int = 168,
):
    """
    Time split (global) + overlap so val/test still have enough history to form 168h windows.
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col])

    times = np.array(sorted(df[time_col].unique()))
    n = len(times)
    t_train_end = times[int(train_ratio * n)]
    t_val_end = times[int((train_ratio + val_ratio) * n)]

    overlap_hours = history_len

    train_df = df[df[time_col] <= t_train_end].copy()

    val_start = t_train_end - pd.Timedelta(hours=overlap_hours)
    val_df = df[(df[time_col] > val_start) & (df[time_col] <= t_val_end)].copy()

    test_start = t_val_end - pd.Timedelta(hours=overlap_hours)
    test_df = df[df[time_col] > test_start].copy()

    return train_df, val_df, test_df