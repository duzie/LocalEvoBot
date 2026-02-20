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
def select_all():
    """
    全选当前焦点输入框中的文本 (Ctrl+A)。
    常用于在输入新内容前清除旧内容（全选后直接输入即可覆盖）。
    """
    tool_name = "select_all"
    try:
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'a')
        _emit_event(tool_name, "select_all")
        return _ok_payload("已执行全选")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("select_all_failed", str(e), tool=tool_name)
