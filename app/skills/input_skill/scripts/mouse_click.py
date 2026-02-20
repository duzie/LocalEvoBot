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
def mouse_click(x: int, y: int, clicks: int = 1, button: str = 'left'):
    """
    模拟鼠标点击。
    
    Args:
        x: 屏幕 X 坐标
        y: 屏幕 Y 坐标
        clicks: 点击次数，默认为 1
        button: 鼠标按键，'left', 'middle', 'right'，默认为 'left'
    """
    tool_name = "mouse_click"
    try:
        button_name = str(button or "left").strip().lower()
        click_times = max(1, int(clicks or 1))
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click(clicks=click_times, button=button_name)
        _emit_event(tool_name, "click", x=x, y=y, button=button_name, clicks=click_times)
        return _ok_payload("鼠标点击完成", x=x, y=y, button=button_name, clicks=click_times)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("mouse_click_failed", str(e), tool=tool_name)
