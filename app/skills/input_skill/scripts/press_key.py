from langchain_core.tools import tool
import pyautogui
import time
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
def press_key(key: str, times: int = 1):
    """
    模拟按下特定的键盘按键。
    
    Args:
        key: 按键名称，例如 "enter", "tab", "esc", "backspace", "space", "up", "down", "left", "right"
             也支持组合键如 "ctrl+c" (尚未完全支持解析，建议仅用单键)
        times: 按下次数，默认为 1
    """
    tool_name = "press_key"
    try:
        time.sleep(0.2)
        valid_keys = ['enter', 'tab', 'esc', 'backspace', 'space', 'up', 'down', 'left', 'right', 
                      'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                      'pageup', 'pagedown', 'home', 'end', 'insert', 'delete']
        
        key_lower = str(key or "").lower().strip()
        if not key_lower:
            return _error_payload("invalid_args", "key 不能为空", tool=tool_name)
        if key_lower not in valid_keys and len(key_lower) > 1:
            return _error_payload("invalid_args", f"不支持的按键: {key}", tool=tool_name)

        pyautogui.press(key_lower, presses=max(1, int(times or 1)))
        _emit_event(tool_name, "press", key=key_lower, times=max(1, int(times or 1)))
        return _ok_payload("按键完成", key=key_lower, times=max(1, int(times or 1)))
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("press_failed", str(e), tool=tool_name)
