import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    mean_absolute_error, mean_squared_error, r2_score,
)
from typing import Optional


def classification_report(y_true, y_pred, y_proba: Optional[np.ndarray] = None) -> dict:
    metrics = {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
    }
    if y_proba is not None:
        metrics["roc_auc"] = round(roc_auc_score(y_true, y_proba), 4)
        metrics["avg_precision"] = round(average_precision_score(y_true, y_proba), 4)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    metrics["specificity"] = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0
    return metrics


def regression_report(y_true, y_pred) -> dict:
    return {
        "mae": round(mean_absolute_error(y_true, y_pred), 4),
        "mse": round(mean_squared_error(y_true, y_pred), 4),
        "rmse": round(np.sqrt(mean_squared_error(y_true, y_pred)), 4),
        "r2": round(r2_score(y_true, y_pred), 4),
    }


def feature_importance(model, feature_names: list[str], top_n: int = 10) -> list[dict]:
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_).flatten()
    else:
        return []
    indices = np.argsort(importances)[::-1][:top_n]
    return [
        {"feature": feature_names[i], "importance": round(importances[i], 4)}
        for i in indices
    ]


def error_analysis(y_true, y_pred, ids: Optional[pd.Series] = None) -> pd.DataFrame:
    df = pd.DataFrame({"true": y_true, "pred": y_pred})
    if ids is not None:
        df["id"] = ids.values
    df["correct"] = df["true"] == df["pred"]
    df["error_type"] = "correct"
    df.loc[(df["true"] == 1) & (df["pred"] == 0), "error_type"] = "false_negative"
    df.loc[(df["true"] == 0) & (df["pred"] == 1), "error_type"] = "false_positive"
    return df
