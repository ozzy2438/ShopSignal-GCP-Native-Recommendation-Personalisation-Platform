"""
ShopSignal — FastAPI serving layer.

Endpoints
---------
GET  /health     → liveness probe (Cloud Run / Kubernetes)
GET  /version    → application metadata
POST /recommend  → placeholder recommendation response (mock data)

NOTE: The real recommendation logic (ALS candidate gen + LightGBM ranker)
will be wired in during Phase 2 of the roadmap (feat/two-stage-model).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from src.serve.schemas import RecommendedItem, RecommendRequest, RecommendResponse

# ── Application version ───────────────────────────────────────────────────────
# Injected at build time via Docker ARG / environment variable.
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "development")
# BUILD_DATE is injected at Docker build time; falls back to startup timestamp.
BUILD_DATE = os.getenv("BUILD_DATE", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

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
        "build_date": BUILD_DATE,
        "model_stage": "placeholder",  # TODO: replace with MLflow model stage
    }


# ── Recommend (placeholder) ───────────────────────────────────────────────────
@app.post("/recommend", response_model=RecommendResponse, tags=["recommend"])
async def recommend(request: RecommendRequest) -> RecommendResponse:
    """
    Return top-N product recommendations for a given customer.

    **Current implementation:** returns deterministic mock data.
    **Planned implementation:**
      1. Look up pre-computed ALS candidates from BigQuery serving table.
      2. Score candidates with the LightGBM LambdaMART ranker.
      3. Return top-N items sorted by predicted relevance score.

    TODO(feat/two-stage-model): replace mock data with real inference.
    """
    if not request.customer_id:
        raise HTTPException(status_code=422, detail="customer_id must not be empty")

    # Mock recommendations — deterministic so unit tests are stable.
    mock_items = [
        RecommendedItem(article_id=f"0{i}928134{i:02d}", score=round(1.0 - i * 0.08, 3))
        for i in range(min(request.top_n, 10))
    ]

    return RecommendResponse(
        customer_id=request.customer_id,
        recommendations=mock_items,
        model_version=APP_VERSION,
        source="mock",  # TODO: change to "als+lgbm" after real model is wired in
    )
