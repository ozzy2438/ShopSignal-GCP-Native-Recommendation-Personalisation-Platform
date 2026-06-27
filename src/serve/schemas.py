"""Pydantic schemas for the ShopSignal recommendation API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    customer_id: str = Field(..., description="Hashed customer identifier from H&M dataset")
    top_n: int = Field(default=10, ge=1, le=50, description="Number of items to return")

    model_config = {
        "json_schema_extra": {
            "example": {"customer_id": "00000dbacae5abe5e23885899a1fa44253a17956", "top_n": 10}
        }
    }


class RecommendedItem(BaseModel):
    article_id: str = Field(..., description="H&M article identifier")
    score: float = Field(..., description="Predicted relevance score (higher is better)")


class RecommendResponse(BaseModel):
    customer_id: str
    recommendations: list[RecommendedItem]
    model_version: str
    source: str = Field(..., description="'mock' | 'als+lgbm' | 'bigquery-batch'")
