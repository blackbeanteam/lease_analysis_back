# app/models/extract_models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class TextBlock(BaseModel):
    bbox: List[float] = Field(..., description="[x0,y0,x1,y1]")
    text: str

class ExtractPage(BaseModel):
    page: int
    text: str
    blocks: List[TextBlock] = []

class ExtractMeta(BaseModel):
    filename: str
    page_count: int
    sha256: str

class ExtractResult(BaseModel):
    ok: bool = True
    meta: ExtractMeta
    pages: List[ExtractPage]
    error: Optional[str] = None
