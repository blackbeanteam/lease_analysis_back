import os, json, time
from typing import Optional
from openai import OpenAI
from httpx import Timeout, Limits
import httpx

from ..models.llm_models import LlmInput, LlmOutput

# === 以下内容直接参考你已有脚本（保留同样的语气/Schema/规则） === :contentReference[oaicite:7]{index=7}
LEASE_SCHEMA = {
    "name": "lease_struct",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "summary", "findings"],
        "properties": {
            "schema_version": {"type": "string"},
            "summary": {
                "type": "object",
                "additionalProperties": True,
                "required": ["verdict", "risk_score", "jurisdiction"],
                "properties": {
                    "verdict": {"enum": ["ok", "conditional_ok", "do_not_sign"]},
                    "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "jurisdiction": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["country", "state", "city"],
                        "properties": {
                            "country": {"type": "string"},
                            "state": {"type": "string"},
                            "city": {"type": "string"}
                        }
                    },
                    "notes": {"type": "string"}
                }
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["status", "category", "explanation", "evidence", "original_text"],
                    "properties": {
                        "id": {"type": "string"},
                        "status": {"enum": ["ok", "borderline", "non_compliant"]},
                        "severity": {"enum": ["low", "medium", "high"], "default": "medium"},
                        "category": {
                            "enum": [
                                "money_dates", "deposit_return", "renewal", "repairs_entry",
                                "termination", "insurance_indemnity", "rights_limits",
                                "utilities", "dispute", "other"
                            ]
                        },
                        "statutes": {"type": "array", "items": {"type": "string"}},
                        "explanation": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "original_text": {
                            "type": "string",
                            "minLength": 40,
                            "maxLength": 2000
                        },
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": True,
                                "required": ["page", "quote"],
                                "properties": {
                                    "page": {"type": "integer", "minimum": 1},
                                    "section": {"type": "string"},
                                    "quote": {
                                        "type": "string",
                                        "minLength": 20,
                                        "maxLength": 400
                                    }
                                }
                            }
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "string"},
                        "extensions": {"type": "object", "additionalProperties": True},
                        "low_confidence": {"type": "boolean"}
                    }
                }
            },
            "law_checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["rule", "status"],
                    "properties": {
                        "rule": {"type": "string"},
                        "status": {"enum": ["ok", "needs_detail", "exceeds", "missing"]},
                        "statute": {"type": "string"}
                    }
                }
            },
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["title", "priority", "blocker"],
                    "properties": {
                        "title": {"type": "string"},
                        "priority": {"enum": ["low", "medium", "high"]},
                        "blocker": {"type": "boolean"}
                    }
                }
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["page", "section"],
                    "properties": {
                        "page": {"type": "integer"},
                        "section": {"type": "string"}
                    }
                }
            },
            "unstructured_appendix": {"type": "string"}
        }
    }
}

SYSTEM_PROMPT = (
    "You are an extraction-and-compliance engine for residential leases under the relevant "
    "jurisdiction (country/state/city) and applicable U.S. federal law where relevant. "
    "Output VALID JSON ONLY that conforms to the provided JSON Schema. "
    "Do not include any prose outside JSON. Only rely on the contract text. "
    "For each finding, include: status, category, statutes (if any), explanation, recommendation, "
    "a short evidence.quote (20–50 words), page if known, and an `original_text` field with a longer "
    "contiguous excerpt (≈100–400 words) from the contract covering the clause, to support later "
    "human annotation. If you cannot find page or section, set them to null and mark low_confidence=true."
)

def build_rules_section(jurisdiction: dict | None) -> str:
    """
    Construct a concise English instruction to query jurisdiction-specific law.
    Expected jurisdiction example: {"country": "United States", "state": "WA"|"ALL_STATES"|"N/A"}
    """
    j = jurisdiction or {}
    country = j.get("country") or "United States"
    state   = j.get("state") or ""
    # 人类可读：US_ALL -> All U.S. states
    if state == "ALL_STATES": state_h = "all U.S. states (nationwide)"
    elif state in (None, "", "N/A", "OTHER"): state_h = "N/A"
    else: state_h = state

    focus = [
        "returned-check fees",
        "non-emergency entry notice",
        "security deposit accounting/timing",
        "auto-renew visibility and tenant rights",
        "service/assistance animals or pets",
        "holdover charges reasonableness"
    ]
    focus_str = ", ".join(focus)

    # 你要的措辞（更灵活，允许模型按需扩展/引用）
    return (
        "Research governing landlord–tenant law for the selected jurisdiction. "
        f"Jurisdiction: country = {country}"
        + (f", state/region = {state_h}" if state_h and state_h != "N/A" else "") + ". "
        "When evaluating the contract, consult and reflect applicable statutory/administrative rules "
        f"around {focus_str}. Cite or name statutes if feasible. Keep answers grounded in the contract text."
    )

def _client_from_env() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    http_client = httpx.Client(
        http2=False,
        headers={"Accept-Encoding": "identity", "Connection": "keep-alive"},
        timeout=Timeout(connect=30.0, read=120.0, write=30.0, pool=120.0),
        limits=Limits(max_connections=10, max_keepalive_connections=2),
        trust_env=False,
    )
    return OpenAI(http_client=http_client, api_key=api_key)

def run_leases_check_with_text(contract_text: str, *, jurisdiction: dict | None = None, retries:int=3, temperature:float=0.0, max_tokens:int=2000) -> LlmOutput:
    client = _client_from_env()

    user_prompt = (
        f"{build_rules_section(jurisdiction)}\n\n"
        "=== CONTRACT TEXT START ===\n"
        f"{contract_text}\n"
        "=== CONTRACT TEXT END ==="
    )

    last_err: Optional[Exception] = None
    for attempt in range(1, retries+1):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_schema", "json_schema": LEASE_SCHEMA},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
            )
            raw = resp.choices[0].message.content
            data = json.loads(raw)  # 期望严格 JSON
            return LlmOutput(**data)
        except Exception as e:
            last_err = e
            time.sleep(0.8 * attempt)

    raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")


