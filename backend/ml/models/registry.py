import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import os
_MODELS_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models', 'artifacts'))


class ModelRegistry:
    """Lightweight model registry — save, load, version, and list models."""

    def __init__(self, registry_dir: Optional[Path] = None):
        self.registry_dir = registry_dir or _MODELS_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.registry_dir / "index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            return json.loads(self._index_path.read_text())
        return {"models": []}

    def _save_index(self):
        self._index_path.write_text(json.dumps(self._index, indent=2))

    def save(self, model: Any, name: str, metrics: Optional[dict] = None) -> str:
        version = f"{name}_v{len([m for m in self._index['models'] if m['name'] == name]) + 1}"
        model_path = self.registry_dir / f"{version}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        entry = {
            "name": name,
            "version": version,
            "path": str(model_path),
            "created_at": datetime.utcnow().isoformat(),
            "metrics": metrics or {},
        }
        self._index["models"].append(entry)
        self._save_index()
        return version

    def load(self, name: str, version: Optional[str] = None) -> Any:
        models = [m for m in self._index["models"] if m["name"] == name]
        if not models:
            raise FileNotFoundError(f"No model found: {name}")
        if version:
            models = [m for m in models if m["version"] == version]
        entry = models[-1]
        with open(entry["path"], "rb") as f:
            return pickle.load(f)

    def list(self, name: Optional[str] = None) -> list[dict]:
        if name:
            return [m for m in self._index["models"] if m["name"] == name]
        return self._index["models"]

    def delete(self, name: str, version: Optional[str] = None) -> int:
        to_keep = []
        deleted = 0
        for m in self._index["models"]:
            if m["name"] == name and (version is None or m["version"] == version):
                Path(m["path"]).unlink(missing_ok=True)
                deleted += 1
            else:
                to_keep.append(m)
        self._index["models"] = to_keep
        self._save_index()
        return deleted

    def get_best(self, name: str, metric: str = "accuracy") -> Optional[dict]:
        models = [m for m in self._index["models"] if m["name"] == name and m.get("metrics", {}).get(metric) is not None]
        if not models:
            return None
        return max(models, key=lambda m: m["metrics"][metric])


_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
