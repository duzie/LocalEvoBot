from typing import Dict, Any, Optional
import os
import json
from datetime import datetime
from web.backend.shared import shared

class SkillException(Exception):
    """
    Base exception for skill tools.
    Raising this exception allows StandardizedTool to catch it and format a standardized error payload.
    """
    def __init__(self, code: str, message: str, **kwargs):
        self.code = code
        self.message = message
        self.details = kwargs
        super().__init__(message)

def get_project_root() -> str:
    """Returns the absolute path to the project root directory."""
    # Assuming this file is in app/skills/common.py
    # Root is ../../../
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    """
    Helper to create a success payload.
    """
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    """
    Helper to create an error payload.
    """
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def emit_event(tool_name: str, event: str, **fields):
    """
    Emit a thread-safe event for the frontend/logs.
    """
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))
