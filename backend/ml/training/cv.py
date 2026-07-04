import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from typing import Callable, Optional


def cross_validate(
    model_fn: Callable,
    X: pd.DataFrame,
    y: pd.Series,
    n_folds: int = 5,
    stratify: bool = True,
    groups: Optional[pd.Series] = None,
) -> dict:
    if stratify and y.nunique() == 2:
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    else:
        cv = TimeSeriesSplit(n_splits=n_folds)

    fold_metrics = []
    for fold, (train_idx, val_idx) in enumerate(cv.split(X, y, groups)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = model_fn()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)

        fold_metrics.append({
            "fold": fold + 1,
            "accuracy": accuracy_score(y_val, y_pred),
            "precision": precision_score(y_val, y_pred, zero_division=0),
            "recall": recall_score(y_val, y_pred, zero_division=0),
            "f1": f1_score(y_val, y_pred, zero_division=0),
            "train_size": len(X_train),
            "val_size": len(X_val),
        })

    summary = {}
    for metric in ["accuracy", "precision", "recall", "f1"]:
        values = [m[metric] for m in fold_metrics]
        summary[metric] = {
            "mean": round(np.mean(values), 4),
            "std": round(np.std(values), 4),
        }

    return {"folds": fold_metrics, "summary": summary}
