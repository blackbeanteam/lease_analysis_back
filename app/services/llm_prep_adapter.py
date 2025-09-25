# app/services/llm_prep_adapter.py
from typing import Dict, Any
from app.models.extract_models import ExtractResult

def build_llm_input_text(extract: ExtractResult, *, max_chars: int = 120_000) -> str:
    parts = []
    for p in extract.pages:
        parts.append(f"[Page {p.page}]\n{(p.text or '').strip()}\n")
    full = "\n".join(parts)
    if max_chars and len(full) > max_chars:
        full = full[:max_chars] + "\n...[TRUNCATED]"
    return full
