from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline

from ...preprocessing.transformers import ColumnSelector, FeatureEncoder, FeatureScaler


CHURN_FEATURES = [
    "total_events",
    "unique_event_types",
    "days_active",
    "event_density",
    "session_count",
    "hours_since_last_event",
    "pageview_ratio",
    "purchase_count",
]


def build_churn_pipeline() -> Pipeline:
    return Pipeline([
        ("select", ColumnSelector(CHURN_FEATURES)),
        ("scale", FeatureScaler(CHURN_FEATURES)),
        ("classifier", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ])
