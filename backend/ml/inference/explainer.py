import pandas as pd
import numpy as np
from typing import Optional


def explain_prediction(
    model,
    row: pd.Series,
    feature_names: list[str],
    n_top: int = 5,
) -> list[dict]:
    """Simple feature attribution via permutation."""
    X = row.values.reshape(1, -1)
    base_pred = model.predict_proba(X)[0, 1]

    contributions = []
    for i, name in enumerate(feature_names):
        X_perm = X.copy()
        X_perm[0, i] = 0
        perm_pred = model.predict_proba(X_perm)[0, 1]
        contributions.append({
            "feature": name,
            "value": float(row.iloc[i]),
            "impact": round(base_pred - perm_pred, 4),
        })

    contributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
    return contributions[:n_top]


def summary_plot_data(
    model,
    X: pd.DataFrame,
    feature_names: list[str],
    n_samples: int = 100,
) -> dict:
    if len(X) > n_samples:
        X = X.sample(n_samples, random_state=42)
    shap_values = []
    for _, row in X.iterrows():
        expl = explain_prediction(model, row, feature_names, n_top=len(feature_names))
        shap_values.append([e["impact"] for e in expl])
    return {
        "feature_names": feature_names,
        "shap_values": np.array(shap_values).tolist(),
        "feature_values": X.values.tolist(),
    }
