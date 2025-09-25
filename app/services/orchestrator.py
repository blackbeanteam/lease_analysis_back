# app/services/orchestrator.py
import json
from app.models.api_models import AnalyzeResponse
from app.services.pdf_extract import extract_from_pdf_bytes
from app.services.llm_prep_adapter import build_llm_input_text
from app.services.llm_client_existing import run_leases_check_with_text

def analyze_pipeline(filename: str, data: bytes, *, debug: bool=False, jurisdiction: dict | None = None) -> AnalyzeResponse:
    # 1) pdf -> json
    extract = extract_from_pdf_bytes(filename, data)
    if debug:
        # 直接打印：模型对象也能打印；另外补一行更友好的摘要
        print("[extract]", extract, flush=True)
        try:
            pages = getattr(extract, "pages", []) or []
            p1 = (pages[0].text if pages else "") or ""
            print(f"[extract_summary] ok={extract.ok} pages={getattr(extract.meta,'page_count',None)} "
                  f"p1_text100='{p1[:100]}'", flush=True)
        except Exception as _:
            pass
    if not extract.ok:
        return AnalyzeResponse(ok=False, meta={"filename": filename}, error=extract.error, llm=None)  # type: ignore

    # 2) json -> text（沿用你的 prompt_builder 组织方式）
    llm_text = build_llm_input_text(extract)
    if debug:
        # 只打印前 2000 个字符，防止日志过大
        print("[llm_text]", (llm_text[:2000] + (" ...[truncated]" if len(llm_text) > 2000 else "")), flush=True)

    # 3) text -> OpenAI 严格 JSON
    llm_out = run_leases_check_with_text(llm_text, jurisdiction=jurisdiction or {})
    if debug:
        try:
            payload = llm_out.model_dump() if hasattr(llm_out, "model_dump") else (
                llm_out if isinstance(llm_out, dict) else str(llm_out)
            )
            s = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
            print("[llm_out]", (s[:2000] + (" ...[truncated]" if len(s) > 2000 else "")), flush=True)
        except Exception as _:
            print("[llm_out] <print failed>", flush=True)

    # 4) 汇总
    return AnalyzeResponse(
        ok=True,
        meta=extract.meta.dict() if hasattr(extract.meta, "dict") else extract.meta.model_dump(),
        llm=llm_out,
        extract_debug=extract if debug else None,
        llm_input_debug={"full_text": llm_text[:2000] + (" ...[truncated]" if len(llm_text) > 2000 else "")} if debug else None,
    )

