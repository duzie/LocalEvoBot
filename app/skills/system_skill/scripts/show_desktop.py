from langchain_core.tools import tool
import pyautogui
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

@tool
def show_desktop():
    """
    显示桌面，点击屏幕右下角的“显示桌面”区域。
    """
    tool_name = "show_desktop"
    try:
        width, height = pyautogui.size()
        x = max(0, width - 5)
        y = max(0, height - 5)
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        _emit_event(tool_name, "show")
        return _ok_payload("已显示桌面")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("show_desktop_failed", str(e), tool=tool_name)
