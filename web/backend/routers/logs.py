from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from typing import List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, maybe receive commands
            data = await websocket.receive_text()
            # Echo or process commands (optional)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Helper function to push logs from other parts of the app
async def push_log(message: str):
    await manager.broadcast(message)
