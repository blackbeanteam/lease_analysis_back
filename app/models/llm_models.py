# app/models/llm_models.py
from pydantic import BaseModel
from typing import List, Optional, Any

class LlmInput(BaseModel):
    full_text: str
    jurisdiction_hint: Optional[str] = None

class Finding(BaseModel):
    id: Optional[str] = None
    status: str
    severity: Optional[str] = None
    category: str
    statutes: List[str] = []
    explanation: str
    recommendation: Optional[str] = None
    original_text: str
    page: Optional[int] = None
    low_confidence: Optional[bool] = None
    tags: Optional[List[str]] = None

class LlmSummary(BaseModel):
    verdict: str
    risk_score: int
    jurisdiction: Optional[dict] = None
    notes: Optional[str] = None

class LlmOutput(BaseModel):
    schema_version: str = "1.0"
    summary: LlmSummary
    findings: List[Finding]
    raw_model: Optional[Any] = None
