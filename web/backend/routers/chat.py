from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from ..shared import shared
import asyncio
import os
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

@router.post("/send")
async def send_message(chat: ChatMessage):
    """Send a message to the Agent"""
    if not chat.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    shared.put_input(chat.message)
    # Echo back to chat history (optional, or handle in frontend)
    return {"status": "sent"}

def _get_env_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, ".env")

@router.get("/models")
async def list_models():
    env_path = _get_env_path()
    env = dotenv_values(env_path) if os.path.exists(env_path) else {}
    current = (os.getenv("LLM_PROVIDER") or env.get("LLM_PROVIDER") or "deepseek").strip().lower()
    models = [
        {"id": "deepseek", "label": "DeepSeek"},
        {"id": "qwen", "label": "千问"},
        {"id": "openai", "label": "OpenAI"},
        {"id": "nim_minimax_m2", "label": "NIM / MiniMax-M2"},
        {"id": "nim_glm47", "label": "NIM / GLM4.7"},
    ]
    return {"current": current, "models": models}

@router.post("/model")
async def set_model(selection: ModelSelect):
    provider = (selection.provider or "").strip().lower()
    allowed = {"deepseek", "qwen", "openai", "nim_minimax_m2", "nim_glm47"}
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
