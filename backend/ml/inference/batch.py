import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import settings
from ..datasets.loader import load_events
from ..preprocessing.features import build_user_features
from ..models.registry import get_registry

_registry = get_registry()


class BatchPredictor:
    """Batch inference — predict for all users and write results."""

    def __init__(self, model_name: str, output_dir: Optional[Path] = None):
        self.model = _registry.load(model_name)
        self.model_name = model_name
        self.output_dir = output_dir or settings.datasets_dir / "predictions"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, project_id: int, days: Optional[int] = None) -> Path:
        days = days or settings.lookback_days
        events = load_events(project_id, days=days)
        features = build_user_features(events)
        if features.empty:
            raise ValueError("No features generated")

        X = features.drop(columns=["user_id"], errors="ignore")
        probas = self.model.predict_proba(X)[:, 1]

        results = features[["user_id"]].copy()
        results["probability"] = probas
        results["prediction"] = (probas >= 0.5).astype(int)
        results["model"] = self.model_name
        results["run_at"] = datetime.utcnow().isoformat()

        filename = f"{self.model_name}_preds_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.parquet"
        path = self.output_dir / filename
        results.to_parquet(path, index=False)
        return path
