import numpy as np
import pandas as pd


class HeuristicChurnModel:
    """Rule-based churn predictor using recency + frequency thresholds."""

    def __init__(self, inactivity_days: int = 14, min_events: int = 5):
        self.inactivity_days = inactivity_days
        self.min_events = min_events

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        preds = np.zeros(len(features), dtype=int)
        for i, row in features.iterrows():
            if (
                row.get("hours_since_last_event", 0) > self.inactivity_days * 24
                and row.get("total_events", 0) < self.min_events
            ):
                preds[i] = 1
        return preds

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        scores = np.zeros(len(features))
        for i, row in features.iterrows():
            hours = row.get("hours_since_last_event", 0)
            events = row.get("total_events", 1)
            score = (hours / (self.inactivity_days * 24)) * (1 / (events / self.min_events))
            scores[i] = min(score, 1.0)
        return np.column_stack((1 - scores, scores))


class HeuristicConversionModel:
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return (features.get("purchase_count", 0) > 0).astype(int).values
