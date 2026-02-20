from langchain_core.tools import tool
import pyautogui
import os
import datetime
import json
from datetime import datetime as dt
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
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": dt.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

@tool
def take_screenshot(save_path: str = None):
    """
    截取当前屏幕并保存。
    
    Args:
        save_path: (可选) 保存路径。
                   如果是目录，会自动生成文件名 (screenshot_YYYYMMDD_HHMMSS.png)。
                   如果未提供，默认保存到当前运行目录的 images 文件夹。
    """
    tool_name = "take_screenshot"
    try:
        if not save_path:
            save_path = os.path.join(os.getcwd(), "images")
        
        if os.path.isdir(save_path) or not os.path.splitext(save_path)[1]:
            os.makedirs(save_path, exist_ok=True)
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            final_path = os.path.join(save_path, filename)
        else:
            parent_dir = os.path.dirname(save_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            final_path = save_path

        pyautogui.screenshot(final_path)
        _emit_event(tool_name, "screenshot", path=final_path)
        return _ok_payload("截图已保存", path=final_path)
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("screenshot_failed", str(e), tool=tool_name)
