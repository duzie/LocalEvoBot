from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from pydantic import BaseModel
from ..shared import shared
import asyncio
import base64
import hashlib
import hmac
import io
import json
import wave
import datetime
from urllib.parse import quote
import websockets
import os
import sqlite3
import glob
from dotenv import dotenv_values, set_key
from typing import List
from fastapi import Body
from fastapi import Request
from fastapi.responses import PlainTextResponse

router = APIRouter()

class ChatMessage(BaseModel):
    message: str
    history: list = []
    new_session: bool = False

class ModelSelect(BaseModel):
    provider: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Hook up shared broadcast
async def broadcast_wrapper(message: str):
    await manager.broadcast(message)

shared.broadcast_func = broadcast_wrapper

@router.on_event("startup")
async def startup_event():
    shared.set_loop(asyncio.get_running_loop())

def _get_short_term_db_path(date_key: str = None):
    base_dir = os.path.dirname(_get_env_path())
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    if not date_key:
        date_key = datetime.datetime.now().astimezone().strftime("%Y%m%d")
    return os.path.join(data_dir, f"short_term_memory_{date_key}.sqlite3")

def _list_short_term_db_paths():
    base_dir = os.path.dirname(_get_env_path())
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(data_dir, "short_term_memory_*.sqlite3")))
    legacy_path = os.path.join(data_dir, "short_term_memory.sqlite3")
    if os.path.exists(legacy_path):
        paths.append(legacy_path)
    return paths

def _init_short_term_db(date_key: str = None):
    path = _get_short_term_db_path(date_key)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS short_term_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                project_id TEXT,
                user_id TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_created ON short_term_messages(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stm_project_user ON short_term_messages(project_id, user_id)")
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS short_term_messages_fts
            USING fts5(content, role, created_at, project_id, user_id)
            """
        )
        conn.commit()
    finally:
        conn.close()

@router.post("/send")
async def send_message(chat: ChatMessage):
    """Send a message to the Agent"""
    if not chat.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # 构造标准化的消息协议，由 main.py 统一解析
    payload = {
        "text": chat.message,
        "history": chat.history or [],
        "new_session": chat.new_session
    }
    shared.put_input("__CHAT_MSG__:" + json.dumps(payload, ensure_ascii=False))
    
    # Echo back to chat history (optional, or handle in frontend)
    return {"status": "sent"}

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, payload: dict = Body(...)):
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    expected = (os.getenv("WA_WEBHOOK_TOKEN") or env.get("WA_WEBHOOK_TOKEN") or "").strip()
    if expected:
        auth = str(request.headers.get("authorization") or "")
        if auth != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    text = str(payload.get("text") or "").strip()
    chat_jid = str(payload.get("chatJid") or payload.get("senderJid") or "").strip()
    sender_e164 = str(payload.get("senderE164") or "").strip()
    if not chat_jid or not text:
        raise HTTPException(status_code=400, detail="Invalid payload")

    shared.put_input(
        "__WA_IN__:" + json.dumps(
            {"chatJid": chat_jid, "senderE164": sender_e164, "text": text},
            ensure_ascii=False,
        )
    )
    return {"ok": True}

def _read_bool_env_value(key: str, default: bool = False) -> bool:
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    raw = (os.getenv(key) or env.get(key) or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default

def _read_env_value(key: str) -> str:
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    return (os.getenv(key) or env.get(key) or "").strip()

def _wa_allow_from_set() -> set[str]:
    raw = _read_env_value("WA_ALLOW_FROM")
    items = [s.strip() for s in raw.split(",")] if raw else []
    allow: set[str] = set()
    for it in items:
        if not it:
            continue
        allow.add(it)
        digits = "".join(ch for ch in it if ch.isdigit())
        if digits:
            allow.add(digits)
            allow.add("+" + digits)
    return allow

def _wa_is_allowed_dm(sender: str) -> bool:
    if not _read_bool_env_value("WA_DM_ENABLED", True):
        return False
    allow = _wa_allow_from_set()
    if len(allow) == 0:
        return True
    if "*" in allow:
        return True
    s = (sender or "").strip()
    if not s:
        return False
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits and (digits in allow or ("+" + digits) in allow):
        return True
    return s in allow

@router.get("/whatsapp/cloud/webhook")
async def whatsapp_cloud_verify(request: Request):
    expected = _read_env_value("WA_CLOUD_VERIFY_TOKEN")
    mode = str(request.query_params.get("hub.mode") or "")
    token = str(request.query_params.get("hub.verify_token") or "")
    challenge = str(request.query_params.get("hub.challenge") or "")
    if mode == "subscribe" and expected and token == expected and challenge:
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403, detail="Forbidden")

@router.post("/whatsapp/cloud/webhook")
async def whatsapp_cloud_webhook(request: Request, payload: dict = Body(...)):
    app_secret = _read_env_value("WA_CLOUD_APP_SECRET")
    if app_secret:
        sig = str(request.headers.get("x-hub-signature-256") or "")
        raw_body = await request.body()
        expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")

    received = 0
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes") or []
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            messages = value.get("messages") or []
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                sender = str(msg.get("from") or "").strip()
                mtype = str(msg.get("type") or "").strip()
                text = ""
                if mtype == "text":
                    body = msg.get("text") or {}
                    if isinstance(body, dict):
                        text = str(body.get("body") or "").strip()
                elif mtype == "button":
                    body = msg.get("button") or {}
                    if isinstance(body, dict):
                        text = str(body.get("text") or "").strip()
                elif mtype == "interactive":
                    inter = msg.get("interactive") or {}
                    if isinstance(inter, dict):
                        button_reply = inter.get("button_reply") or {}
                        list_reply = inter.get("list_reply") or {}
                        if isinstance(button_reply, dict):
                            text = str(button_reply.get("title") or button_reply.get("id") or "").strip()
                        elif isinstance(list_reply, dict):
                            text = str(list_reply.get("title") or list_reply.get("id") or "").strip()
                if not sender or not text:
                    continue
                if not _wa_is_allowed_dm(sender):
                    continue
                sender_e164 = ("+" + sender) if sender.isdigit() else sender
                shared.put_input(
                    "__WA_IN__:" + json.dumps(
                        {"chatJid": sender, "senderE164": sender_e164, "text": text, "provider": "cloud"},
                        ensure_ascii=False,
                    )
                )
                received += 1
    return {"ok": True, "received": received}

@router.get("/status")
async def get_status():
    return shared.get_status()

def _get_task_plan_path():
    base_dir = os.path.dirname(_get_env_path())
    return os.path.join(base_dir, "app", "skills", "system_skill", "scripts", "current_task_plan.json")

def _get_board_path():
    base_dir = os.path.dirname(_get_env_path())
    return os.path.join(base_dir, "app", "data", "board", "board.json")

def _load_board():
    path = _get_board_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _normalize_status(status: str) -> str:
    s = (status or "").strip()
    mapping = {
        "pending": "待处理",
        "todo": "待处理",
        "in_progress": "进行中",
        "doing": "进行中",
        "review": "待验收",
        "done": "已完成",
        "completed": "已完成",
        "rework": "需返工"
    }
    if s in mapping:
        return mapping[s]
    if s in {"待处理", "进行中", "待验收", "已完成", "需返工"}:
        return s
    return s or "待处理"

def _load_task_plan():
    path = _get_task_plan_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

@router.get("/progress")
async def get_progress():
    status = shared.get_status()
    plan = _load_task_plan()
    board = _load_board()
    completed_steps = []
    pending_steps = []
    total_steps = 0
    if isinstance(plan, dict):
        steps = plan.get("steps") or []
        total_steps = len(steps)
        for step in steps:
            if not isinstance(step, dict):
                continue
            desc = str(step.get("desc") or "").strip()
            if not desc:
                continue
            if step.get("status") == "completed":
                completed_steps.append(desc)
            elif step.get("status") == "pending":
                pending_steps.append(desc)
    next_steps = pending_steps[:1]
    current_activity = (status.get("status_message") or "").strip()
    if not current_activity:
        current_activity = (status.get("current_task") or "").strip()
    if not current_activity and next_steps:
        current_activity = next_steps[0]
    blocked_points = []
    if status.get("last_error"):
        blocked_points.append(status.get("last_error"))
    by_owner = []
    if isinstance(board, dict):
        tasks = board.get("tasks") or []
        grouped = {}
        for task in tasks:
            owner = str(task.get("owner") or "").strip() or "未分配"
            bucket = grouped.setdefault(owner, {"owner": owner, "total": 0, "done": 0, "doing": 0, "pending": 0, "review": 0, "rework": 0})
            bucket["total"] += 1
            st = _normalize_status(task.get("status") or "")
            if st == "已完成":
                bucket["done"] += 1
            elif st == "进行中":
                bucket["doing"] += 1
            elif st == "待处理":
                bucket["pending"] += 1
            elif st == "待验收":
                bucket["review"] += 1
            elif st == "需返工":
                bucket["rework"] += 1
        by_owner = sorted(grouped.values(), key=lambda x: x["owner"])
    return {
        "execution_status": status.get("execution_status"),
        "current_activity": current_activity,
        "completed_steps": completed_steps,
        "completed_count": len(completed_steps),
        "total_steps": total_steps,
        "progress_text": f"{len(completed_steps)}/{total_steps}" if total_steps else "",
        "blocked_points": blocked_points,
        "next_steps": next_steps,
        "by_owner": by_owner,
        "last_task_done_at": status.get("last_task_done_at"),
        "last_error_at": status.get("last_error_at")
    }

def _get_role_log_dir():
    base_dir = os.path.dirname(_get_env_path())
    return os.path.join(base_dir, "app", "data", "board", "role_logs")

def _read_tail_lines(path: str, limit: int = 200) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    except Exception:
        return []
    if limit and len(lines) > limit:
        return lines[-limit:]
    return lines

@router.get("/role-logs")
async def role_logs(limit: int = 200):
    safe_limit = max(1, min(int(limit or 200), 1000))
    base = _get_role_log_dir()
    if not os.path.isdir(base):
        return {"logs": []}
    items = []
    for path in sorted(glob.glob(os.path.join(base, "*.log"))):
        role = os.path.splitext(os.path.basename(path))[0]
        lines = _read_tail_lines(path, safe_limit)
        items.append({"role": role, "lines": lines, "line_count": len(lines)})
    return {"logs": items}

def _get_cookie_dir():
    base_dir = os.path.dirname(_get_env_path())
    data_dir = os.path.join(base_dir, "app", "data", "cookies")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def _sanitize_filename(value: str):
    text = str(value or "").strip().replace(" ", "_")
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-", "."))
    return cleaned or "default"

@router.post("/cookies/save")
async def save_cookies(payload: dict = Body(...)):
    """
    Save cookies posted by a browser extension.
    Expected payload: { "domain": "example.com", "cookies": [ {...}, ... ] }
    """
    domain = str(payload.get("domain") or "").strip()
    cookies = payload.get("cookies")
    if not domain or not isinstance(cookies, list):
        raise HTTPException(status_code=400, detail="Invalid payload: require domain and cookies list")
    fname = _sanitize_filename(domain) + ".json"
    path = os.path.join(_get_cookie_dir(), fname)
    content = json.dumps({"domain": domain, "cookies": cookies}, ensure_ascii=False, indent=2)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "ok", "saved_path": path, "count": len(cookies)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {e}")

@router.get("/cookies/{domain}")
async def get_cookies(domain: str):
    """
    Retrieve saved cookies for a domain.
    """
    fname = _sanitize_filename(domain) + ".json"
    path = os.path.join(_get_cookie_dir(), fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No cookies for this domain")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Read failed: {e}")

@router.get("/cookies")
async def list_cookies():
    """
    List saved cookie files.
    """
    base = _get_cookie_dir()
    items = []
    paths = sorted(glob.glob(os.path.join(base, "*.json")))
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        domain = name
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                domain = data.get("domain") or domain
                cookies = data.get("cookies")
                if isinstance(cookies, list):
                    count = len(cookies)
        except Exception:
            count = 0
        try:
            mtime = os.path.getmtime(path)
            updated_at = datetime.datetime.fromtimestamp(mtime).isoformat()
        except Exception:
            updated_at = ""
        items.append({
            "domain": domain,
            "file": os.path.basename(path),
            "count": count,
            "updated_at": updated_at
        })
    return {"items": items}

@router.delete("/cookies/{domain}")
async def delete_cookies(domain: str):
    """
    Delete saved cookies for a domain.
    """
    fname = _sanitize_filename(domain) + ".json"
    path = os.path.join(_get_cookie_dir(), fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No cookies for this domain")
    try:
        os.remove(path)
        return {"status": "deleted", "domain": domain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")

@router.post("/stop")
async def stop_current():
    """Request to stop current agent answer/task without affecting main dialog"""
    current_status = str(shared.execution_status or "").lower()
    if current_status in {"idle", "stopped"}:
        shared.clear_stop()
        shared.set_status("idle", "空闲", "")
        try:
            await manager.broadcast(">>> 系统: 状态=空闲")
        except Exception:
            pass
        return {"status": "idle"}

    shared.request_stop()
    shared.set_status("stopping", "停止中", shared.current_task)
    try:
        await manager.broadcast(">>> 系统: 状态=停止中")
    except Exception:
        pass
    return {"status": "stop_requested"}

@router.get("/history")
@router.get("/history")
@router.get("/history")
async def get_history(limit: int = 60):
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    base_dir = os.path.dirname(env_path)
    project_id = os.path.basename(base_dir)
    user_id = (os.getenv("LOCAL_USER_ID") or env.get("LOCAL_USER_ID") or "local_user").strip().strip("'\"")
    safe_limit = max(1, min(int(limit or 60), 200))
    db_paths = _list_short_term_db_paths()
    if not db_paths:
        _init_short_term_db()
        db_paths = [_get_short_term_db_path()]
    items = []
    
    # 修改查询逻辑，使其能够匹配数据库中user_id为空的记录
    sql = """SELECT role, content, created_at 
             FROM short_term_messages 
             WHERE project_id = ? 
             AND (user_id = ? OR user_id IS NULL OR user_id = '') 
             ORDER BY id DESC LIMIT ?"""
    
    for path in db_paths:
        conn = sqlite3.connect(path)
        try:
            cur = conn.cursor()
            rows = cur.execute(sql, (project_id, user_id, safe_limit)).fetchall()
            for r in rows:
                items.append({"role": r[0], "content": r[1], "created_at": r[2]})
        finally:
            conn.close()
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    items = items[:safe_limit]
    items.reverse()
    return {"messages": items}

def _get_xf_config():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    app_id = os.getenv("XF_APP_ID") or os.getenv("XF_APPID") or env.get("XF_APP_ID") or env.get("XF_APPID")
    api_key = os.getenv("XF_API_KEY") or os.getenv("XFAPI_KEY") or env.get("XF_API_KEY") or env.get("XFAPI_KEY")
    api_secret = os.getenv("XF_API_SECRET") or os.getenv("XFAPI_SECRET") or os.getenv("XFapi_secret") or env.get("XF_API_SECRET") or env.get("XFAPI_SECRET") or env.get("XFapi_secret")
    return (app_id or "").strip(), (api_key or "").strip(), (api_secret or "").strip()

def _wav_to_pcm16_mono_16k(wav_bytes: bytes):
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if channels != 1 or sampwidth != 2 or framerate != 16000:
        raise ValueError("Unsupported wav format")
    return frames

def _build_xf_url(api_key: str, api_secret: str):
    host = "iat-api.xfyun.cn"
    path = "/v2/iat"
    date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(api_secret.encode("utf-8"), signature_origin.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    return f"wss://{host}{path}?authorization={authorization}&date={quote(date)}&host={host}"

def _extract_text_from_result(data):
    text = ""
    if not isinstance(data, dict):
        return text
    if data.get("data") and isinstance(data["data"], dict):
        result = data["data"].get("result") or {}
        ws = result.get("ws") or []
        for item in ws:
            for cw in item.get("cw") or []:
                text += cw.get("w") or ""
    if not text and data.get("payload") and isinstance(data["payload"], dict):
        payload = data["payload"].get("result") or {}
        encoded = payload.get("text")
        if encoded:
            try:
                decoded = base64.b64decode(encoded).decode("utf-8")
                inner = json.loads(decoded)
                ws = inner.get("ws") or []
                for item in ws:
                    for cw in item.get("cw") or []:
                        text += cw.get("w") or ""
            except Exception:
                pass
    return text

async def _xf_asr(pcm: bytes, app_id: str, api_key: str, api_secret: str):
    url = _build_xf_url(api_key, api_secret)
    result_text = ""
    async with websockets.connect(url) as ws:
        frame_size = 1280
        chunks = [pcm[i:i + frame_size] for i in range(0, len(pcm), frame_size)]
        for idx, chunk in enumerate(chunks):
            status = 0 if idx == 0 else 1
            if idx == len(chunks) - 1:
                status = 2
            payload = {
                "common": {"app_id": app_id},
                "business": {"language": "zh_cn", "domain": "iat", "accent": "mandarin"},
                "data": {
                    "status": status,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": base64.b64encode(chunk).decode("utf-8")
                }
            }
            await ws.send(json.dumps(payload))
            if status == 0:
                break
        if len(chunks) > 1:
            for idx in range(1, len(chunks)):
                status = 1
                if idx == len(chunks) - 1:
                    status = 2
                payload = {
                    "data": {
                        "status": status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(chunks[idx]).decode("utf-8")
                    }
                }
                await ws.send(json.dumps(payload))
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if int(data.get("code", 0)) != 0:
                raise HTTPException(status_code=500, detail=data.get("message") or "ASR failed")
            result_text += _extract_text_from_result(data)
            status = None
            if data.get("data") and isinstance(data["data"], dict):
                status = data["data"].get("status")
            if status is None and data.get("payload") and isinstance(data["payload"], dict):
                status = data["payload"].get("status")
            if status == 2:
                break
    return result_text.strip()

@router.post("/asr")
async def speech_to_text(audio: UploadFile = File(...)):
    app_id, api_key, api_secret = _get_xf_config()
    if not app_id or not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Missing XF credentials")
    if not audio:
        raise HTTPException(status_code=400, detail="Audio required")
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio")
    try:
        pcm = _wav_to_pcm16_mono_16k(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wav audio")
    text = await _xf_asr(pcm, app_id, api_key, api_secret)
    return {"text": text}

def _get_env_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, ".env")

@router.get("/models")
async def list_models():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    current = (os.getenv("LLM_PROVIDER") or env.get("LLM_PROVIDER") or "doubao").strip().strip("'\"").lower()
    models = [
        {"id": "doubao", "label": "豆包"},
        {"id": "deepseek", "label": "DeepSeek"},
        {"id": "qwen", "label": "千问"},
        {"id": "openai", "label": "OpenAI"},
        {"id": "local", "label": "Local"},
        {"id": "nim_minimax_m2", "label": "NIM / MiniMax-M2"},
        {"id": "nim_glm47", "label": "NIM / GLM4.7"},
    ]
    return {"current": current, "models": models}

@router.post("/model")
async def set_model(selection: ModelSelect):
    provider = (selection.provider or "").strip().lower()
    allowed = {"doubao", "deepseek", "qwen", "openai", "local", "nim_minimax_m2", "nim_glm47"}
    if provider not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    env_path = _get_env_path()
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("")

    try:
        set_key(env_path, "LLM_PROVIDER", provider)
        os.environ["LLM_PROVIDER"] = provider
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    shared.put_input(f"__SET_MODEL__:{provider}")
    return {"status": "switching", "provider": provider}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't necessarily expect input from WS, but keep it open
            # User input comes via POST or this WS. 
            # Let's support WS input too for convenience.
            data = await websocket.receive_text()
            if data:
                shared.put_input(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
