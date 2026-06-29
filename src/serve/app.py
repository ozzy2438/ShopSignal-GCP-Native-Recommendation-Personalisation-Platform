"""
ShopSignal — FastAPI serving layer.

Endpoints
---------
GET  /health           → liveness probe (Cloud Run / Kubernetes)
GET  /version          → application + model metadata
POST /recommend        → two-stage recommendation (ALS→LGBM), mock fallback
POST /recommend/batch  → batch recommendations for a list of customers

The real two-stage model loads from SHOPSIGNAL_MODEL_DIR when present; without
it the API serves deterministic mock data so it runs without the full dataset.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException

from src.serve.model_registry import registry
from src.serve.schemas import (
    BatchRecommendRequest,
    BatchRecommendResponse,
    RecommendedItem,
    RecommendRequest,
    RecommendResponse,
)

# ── Application version ───────────────────────────────────────────────────────
# Injected at build time via Docker ARG / environment variable.
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "development")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ShopSignal Recommendation API",
    description=(
        "GCP-native two-stage recommendation platform. "
        "Stage 1: ALS collaborative filtering (candidate gen). "
        "Stage 2: LightGBM LambdaMART ranker."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Health probe ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """
    Liveness probe used by Cloud Run and the Docker HEALTHCHECK instruction.
    Returns 200 OK when the service is ready to accept traffic.
    """
    return {"status": "ok", "env": APP_ENV}


# ── Version ───────────────────────────────────────────────────────────────────
@app.get("/version", tags=["ops"])
async def version() -> dict[str, Any]:
    """
    Returns the running application version and environment.
    The version is set from the APP_VERSION environment variable,
    which CI/CD injects from the Git commit SHA at build time.
    """
    return {
        "version": APP_VERSION,
        "env": APP_ENV,
        "model_stage": "als+lgbm" if registry.loaded else "placeholder",
        "model_loaded": registry.loaded,
        "model_dir": registry.model_dir,
        "feature_cols": registry.meta.get("feature_cols", []),
    }


def _to_items(article_ids: list[str]) -> list[RecommendedItem]:
    """Wrap ordered article IDs as scored items (descending, rank-based)."""
    n = len(article_ids)
    return [
        RecommendedItem(article_id=a, score=round(1.0 - i / max(n, 1), 4))
        for i, a in enumerate(article_ids)
    ]


def _mock_items(top_n: int) -> list[RecommendedItem]:
    return [
        RecommendedItem(article_id=f"0{i}928134{i:02d}", score=round(1.0 - i * 0.08, 3))
        for i in range(min(top_n, 10))
    ]


def _recommend_for(customer_id: str, top_n: int) -> tuple[list[RecommendedItem], str]:
    """Return (items, source) using the real model when loaded, else mock."""
    if not registry.loaded:
        return _mock_items(top_n), "mock"
    article_ids = registry.model.recommend(customer_id, k=top_n)
    source = "als+lgbm" if registry.model.is_known_user(customer_id) else "popularity"
    return _to_items(article_ids), source


# ── Recommend (placeholder) ───────────────────────────────────────────────────
@app.post("/recommend", response_model=RecommendResponse, tags=["recommend"])
async def recommend(request: RecommendRequest) -> RecommendResponse:
    """
    Return top-N product recommendations for a given customer.

    Two-stage flow when a model bundle is loaded: ALS top-200 candidates →
    LightGBM re-rank → top-N.  Cold-start users fall back to popularity.
    Without a bundle (default in CI / fresh clone) deterministic mock data is
    returned so the contract stays testable without the full dataset.
    """
    if not request.customer_id:
        raise HTTPException(status_code=422, detail="customer_id must not be empty")

    items, source = _recommend_for(request.customer_id, request.top_n)
    return RecommendResponse(
        customer_id=request.customer_id,
        recommendations=items,
        model_version=APP_VERSION,
        source=source,
    )


# ── Recommend (batch) ─────────────────────────────────────────────────────────
@app.post("/recommend/batch", response_model=BatchRecommendResponse, tags=["recommend"])
async def recommend_batch(request: BatchRecommendRequest) -> BatchRecommendResponse:
    """Return top-N recommendations for a list of customers in one call."""
    results: list[RecommendResponse] = []
    for cid in request.customer_ids:
        if not cid:
            raise HTTPException(status_code=422, detail="customer_id must not be empty")
        items, src = _recommend_for(cid, request.top_n)
        results.append(
            RecommendResponse(
                customer_id=cid, recommendations=items, model_version=APP_VERSION, source=src
            )
        )
    overall = "als+lgbm" if registry.loaded else "mock"
    return BatchRecommendResponse(results=results, model_version=APP_VERSION, source=overall)
