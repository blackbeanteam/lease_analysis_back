# app/main.py
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
import base64, os, time, logging, sys, traceback, json
from fastapi.middleware.cors import CORSMiddleware

# 降低 httpx/httpcore 的日志噪音
for name in ("httpx", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)

# ===== logging setup =====
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("lease")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        t0 = time.time()
        clen = request.headers.get("content-length", "-")
        try:
            log.info(f"[req] {request.method} {request.url.path} q={dict(request.query_params)} len={clen}")
            resp: StarletteResponse = await call_next(request)
            dt = int((time.time() - t0) * 1000)
            log.info(f"[res] {request.method} {request.url.path} -> {resp.status_code} {dt}ms")
            return resp
        except Exception:
            dt = int((time.time() - t0) * 1000)
            log.error(f"[res] {request.method} {request.url.path} -> 500 {dt}ms\n{traceback.format_exc()}")
            raise

from app.services.orchestrator import analyze_pipeline
from app.models.api_models import AnalyzeB64In, EnqueueResponse, JobPollResponse, JobStatus
from app.services.job_store import (
    enqueue_job, pop_jobs, set_status, save_result, save_error, get_job
)

import httpx   # fire-and-forget self trigger + blob helpers

# === Blob helper endpoints (Node routes in the same Vercel project) ===
# We call these tiny Node handlers because Vercel Blob private objects
# are easiest to access/delete via @vercel/blob on Node.
# Example:
#   POST   /api/blob/upload   -> issues client-upload token (used by the extension)
#   GET    /api/blob/fetch    -> returns raw bytes of a private blob (server-to-server)
#   POST   /api/blob/delete   -> deletes a blob by pathname
BLOB_HELPER_BASE = os.environ.get("BLOB_HELPER_BASE") or ""  # e.g. "https://<your-app>.vercel.app"
if not BLOB_HELPER_BASE:
    # When FastAPI is deployed behind Vercel, we'll compute base_url per-request.
    # Having this env makes local/dev calls simpler.
    pass
    
def create_app() -> FastAPI:
    app = FastAPI(title="Lease Analysis Backend", version="0.1.0")
    app.add_middleware(AccessLogMiddleware)
    
    # === CORS（关键）===
    # 多个来源用逗号分隔：例如 "http://localhost:5173,https://your-frontend.com"
    allow_origins = os.getenv("CORS_ALLOW_ORIGIN")
    origins = [o.strip() for o in allow_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,          # 如不需要携带 cookie，可改 False
        allow_methods=["GET","POST","OPTIONS"],
        allow_headers=["*"],             # 至少要包含 Content-Type
        expose_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"message": "Lease Analysis Backend is running"}

    # ========= New: enqueue by Blob pathname (no base64 in Redis) =========
    @app.post("/analyzeLeaseByUrl", tags=["upload"])
    def enqueue_by_url(p: dict = Body(...), request: Request = None) -> JSONResponse:
        """
        Accepts { pathname, name?, size?, debug? } where `pathname` is the Blob's private identifier
        returned by the client-upload flow. We only store metadata and the pathname.
        """
        pathname = p.get("pathname") or p.get("path") or p.get("blob_pathname")
        if not pathname:
            raise HTTPException(status_code=400, detail="missing pathname")
        filename = p.get("name") or "Lease.pdf"
        debug = bool(p.get("debug", 0))
        size = int(p.get("size", 0))
        jurisdiction = p.get("jurisdiction") or {}

        # Minimal metadata-only enqueue. Your job_store can accept extra fields;
        # here we reuse the existing enqueue_job for id/queue, then stash pathname into the hash.
        job_id = enqueue_job(filename, b64="", debug=debug)  # b64 intentionally empty
        try:
            from app.services import job_store as _js
            _js._r.hset(_js._hkey(job_id), mapping={
                "blob_pathname": pathname,
                "size": size,
                "b64": "",  # ensure no content copy is kept
                "jurisdiction": json.dumps(jurisdiction, ensure_ascii=False)
            })
        except Exception as e:
            log.error(f"[enqueue-url] failed to stash pathname: {e}")
            raise HTTPException(status_code=500, detail="enqueue failed")

        # Fire-and-forget worker trigger (tolerate cold-start) + clear logs
        try:
            #base_url = str(request.base_url).rstrip("/")
            #tick = f"{base_url}/worker/tick?single={job_id}"
            
            scheme = request.headers.get("x-forwarded-proto", "https")
            host   = request.headers.get("host")
            tick = f"{scheme}://{host}/worker/tick?single={job_id}"
    
            # Give it a little more headroom; cold start often > 200ms
            with httpx.Client(timeout=httpx.Timeout(0.8)) as c:
                r = c.get(tick)
            log.info(f"[enqueue-url] self-trigger {tick} -> {getattr(r, 'status_code', 0)}")
        except httpx.TimeoutException as e:
            log.info(f"[enqueue-url] self-trigger timed out (ignored): {e}")
        except Exception as e:
            log.warning(f"[enqueue-url] self-trigger error: {e}")

        return JSONResponse(status_code=202, content=EnqueueResponse(job_id=job_id).model_dump())

    # ========= 轮询：前端一直打这个 =========
    @app.get("/jobs/{job_id}", response_model=JobPollResponse)
    def poll(job_id: str):
        log.info(f"[poll] job_id={job_id}")
        data = get_job(job_id)
        if not data:
            log.warning(f"[poll] job_id={job_id} not found")
            raise HTTPException(status_code=404, detail="job not found")
        return JobPollResponse(
            job_id=job_id,
            status=JobStatus(data["status"]),
            message=data.get("message"),
            result=data.get("result"),
        )

    # ========= worker：支持处理单个 / 或批量 =========
    @app.get("/worker/tick")
    def worker_tick(request: Request, single: str | None = None):
        log.info(f"[worker] start single={single!r}")
        print(f"[worker] start single={single!r}")
        handled = 0
        ids = [single] if single else pop_jobs(max_n=3)
        log.info(f"[worker] pop -> {ids}")
        print(f"[worker] pop -> {ids}")

        for job_id in ids:
            if not job_id:
                continue
            handled += 1
            try:
                set_status(job_id, "running", "decoding")
                data = get_job(job_id)
                if not data:
                    log.warning(f"[worker] job_id={job_id} hgetall miss")
                    print(f"[worker] job_id={job_id} hgetall miss")
                    continue
                filename = data["filename"]
                debug = data.get("debug", False)
                log.info(f"[worker] job_id={job_id} file={filename!r} debug={debug}")
                print(f"[worker] job_id={job_id} file={filename!r} debug={debug}")

                # Acquire PDF bytes: prefer private Blob pathname
                raw = None
                blob_pathname = data.get("blob_pathname")
                log.info(f"[worker] fetching blob_pathname={blob_pathname!r}")
                print(f"[worker] fetching blob_pathname={blob_pathname!r}")
                if blob_pathname:
                    set_status(job_id, "running", "downloading")
                    # Prefer explicit env; otherwise same origin as this function
                    base_url = (BLOB_HELPER_BASE or str(request.base_url)).rstrip("/")
                    # Server-to-server fetch of private blob bytes (POST JSON)
                    fetch_url = f"{base_url}/api/blob/fetch"
                    with httpx.Client(timeout=30.0) as c:
                        fr = c.post(fetch_url, json={"pathname": blob_pathname})
                        if fr.status_code != 200:
                            # surface the first 200 chars of body to logs to know *why* it's 400
                            err_txt = fr.text[:200] if hasattr(fr, "text") else ""
                            log.error(f"[worker] blob fetch failed: {fr.status_code} body={err_txt!r}")
                            print(f"[worker] blob fetch failed: {fr.status_code} body={err_txt!r}")
                            raise RuntimeError(f"blob fetch failed: {fr.status_code}")
                        raw = fr.content
                
                set_status(job_id, "running", "analyzing")
                t0 = time.time()
                # 取回地域参数并传入分析管线
                j = {}
                try:
                    if data.get("jurisdiction"):
                        j = json.loads(data["jurisdiction"])
                except Exception:
                    j = {}
                result = analyze_pipeline(filename or "unknown.pdf", raw, debug=bool(debug), jurisdiction=j)
                dt = int((time.time() - t0) * 1000)
                log.info(f"[worker] job_id={job_id} analyze done in {dt}ms")
                print(f"[worker] job_id={job_id} analyze done in {dt}ms")

                # 兼容 pydantic 模型 / dict
                out = result.model_dump() if hasattr(result, "model_dump") else result
                ok  = getattr(result, "ok", True) if not isinstance(result, dict) else True

                if ok:
                    save_result(job_id, out)
                    log.info(f"[worker] job_id={job_id} -> done")
                    print(f"[worker] job_id={job_id} -> done")
                    # Best-effort delete the private blob after success
                    try:
                        blob_pathname = blob_pathname or data.get("blob_pathname")
                        if blob_pathname:
                            base_url = (BLOB_HELPER_BASE or str(request.base_url)).rstrip("/")
                            del_url = f"{base_url}/api/blob/delete"
                            with httpx.Client(timeout=10.0) as c:
                                c.post(del_url, json={"pathname": blob_pathname})
                    except Exception as _:
                        # Ignore deletion errors; lifecycle policies or cron can clean up
                        pass
                else:
                    err = getattr(result, "error", "unknown error")
                    save_error(job_id, err)
                    log.warning(f"[worker] job_id={job_id} -> error: {err}")
                    print(f"[worker] job_id={job_id} -> error: {err}")
            except Exception as e:
                log.error(f"[worker] job_id={job_id} crashed: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                print(f"[worker] job_id={job_id} crashed: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                save_error(job_id, f"{type(e).__name__}: {e}")
        return {"handled": handled, "single": single}
    
    return app

app = create_app()





















