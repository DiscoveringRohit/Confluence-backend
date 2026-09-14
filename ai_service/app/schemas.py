from typing import List, Optional
from pydantic import BaseModel, Field


class ExistingIssue(BaseModel):
    """One prior issue to check the new submission against for dedup.
    Optional on the request — see README for the payload-contract note."""
    id: int
    title: str
    description: str
    district: Optional[str] = None


class TriageRequest(BaseModel):
    title: str
    description: str
    district: Optional[str] = None
    existing_issues: Optional[List[ExistingIssue]] = Field(default=None)


class TriageResponse(BaseModel):
    predicted_category: str
    confidence: float
    summary: str
    potential_duplicate_id: Optional[int] = None
