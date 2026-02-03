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
from dotenv import dotenv_values, set_key
from typing import List

router = APIRouter()

class ChatMessage(BaseModel):
    message: str

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
            except:
                self.disconnect(connection)

manager = ConnectionManager()

# Hook up shared broadcast
async def broadcast_wrapper(message: str):
    await manager.broadcast(message)

shared.broadcast_func = broadcast_wrapper

@router.on_event("startup")
async def startup_event():
    shared.set_loop(asyncio.get_running_loop())

def _get_short_term_db_path():
    base_dir = os.path.dirname(_get_env_path())
    data_dir = os.path.join(base_dir, "app", "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "short_term_memory.sqlite3")

def _init_short_term_db():
    path = _get_short_term_db_path()
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
        conn.commit()
    finally:
        conn.close()

@router.post("/send")
async def send_message(chat: ChatMessage):
    """Send a message to the Agent"""
    if not chat.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    shared.put_input(chat.message)
    # Echo back to chat history (optional, or handle in frontend)
    return {"status": "sent"}

@router.get("/history")
async def get_history(limit: int = 60):
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    base_dir = os.path.dirname(env_path)
    project_id = os.path.basename(base_dir)
    user_id = (os.getenv("LOCAL_USER_ID") or env.get("LOCAL_USER_ID") or "local_user").strip().strip("'\"")
    safe_limit = max(1, min(int(limit or 60), 200))
    _init_short_term_db()
    path = _get_short_term_db_path()
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT role, content, created_at FROM short_term_messages WHERE project_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?",
            (project_id, user_id, safe_limit),
        ).fetchall()
        items = [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]
        items.reverse()
        return {"messages": items}
    finally:
        conn.close()

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
