"""Pydantic models for contribution review system."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload model."""
    action: str
    issue: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None
    repository: Dict[str, Any]
    sender: Dict[str, Any]


class ContributionReview(BaseModel):
    """Contribution review decision model."""
    contribution_id: str
    type: Literal["bug_report", "pull_request", "build_share"]
    contributor: str
    contributor_email: Optional[str] = None
    github_url: str
    recommendation: Literal["approve", "review", "reject"]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    promo_tier: Optional[str] = None
    webhook_payload: Optional[Dict[str, Any]] = None


class ReviewDecision(BaseModel):
    """Review decision output."""
    contribution_id: str
    type: str
    contributor: str
    recommendation: str
    reason: str
    promo_tier: Optional[str] = None
    confidence: float
    auto_approved: bool = False


class PromoCodeRequest(BaseModel):
    """Promo code generation request."""
    tier: str
    contributor: str
    contributor_email: str
    contribution_id: str
    reason: str


class PromoCodeResult(BaseModel):
    """Promo code generation result."""
    code: str
    tier: str
    duration_months: int
    sent_at: Optional[datetime] = None
    email_status: str = "pending"


class MissionControlTask(BaseModel):
    """Mission Control TODO item."""
    title: str
    description: str
    priority: str = "medium"
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
