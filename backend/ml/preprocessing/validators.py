import pandas as pd
import numpy as np
from typing import Optional


def validate_schema(df: pd.DataFrame, expected_columns: list[str]) -> list[str]:
    errors = []
    for col in expected_columns:
        if col not in df.columns:
            errors.append(f"Missing column: {col}")
    if df.empty:
        errors.append("DataFrame is empty")
    null_counts = df.isnull().sum()
    for col, cnt in null_counts.items():
        if cnt > 0:
            errors.append(f"Column '{col}' has {cnt} null values")
    return errors


def detect_anomalies(
    df: pd.DataFrame,
    numeric_cols: Optional[list[str]] = None,
    z_threshold: float = 3.0,
) -> pd.DataFrame:
    """Return rows flagged as outliers based on z-score."""
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    flags = pd.Series(False, index=df.index)
    for col in numeric_cols:
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            z_scores = (df[col] - mean).abs() / std
            flags = flags | (z_scores > z_threshold)
    return df[flags].copy()


def compute_statistics(df: pd.DataFrame) -> dict:
    stats = {
        "rows": len(df),
        "columns": len(df.columns),
        "nulls": df.isnull().sum().to_dict(),
        "dtypes": df.dtypes.astype(str).to_dict(),
    }
    numeric = df.select_dtypes(include=[np.number])
    if not numeric.empty:
        stats["numeric"] = {
            "mean": numeric.mean().to_dict(),
            "std": numeric.std().to_dict(),
            "min": numeric.min().to_dict(),
            "max": numeric.max().to_dict(),
        }
    return stats
