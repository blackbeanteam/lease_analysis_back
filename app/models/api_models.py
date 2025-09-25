# app/models/api_models.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .llm_models import LlmOutput
from .extract_models import ExtractResult

class AnalyzeResponse(BaseModel):
    ok: bool = True
    meta: Dict[str, Any]
    llm: LlmOutput
    extract_debug: Optional[ExtractResult] = None
    llm_input_debug: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# === 新增：JSON(Base64) 上传的请求体 ===
class AnalyzeB64In(BaseModel):
    filename: str
    b64: str
    debug: bool = False

# --- jobs models ---
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel

class JobStatus(str, Enum):
    queued   = "queued"
    running  = "running"
    done     = "done"
    error    = "error"

class EnqueueResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.queued

class JobPollResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: Optional[str] = None
    result: Optional[Any] = None  # 完成后放最终分析 JSON
