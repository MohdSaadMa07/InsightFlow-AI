import pandas as pd
from typing import Optional

from ..models.registry import get_registry
from ..config import settings
from ..datasets.loader import load_events
from ..preprocessing.features import build_user_features

_registry = get_registry()


class Predictor:
    """Online predictor — returns per-user predictions."""

    def __init__(self, model_name: str, model_version: Optional[str] = None):
        self.model = _registry.load(model_name, model_version)
        self.model_name = model_name

    def predict_user(self, user_id: str, project_id: int) -> dict:
        events = load_events(project_id, days=settings.lookback_days, as_df=True)
        user_events = events[events["user_id"] == user_id]
        if user_events.empty:
            return {"user_id": user_id, "prediction": None, "error": "No events found"}

        features = build_user_features(user_events)
        if features.empty:
            return {"user_id": user_id, "prediction": None, "error": "No features"}

        X = features.drop(columns=["user_id"], errors="ignore")
        proba = self.model.predict_proba(X)[0, 1]
        pred = int(self.model.predict(X)[0])

        return {
            "user_id": user_id,
            "prediction": pred,
            "probability": round(float(proba), 4),
            "model": self.model_name,
        }

    def predict_batch(self, features: pd.DataFrame) -> list[dict]:
        X = features.drop(columns=["user_id"], errors="ignore")
        probas = self.model.predict_proba(X)[:, 1]
        preds = self.model.predict(X)
        return [
            {
                "user_id": row.get("user_id", i),
                "prediction": int(p),
                "probability": round(float(pr), 4),
            }
            for i, (p, pr, (_, row)) in enumerate(zip(preds, probas, features.iterrows()))
        ]
