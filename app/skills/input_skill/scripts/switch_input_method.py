from langchain_core.tools import tool
import pyautogui
import time
import ctypes
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
def switch_input_method(action: str = "toggle"):
    """
    切换或设置输入法状态。

    Args:
        action: 
            - "toggle": 模拟按下 Shift 键切换中英文 (默认)
            - "shift": 同 "toggle"
            - "win_space": 模拟 Win+Space 切换键盘布局
            - "ctrl_space": 模拟 Ctrl+Space 切换输入法
    """
    tool_name = "switch_input_method"
    try:
        action_val = str(action or "").strip()
        if action_val in ["toggle", "shift"]:
            pyautogui.press('shift')
            _emit_event(tool_name, "toggle", action=action_val)
            return _ok_payload("已模拟按下 Shift 键", action=action_val)
        elif action_val == "win_space":
            pyautogui.hotkey('win', 'space')
            _emit_event(tool_name, "toggle", action=action_val)
            return _ok_payload("已模拟 Win+Space", action=action_val)
        elif action_val == "ctrl_space":
            pyautogui.hotkey('ctrl', 'space')
            _emit_event(tool_name, "toggle", action=action_val)
            return _ok_payload("已模拟 Ctrl+Space", action=action_val)
        else:
            return _error_payload("invalid_args", f"未知动作: {action_val}", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("switch_failed", str(e), tool=tool_name)
