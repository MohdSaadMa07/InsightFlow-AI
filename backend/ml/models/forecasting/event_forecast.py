import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline

from ...preprocessing.transformers import ColumnSelector, FeatureScaler


FORECAST_FEATURES = ["day_of_week", "day_of_month", "month", "is_weekend"]


def build_forecast_pipeline() -> Pipeline:
    return Pipeline([
        ("select", ColumnSelector(FORECAST_FEATURES)),
        ("scale", FeatureScaler(FORECAST_FEATURES)),
        ("model", LinearRegression()),
    ])


def forecast_events(model, df: pd.DataFrame, days_ahead: int = 7) -> list[dict]:
    from ...preprocessing.features import build_time_features
    last_date = df["date"].max()
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=days_ahead,
        freq="D",
    )
    future_df = pd.DataFrame({"date": future_dates})
    future_df = build_time_features(future_df)
    X = future_df[FORECAST_FEATURES]
    preds = model.predict(X)
    return [
        {"date": str(d.date()), "predicted_events": max(0, round(p))}
        for d, p in zip(future_dates, preds)
    ]
