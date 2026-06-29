"""
Lazy model registry for the serving layer.

Loads the two-stage bundle (ALS + LightGBM + popularity + feature tables)
from ``SHOPSIGNAL_MODEL_DIR`` when present.  If the directory is missing or
incomplete the registry stays empty and the API falls back to deterministic
mock recommendations — so unit tests and a freshly cloned repo run without
any trained artifacts or the full dataset.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_REQUIRED = ("als_model.joblib", "lgbm_ranker.joblib", "popularity.joblib", "features.joblib")


class ModelRegistry:
    """Holds a single loaded TwoStageRecommender (or nothing)."""

    def __init__(self) -> None:
        self.model = None
        self.model_dir: str | None = None
        self.meta: dict = {}

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load_from_env(self) -> None:
        model_dir = os.getenv("SHOPSIGNAL_MODEL_DIR")
        if not model_dir:
            logger.info("SHOPSIGNAL_MODEL_DIR unset — serving mock recommendations.")
            return
        d = Path(model_dir)
        if not all((d / f).exists() for f in _REQUIRED):
            logger.warning("Model bundle incomplete in %s — serving mock.", model_dir)
            return
        try:
            # Import the heavy ML stack lazily so the API boots fast (and the
            # Docker health check passes) when no model bundle is configured.
            from src.models.two_stage import TwoStageRecommender

            self.model = TwoStageRecommender.load(d)
            self.model_dir = str(d)
            schema = d / "feature_schema.json"
            self.meta = json.loads(schema.read_text()) if schema.exists() else {}
            logger.info("Two-stage model loaded from %s", model_dir)
        except Exception:  # noqa: BLE001 — degrade to mock, never crash boot
            logger.exception("Failed to load model bundle; serving mock.")
            self.model = None


registry = ModelRegistry()
registry.load_from_env()
