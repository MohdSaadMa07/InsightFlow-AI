"""ML module settings.

Central configuration for the machine learning module.
Import as: from ml.config import settings
"""
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class MLSettings:
    # Data loading
    lookback_days: int = 90
    test_split_ratio: float = 0.2
    random_seed: int = 42

    # Dataset versioning
    datasets_dir: Path = Path(__file__).parent / "datasets" / "data"

    # Churn model defaults
    observation_days: int = 30
    gap_days: int = 7
    min_events_per_user: int = 1


settings = MLSettings()
