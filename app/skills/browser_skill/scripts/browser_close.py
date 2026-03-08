"""
browser_close - 关闭浏览器

清理浏览器资源
"""

from langchain_core.tools import tool
import json
from typing import Dict, Any
from datetime import datetime
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
    payload = {
        "event": str(event or ""),
        "tool": str(tool_name or ""),
        "time": datetime.now().isoformat()
    }
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


@tool
def browser_close() -> Dict[str, Any]:
    """
    关闭浏览器，清理资源
    
    Returns:
        {
            "ok": True,
            "message": "浏览器已关闭"
        }
    
    Example:
        browser_close.invoke({})
    """
    tool_name = "browser_close"
    
    try:
        from app.skills.playwright_skill.scripts import _playwright_core as core
        
        # 关闭浏览器
        core._close_browser()
        
        _emit_event(tool_name, "close")
        
        return _ok_payload("浏览器已关闭")
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("close_failed", f"关闭失败：{e}", tool=tool_name)
