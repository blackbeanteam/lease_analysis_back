# app/services/job_store.py
import os, json, time, uuid, logging
from typing import Optional, Dict, Any, List
import redis

log = logging.getLogger("lease")

REDIS_URL = os.environ["REDIS_URL"]
JOB_TTL   = int(os.environ.get("JOB_TTL_SECONDS", "86400"))

QKEY = "lease:jobs:queue"   # 待处理队列（list）
HPFX = "lease:job:"         # 每个任务的 hash 前缀

_r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def _hkey(job_id: str) -> str:
    return f"{HPFX}{job_id}"

def new_job_id() -> str:
    return uuid.uuid4().hex

def enqueue_job(filename: str, b64: str, debug: bool) -> str:
    """
    将任务写入：hash 保存任务内容 + list 入队
    注意：Redis 不接受 bool，统一转 int(0/1) 或 str
    """
    job_id = new_job_id()
    hk = _hkey(job_id)
    payload: Dict[str, Any] = {
        "job_id": str(job_id),
        "filename": str(filename),
        "b64": str(b64),
        "debug": int(bool(debug)),        # 关键修复：bool -> 0/1
        "status": "queued",
        "created_at": int(time.time()),
    }
    log.info(f"[redis] HSET {hk} (ttl={JOB_TTL}) + RPUSH {QKEY} job_id={job_id}")
    p = _r.pipeline()
    p.hset(hk, mapping=payload)
    p.expire(hk, JOB_TTL)
    p.rpush(QKEY, job_id)
    p.execute()
    return job_id

def pop_jobs(max_n: int = 1) -> List[str]:
    """
    先 LLEN 再 LPOP，减少无效命令；返回弹出的 job_id 列表
    """
    n = min(max_n, int(_r.llen(QKEY)))
    log.info(f"[redis] LLEN {QKEY} = {n}")
    ids: List[str] = []
    for _ in range(n):
        j = _r.lpop(QKEY)
        if j:
            ids.append(j)
    log.info(f"[redis] LPOP {QKEY} -> {ids}")
    return ids

def set_status(job_id: str, status: str, message: Optional[str] = None):
    hk = _hkey(job_id)
    m: Dict[str, Any] = {"status": str(status)}
    if message is not None:
        m["message"] = str(message)       # 保底转字符串
    log.info(f"[redis] HSET {hk} status={status} msg={message!r}")
    _r.hset(hk, mapping=m)

def save_result(job_id: str, result_obj: Any):
    hk = _hkey(job_id)
    # result 序列化为 JSON 字符串
    result_json = json.dumps(result_obj, ensure_ascii=False)
    log.info(f"[redis] HSET {hk} status=done + result(len)={len(result_json)}")
    _r.hset(hk, mapping={
        "status": "done",
        "result": result_json,
        "finished_at": int(time.time()),
    })

def save_error(job_id: str, err: str):
    hk = _hkey(job_id)
    log.warning(f"[redis] HSET {hk} status=error msg={err!r}")
    _r.hset(hk, mapping={
        "status": "error",
        "message": str(err),
        "finished_at": int(time.time()),
    })

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    hk = _hkey(job_id)
    data = _r.hgetall(hk)
    log.info(f"[redis] HGETALL {hk} -> {'hit' if data else 'miss'}")
    if not data:
        return None
    # 反序列化 result（如果有）
    if "result" in data and isinstance(data["result"], str):
        try:
            data["result"] = json.loads(data["result"])
        except Exception as e:
            log.warning(f"[redis] parse result JSON fail: {e}")
    # 把 debug 恢复为 bool（非必须，仅方便使用方）
    if "debug" in data:
        try:
            data["debug"] = bool(int(data["debug"]))
        except Exception:
            pass
    return data
