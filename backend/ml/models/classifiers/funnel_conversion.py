from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from ...preprocessing.transformers import ColumnSelector, FeatureEncoder, FeatureScaler


FUNNEL_FEATURES = [
    "total_events",
    "session_count",
    "days_active",
    "pageview_ratio",
    "hour",
    "day_of_week",
    "is_weekend",
    "is_business_hours",
]


def build_funnel_pipeline() -> Pipeline:
    return Pipeline([
        ("select", ColumnSelector(FUNNEL_FEATURES)),
        ("scale", FeatureScaler(FUNNEL_FEATURES)),
        ("classifier", RandomForestClassifier(
            n_estimators=150,
            max_depth=6,
            min_samples_leaf=10,
            random_state=42,
            class_weight="balanced",
        )),
    ])
