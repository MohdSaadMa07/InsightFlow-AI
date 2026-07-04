import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import settings


class DatasetVersion:
    def __init__(
        self,
        name: str,
        rows: int,
        columns: list[str],
        hash: str,
        created_at: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.name = name
        self.rows = rows
        self.columns = columns
        self.hash = hash
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "rows": self.rows,
            "columns": self.columns,
            "hash": self.hash,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DatasetVersion":
        return cls(**d)


def compute_hash(df) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df).values.tobytes())
    return h.hexdigest()[:12]


def save_dataset_version(df, name: str, metadata: Optional[dict] = None) -> DatasetVersion:
    version = DatasetVersion(
        name=name,
        rows=len(df),
        columns=list(df.columns),
        hash=compute_hash(df),
        metadata=metadata,
    )
    manifest_path = settings.datasets_dir / "manifest.json"
    manifest = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    manifest.append(version.to_dict())
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return version


def get_dataset_version(name: str) -> Optional[DatasetVersion]:
    manifest_path = settings.datasets_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text())
    for v in manifest:
        if v["name"] == name:
            return DatasetVersion.from_dict(v)
    return None
